#!/usr/bin/env python3
"""Per-UAV and fleet telemetry collector for the 2-UAV smoke contract."""

import argparse
import itertools
import json
import math
from pathlib import Path
import threading
import time

import yaml


def jaccard(left, right):
    union = left | right
    return float(len(left & right)) / len(union) if union else 0.0


def overlap_ratio(left, right):
    denominator = min(len(left), len(right))
    return float(len(left & right)) / denominator if denominator else 0.0


def planner_box_voxels(box_min, box_max, resolution):
    cells = [int(math.ceil((upper - lower) / resolution))
             for lower, upper in zip(box_min, box_max)]
    return math.prod(cells)


def vehicle_alias_map(config):
    """Map collision-name tokens (uavN / iris_<racer_id-1>) to vehicle names."""
    aliases = {}
    for spec in config.get("vehicles", []):
        aliases[spec["name"].lower()] = spec["name"]
        aliases["iris_%d" % (int(spec["racer_id"]) - 1)] = spec["name"]
    return aliases


def vehicle_names(collision_name, alias_map=None):
    name = collision_name.lower()
    if alias_map is None:
        # Pre-D5 two-UAV contract keeps pure callers and self-tests stable.
        alias_map = {"uav0": "uav0", "iris_0": "uav0",
                     "uav1": "uav1", "iris_1": "uav1"}
    return {vehicle for token, vehicle in alias_map.items() if token in name}


def contact_category(collision1, collision2, alias_map=None):
    names = (collision1 + " " + collision2).lower()
    vehicles = vehicle_names(names, alias_map)
    if len(vehicles) == 2:
        return "inter_uav", vehicles
    if not vehicles:
        return "unrelated", vehicles
    if "ground" in names or "plane" in names:
        return "ground", vehicles
    return "obstacle", vehicles


def pairwise_fleet_metrics(maps):
    """Fleet-wide overlap/jaccard across every vehicle pair.

    For the 2-UAV contract this reduces to the original single pair
    (maps[0], maps[1]); for N>2 the most conservative (minimum) pairwise
    values are reported so no weaker pair is masked.
    """
    overlaps = [overlap_ratio(left, right)
                for left, right in itertools.combinations(maps, 2)]
    jaccards = [jaccard(left, right)
                for left, right in itertools.combinations(maps, 2)]
    return (min(overlaps) if overlaps else 0.0,
            min(jaccards) if jaccards else 0.0)


def severe_contact(category, force_n, duration_s, force_threshold_n,
                   persistence_threshold_s):
    return category in {"obstacle", "inter_uav"} and (
        force_n >= force_threshold_n or duration_s >= persistence_threshold_s)


def exactly_one_topic_owner(owners):
    return (isinstance(owners, (list, tuple)) and len(owners) == 1 and
            isinstance(owners[0], str) and bool(owners[0]))


def liveness_state(expected_nodes, seen_nodes, live_nodes, active):
    """Classify liveness without calling normal teardown a process death."""
    expected = set(expected_nodes)
    seen = set(seen_nodes)
    live = set(live_nodes)
    updated_seen = seen | (expected & live)
    missing = expected - live
    return {
        "seen": updated_seen,
        "never_seen": sorted(expected - updated_seen),
        "lost_after_seen": sorted(updated_seen - live),
        "process_death": sorted(missing) if active else [],
        "process_liveness": {node: node in live for node in sorted(expected)},
    }


def dropout_classification(vehicle_name, dropout_record, liveness, snapshot, active,
                           vehicle_nodes=None):
    """Classify a vehicle per D0 semantics: intentional/unexpected/telemetry_missing/none.

    The runner-authored fleet/dropout.json is authoritative for the vehicle it names;
    otherwise a liveness break on the vehicle's *own* nodes is unexpected_loss and a
    channel break while the process tree survives is telemetry_missing.  Teardown
    (active=False) never invents a fault classification on its own.
    """
    if dropout_record is not None and dropout_record.get("vehicle") == vehicle_name:
        return "intentional_dropout"
    if not active:
        return "none"
    if liveness and liveness.get("lost_after_seen"):
        if vehicle_nodes is None:
            return "unexpected_loss"
        own_lost = [node for node in liveness["lost_after_seen"] if node in vehicle_nodes]
        if own_lost:
            return "unexpected_loss"
    if snapshot and (snapshot.get("telemetry_stale_channels") or
                     snapshot.get("telemetry_missing_channels")):
        return "telemetry_missing"
    return "none"


def dropout_continue_evidence(baseline, report, dropped=False):
    """Per-vehicle continuation evidence after the dropout baseline.

    A survivor "continues" when it produced new coverage, telemetry, or path
    progress after the dropout record first appeared; the dropped vehicle is
    explicitly not a survivor and reports no post-dropout coverage delta.
    """
    if dropped:
        return {"continued": False, "coverage_delta": None}
    if not isinstance(baseline, dict):
        return {"continued": None, "coverage_delta": None}
    cov_now = report.get("coverage", {}).get("observed_voxels", 0)
    cov_delta = max(0, int(cov_now) - int(baseline.get("coverage_voxels", 0)))
    telemetry = report.get("telemetry", {})
    progressed = (cov_delta > 0 or
                  telemetry.get("ack", 0) > baseline.get("ack", 0) or
                  telemetry.get("pos_cmd", 0) > baseline.get("pos_cmd", 0) or
                  telemetry.get("odometry", 0) > baseline.get("odometry", 0) or
                  report.get("path_length_m", 0.0) > baseline.get("path_length_m", 0.0))
    return {"continued": bool(progressed), "coverage_delta": cov_delta}


def apply_dropout_report(report, dropout_record):
    """Overlay intentional-dropout semantics on a vehicle metrics report.

    The dropped UAV must not be mislabelled crash/contact/freeze; its telemetry
    incompleteness is expected, and post-dropout ACK timeouts are the consequence of
    the injected fault, not a fleet safety failure.
    """
    report["dropout"] = True
    report["dropout_classification"] = "intentional_dropout"
    report["dropout_mode"] = dropout_record.get("mode")
    report["dropout_sim_s"] = dropout_record.get("sim_s")
    report["dropout_pids"] = dropout_record.get("pids")
    report["telemetry_expected"] = True
    report["telemetry_complete"] = "dropout_expected"
    report["telemetry_stale_channels"] = []
    report["telemetry_missing_channels"] = []
    report["telemetry_dropout_breakpoint_sim_s"] = dropout_record.get("sim_s")
    report["freeze"] = False
    report["crash"] = False
    ack = report.get("ack_timeout", {})
    report["ack_timeout"] = {"count": 0, "trajectory_ids": [],
                             "recovered_count": ack.get("recovered_count", 0),
                             "recovered_trajectory_ids": list(ack.get("recovered_trajectory_ids", [])),
                             "threshold_s": ack.get("threshold_s")}
    return report


def telemetry_channel_contract(require_command_channels, completion_observed):
    """Return continuous and startup-presence telemetry channels for one UAV.

    Frontier markers establish planner/topic wiring at startup, but they are emitted
    only when the planner has visualizable frontier state.  They are therefore not a
    periodic health heartbeat during WAIT_TRIGGER or no-coverable-frontier periods.
    """
    continuous = ["odometry", "cloud", "health"]
    # Occupancy is a full-map coverage snapshot, not a 5 s health heartbeat.
    presence = ["occupancy"] + ([] if completion_observed else ["frontier"])
    if require_command_channels and not completion_observed:
        # A B-spline is an event that starts execution; PositionCommand and ACK
        # remain the live execution/transport heartbeats.
        continuous.extend(("pos_cmd", "ack"))
        presence.append("trajectory")
    return continuous, presence


def commit_occupancy_snapshot(state, captured, voxels, processed_wall_s):
    """Commit a parsed captured frame without discarding a newer pending frame."""
    _message, stamp = captured
    with state.lock:
        state.note_sample("occupancy")
        state.coverage_voxels.update(voxels)
        state.occupancy_processed += 1
        state.occupancy_processed_wall_s = processed_wall_s
        state.occupancy_processed_sim_s = stamp
        if state.pending_occupancy is captured:
            state.pending_occupancy = None


class VehicleState:
    def __init__(self, spec):
        self.spec = spec
        self.lock = threading.Lock()
        self.samples = {key: 0 for key in (
            "odometry", "cloud", "frontier", "trajectory", "pos_cmd", "ack", "health",
            "occupancy")}
        self.position = None
        self.first_position = None
        self.last_motion_wall_s = None
        self.path_length_m = 0.0
        self.ack_ids = []
        self.pending_commands = {}
        self.ack_timeout_ids = set()
        self.ack_recovered_ids = set()
        self.command_seen = False
        self.last_command_position = None
        self.last_command_wall_s = None
        self.coverage_voxels = set()
        self.occupancy_received = 0
        self.occupancy_processed = 0
        self.occupancy_coalesced = 0
        self.occupancy_callback_wall_s = None
        self.occupancy_processed_wall_s = None
        self.occupancy_processed_sim_s = None
        self.occupancy_callback_duration_s = []
        self.occupancy_processing_duration_s = []
        self.pending_occupancy = None
        self.contacts = {"ground": 0, "obstacle": 0, "inter_uav": 0}
        self.crash = False
        self.airborne = False
        self.last_sample_wall_s = {key: None for key in self.samples}
        self.completion = {"observed": False, "source": "/rosout",
                           "marker": "finish exploration.", "wall_s": None}

    def note_sample(self, key):
        self.samples[key] += 1
        self.last_sample_wall_s[key] = time.monotonic()

    def update_position(self, xyz):
        now = time.monotonic()
        with self.lock:
            self.note_sample("odometry")
            if self.first_position is None:
                self.first_position = xyz
                self.last_motion_wall_s = now
            if self.position is not None:
                distance = math.dist(self.position, xyz)
                self.path_length_m += distance
                if distance >= 0.02:
                    self.last_motion_wall_s = now
            self.position = xyz
            if xyz[2] >= 1.0:
                self.airborne = True
            if self.airborne and xyz[2] < 0.35:
                self.crash = True

    def snapshot(self, freshness_s, require_command_channels, coverage_denominator,
                 ack_timeout_s, freshness_reference_wall_s=None,
                 require_freshness_reference=False):
        with self.lock:
            now = time.monotonic()
            for trajectory_id, sent_s in self.pending_commands.items():
                if now - sent_s >= ack_timeout_s:
                    self.ack_timeout_ids.add(trajectory_id)
            moved = self.path_length_m >= 0.25
            # Freeze is a *stalled* vehicle, not a vehicle holding a reached
            # goal: recent pos_cmd plus on-target position means the command
            # chain is alive and the vehicle has nowhere left to go.
            command_active = (self.last_command_wall_s is not None and
                              now - self.last_command_wall_s < 15.0)
            at_goal = (self.last_command_position is not None and
                       self.position is not None and
                       math.dist(self.position, self.last_command_position) < 0.5)
            hold_at_goal = command_active and at_goal
            frozen = bool(moved and not hold_at_goal and
                          self.last_motion_wall_s is not None and
                          now - self.last_motion_wall_s >= 15.0)
            continuous, presence = telemetry_channel_contract(
                require_command_channels, self.completion["observed"])
            if freshness_reference_wall_s is None and require_freshness_reference:
                stale = list(continuous)
            else:
                reference = now if freshness_reference_wall_s is None else freshness_reference_wall_s
                stale = [key for key in continuous if self.last_sample_wall_s[key] is None or
                         reference - self.last_sample_wall_s[key] > freshness_s]
            missing = [key for key in presence if self.samples[key] == 0]
            reference = now if freshness_reference_wall_s is None else freshness_reference_wall_s
            def age(value):
                return None if value is None else max(0.0, reference - value)
            return {
                "completion": dict(self.completion),
                "freeze": frozen,
                "hold_at_goal": hold_at_goal,
                "crash": self.crash,
                "contact": dict(self.contacts),
                "coverage": {
                    "available": self.samples["occupancy"] > 0,
                    "observed_voxels": len(self.coverage_voxels),
                    "denominator_voxels": coverage_denominator,
                    "ratio": (float(len(self.coverage_voxels)) / coverage_denominator
                              if self.samples["occupancy"] > 0 else None),
                    "missing_policy": "abort_after_startup_grace",
                    "received": self.occupancy_received,
                    "processed": self.occupancy_processed,
                    "coalesced": self.occupancy_coalesced,
                    "last_message_wall_s": self.occupancy_callback_wall_s,
                    "last_processed_wall_s": self.occupancy_processed_wall_s,
                    "last_processed_sim_s": self.occupancy_processed_sim_s,
                    "message_age_s": age(self.occupancy_callback_wall_s),
                    "processed_age_s": age(self.occupancy_processed_wall_s),
                    "callback_wall_duration_s": list(self.occupancy_callback_duration_s[-16:]),
                    "processing_wall_duration_s": list(self.occupancy_processing_duration_s[-16:]),
                },
                "telemetry": dict(self.samples),
                "telemetry_complete": not stale and not missing,
                "telemetry_stale_channels": stale,
                "telemetry_missing_channels": missing,
                "ack_timeout": {
                    "count": len(self.ack_timeout_ids),
                    "trajectory_ids": sorted(self.ack_timeout_ids),
                    "recovered_count": len(self.ack_recovered_ids),
                    "recovered_trajectory_ids": sorted(self.ack_recovered_ids),
                    "threshold_s": ack_timeout_s,
                },
                "ack_count": len(self.ack_ids),
                "last_ack_id": self.ack_ids[-1] if self.ack_ids else None,
                "path_length_m": self.path_length_m,
                "position": self.position,
            }


class Collector:
    def __init__(self, config, runroot):
        import rospy
        from gazebo_msgs.msg import ContactsState
        from mavros_msgs.msg import State
        from nav_msgs.msg import Odometry
        from quadrotor_msgs.msg import PositionCommand
        from rosgraph_msgs.msg import Clock
        from rosgraph_msgs.msg import Log
        from sensor_msgs.msg import PointCloud2
        from std_msgs.msg import UInt32
        from tf2_msgs.msg import TFMessage

        self.rospy = rospy
        self.config = config
        self.runroot = Path(runroot)
        self.states = {spec["name"]: VehicleState(spec)
                       for spec in config["vehicles"]}
        self.clock_samples = 0
        self.clock_last = None
        self.clock_monotonic = True
        self.minimum_inter_uav_distance = None
        self.fleet_contacts = 0
        self.task_state_samples = 0
        self.abort_reasons = []
        self.finalized = False
        self.started_wall_s = time.monotonic()
        self.safety = config["safety_contract"]
        self.contact_first_seen = {}
        self.contact_last_seen = {}
        self.topic_owners = None
        self.tf_parents = {spec["frames"]["child"]: set()
                           for spec in config["vehicles"]}
        self.tf_last_wall_s = {child: None for child in self.tf_parents}
        resolution = self.safety["metrics"]["voxel_resolution_m"]
        self.coverage_denominator = planner_box_voxels(
            config["environment"]["planner_box_min"],
            config["environment"]["planner_box_max"], resolution)
        self.occupancy_coalesce_sim_s = self.safety["metrics"]["coverage_coalesce_sim_s"]
        self._subs = []
        for spec in config["vehicles"]:
            state = self.states[spec["name"]]
            topics = spec["topics"]
            self._subs.extend([
                rospy.Subscriber(topics["registered_odom"], Odometry,
                                 self._odom_cb, (state,)),
                rospy.Subscriber(topics["registered_cloud"], PointCloud2,
                                 self._count_cb, (state, "cloud")),
                rospy.Subscriber(topics["frontier"], rospy.AnyMsg,
                                 self._count_cb, (state, "frontier")),
                rospy.Subscriber(topics["trajectory"], rospy.AnyMsg,
                                 self._count_cb, (state, "trajectory")),
                rospy.Subscriber(topics["pos_cmd"], PositionCommand,
                                 self._command_cb, state),
                rospy.Subscriber(topics["ack"], UInt32, self._ack_cb, state),
                rospy.Subscriber(topics["health"], State,
                                 self._count_cb, (state, "health")),
                rospy.Subscriber(topics["occupancy"], PointCloud2,
                                 self._occupancy_cb, state, queue_size=1),
            ])
        self._subs.append(rospy.Subscriber("/clock", Clock, self._clock_cb))
        self._subs.append(rospy.Subscriber("/rosout", Log, self._rosout_cb))
        self._subs.append(rospy.Subscriber("/tf", TFMessage, self._tf_cb))
        self._subs.append(rospy.Subscriber(
            config["fleet"]["contact_topic"], ContactsState, self._contact_cb))
        self._subs.append(rospy.Subscriber(
            config["fleet"]["task_state_topic"], rospy.AnyMsg, self._task_cb))
        self.timer = rospy.Timer(rospy.Duration(2.0), self._flush)
        self.expected_nodes = {"/two_uav_gt_mapper", "/two_uav_collector"} | {
            node for spec in config["vehicles"]
            for node in ("/px4_bridge_%s" % spec["racer_id"],
                         "/exploration_node_%s" % spec["racer_id"],
                         "/traj_server_%s" % spec["racer_id"])}
        self.seen_nodes = set()
        self.last_active_liveness = None
        self.last_active_report_wall_s = None
        self.dropout_record = None
        self.dropout_baseline = None
        self.expected_nodes_by_vehicle = {
            spec["name"]: {
                "/px4_bridge_%s" % spec["racer_id"],
                "/exploration_node_%s" % spec["racer_id"],
                "/traj_server_%s" % spec["racer_id"],
            } for spec in config["vehicles"]}
        self.tf_vehicle = {spec["frames"]["child"]: spec["name"]
                           for spec in config["vehicles"]}
        self.contact_alias_map = vehicle_alias_map(config)

    def _load_dropout_record(self):
        """Read the runner-authored fleet/dropout.json once and cache it.

        D4 strengthening: a record is authoritative only when it carries the
        vehicle plus the classification fields (mode, sim_s) that distinguish
        intentional_dropout from unexpected_loss/telemetry_missing.
        """
        if self.dropout_record is not None:
            return self.dropout_record
        path = self.runroot / "fleet" / "dropout.json"
        if not path.is_file():
            return None
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return None
        if not isinstance(record, dict) or not isinstance(record.get("vehicle"), str):
            return None
        if not isinstance(record.get("mode"), str) or not record["mode"]:
            return None
        sim_s = record.get("sim_s")
        if not isinstance(sim_s, (int, float)) or isinstance(sim_s, bool):
            return None
        self.dropout_record = record
        return record

    def _dropped_vehicle(self):
        record = self._load_dropout_record()
        return record.get("vehicle") if record else None

    def _is_dropped(self, name):
        return self._dropped_vehicle() == name

    def _vehicle_for_node(self, node_name):
        for spec in self.config["vehicles"]:
            if node_name in self.expected_nodes_by_vehicle[spec["name"]]:
                return spec["name"]
        return None

    def _capture_dropout_baseline(self):
        """Snapshot per-vehicle progress at the first report after the dropout."""
        if self.dropout_baseline is not None:
            return
        record = self._load_dropout_record()
        if record is None:
            return
        baseline = {"sim_s": record.get("sim_s"), "vehicles": {}}
        for name, state in self.states.items():
            with state.lock:
                baseline["vehicles"][name] = {
                    "coverage_voxels": len(state.coverage_voxels),
                    "path_length_m": state.path_length_m,
                    "ack": state.samples["ack"],
                    "pos_cmd": state.samples["pos_cmd"],
                    "odometry": state.samples["odometry"],
                }
        self.dropout_baseline = baseline

    def _count_cb(self, _message, args):
        state, key = args
        with state.lock:
            state.note_sample(key)

    def _odom_cb(self, message, args):
        state = args[0]
        point = message.pose.pose.position
        state.update_position((point.x, point.y, point.z))
        positions = [item.position for item in self.states.values()
                     if item.position is not None]
        for left, right in itertools.combinations(positions, 2):
            distance = math.dist(left, right)
            if self.minimum_inter_uav_distance is None:
                self.minimum_inter_uav_distance = distance
            else:
                self.minimum_inter_uav_distance = min(
                    self.minimum_inter_uav_distance, distance)

    def _ack_cb(self, message, state):
        with state.lock:
            state.note_sample("ack")
            trajectory_id = int(message.data)
            state.ack_ids.append(trajectory_id)
            sent_s = state.pending_commands.pop(trajectory_id, None)
            if (sent_s is not None and time.monotonic() - sent_s >=
                    self.safety["telemetry"]["command_ack_timeout_s"]):
                state.ack_timeout_ids.add(trajectory_id)
                state.ack_recovered_ids.add(trajectory_id)

    def _command_cb(self, message, state):
        with state.lock:
            state.note_sample("pos_cmd")
            state.command_seen = True
            state.pending_commands.setdefault(
                int(message.trajectory_id), time.monotonic())
            position = getattr(message, "position", None)
            if position is not None:
                state.last_command_position = (position.x, position.y, position.z)
            state.last_command_wall_s = time.monotonic()

    def _occupancy_cb(self, message, state):
        started = time.monotonic()
        stamp = message.header.stamp.to_sec() if message.header.stamp else None
        with state.lock:
            state.occupancy_received += 1
            if state.pending_occupancy is not None:
                state.occupancy_coalesced += 1
            state.pending_occupancy = (message, stamp)
            state.occupancy_callback_wall_s = started
            state.occupancy_callback_duration_s.append(time.monotonic() - started)

    def _process_occupancy_snapshots(self):
        from sensor_msgs import point_cloud2
        for state in self.states.values():
            with state.lock:
                pending = state.pending_occupancy
                previous_sim_s = state.occupancy_processed_sim_s
            if pending is None:
                continue
            message, stamp = pending
            if (stamp is not None and previous_sim_s is not None and
                    stamp - previous_sim_s < self.occupancy_coalesce_sim_s):
                continue
            started = time.monotonic()
            voxels = set()
            try:
                for index, point in enumerate(point_cloud2.read_points(
                        message, field_names=("x", "y", "z"), skip_nans=True)):
                    if index % 4 == 0:
                        voxels.add(tuple(int(math.floor(axis / 0.25)) for axis in point))
            except Exception as exc:
                self._abort("corrupted_telemetry:%s:%s" % (state.spec["name"], exc))
                continue
            processed_wall_s = time.monotonic()
            commit_occupancy_snapshot(state, pending, voxels, processed_wall_s)
            with state.lock:
                state.occupancy_processing_duration_s.append(processed_wall_s - started)

    def _clock_cb(self, message):
        value = message.clock.to_sec()
        if self.clock_last is not None and value < self.clock_last:
            self.clock_monotonic = False
            self._abort("corrupted_telemetry:non_monotonic_clock")
        self.clock_last = value
        self.clock_samples += 1

    def _rosout_cb(self, message):
        marker = self.safety["completion"]["marker"].lower()
        if marker not in message.msg.lower():
            return
        for state in self.states.values():
            expected = "/exploration_node_%s" % state.spec["racer_id"]
            if message.name == expected:
                with state.lock:
                    state.completion = {"observed": True, "source": "/rosout",
                                        "marker": self.safety["completion"]["marker"],
                                        "wall_s": time.monotonic()}

    def _tf_cb(self, message):
        expected = {spec["frames"]["child"]: spec["frames"]["parent"]
                    for spec in self.config["vehicles"]}
        for transform in message.transforms:
            child = transform.child_frame_id.lstrip("/")
            if child not in expected:
                continue
            parent = transform.header.frame_id.lstrip("/")
            self.tf_parents[child].add(parent)
            self.tf_last_wall_s[child] = time.monotonic()
            if parent != expected[child] or len(self.tf_parents[child]) > 1:
                self._abort("namespace_or_tf_cross_talk:%s" % child)

    def _contact_cb(self, message):
        for contact in message.states:
            category, involved = contact_category(
                contact.collision1_name, contact.collision2_name,
                alias_map=self.contact_alias_map)
            if not involved:
                continue
            # A contact between only dropped vehicles is expected dropout drift,
            # not a fleet fault; the surviving vehicles still abort normally.
            if all(self._is_dropped(name) for name in involved):
                continue
            key = (contact.collision1_name, contact.collision2_name)
            now = time.monotonic()
            persistence = self.safety["contact"]["persistence_threshold_s"]
            if now - self.contact_last_seen.get(key, now) > persistence:
                self.contact_first_seen[key] = now
            first_seen = self.contact_first_seen.setdefault(key, now)
            self.contact_last_seen[key] = now
            duration = now - first_seen
            force = contact.total_wrench.force
            force_n = math.sqrt(force.x ** 2 + force.y ** 2 + force.z ** 2)
            for name in involved:
                self.states[name].contacts[category] += 1
            self.fleet_contacts += 1
            policy = self.safety["contact"]
            if severe_contact(category, force_n, duration,
                              policy["force_threshold_n"],
                              policy["persistence_threshold_s"]):
                self._abort("severe_contact:%s" % category)

    def _task_cb(self, _message):
        self.task_state_samples += 1

    def _abort(self, reason):
        if reason not in self.abort_reasons:
            self.abort_reasons.append(reason)
            try:
                with open(self.runroot / "fleet" / "abort.request", "x",
                          encoding="utf-8") as stream:
                    stream.write(json.dumps(
                        {"reason": reason, "wall_time": time.time()}) + "\n")
            except FileExistsError:
                pass

    def _check_topic_owners(self):
        try:
            import rosgraph
            _publishers, _subscribers, _services = rosgraph.Master(
                "/two_uav_collector").getSystemState()
            owners = {topic: tuple(sorted(nodes)) for topic, nodes in _publishers}
        except Exception:
            self._abort("corrupted_telemetry:topic_owner_probe_failed")
            return
        dropped = self._dropped_vehicle()
        dropped_topics = set()
        if dropped is not None:
            for spec in self.config["vehicles"]:
                if spec["name"] == dropped:
                    dropped_topics = set(spec["topics"].values())
                    break
        required = sorted(topic for state in self.states.values()
                          for topic in state.spec["topics"].values())
        current = {topic: owners.get(topic, ()) for topic in required}
        # An intentional dropout kills the dropped UAV's publishers; those
        # topics are exempt from missing/owner/drift checks.
        for topic, nodes in current.items():
            if topic in dropped_topics:
                continue
            if not nodes:
                self._abort("corrupted_telemetry:topic_owner_missing")
            elif not exactly_one_topic_owner(nodes):
                self._abort("namespace_or_tf_cross_talk:topic_owner_cardinality:" + topic)
        if self.topic_owners is None:
            self.topic_owners = current
        elif current != self.topic_owners:
            # Ignore drift caused only by the dropped UAV's topics.
            relevant_current = {t: n for t, n in current.items()
                                if t not in dropped_topics}
            relevant_previous = {t: n for t, n in self.topic_owners.items()
                                 if t not in dropped_topics}
            if relevant_current != relevant_previous:
                self._abort("namespace_or_tf_cross_talk:topic_owner_drift")

    def _safety_watchdog(self):
        elapsed = time.monotonic() - self.started_wall_s
        telemetry = self.safety["telemetry"]
        dropped = self._dropped_vehicle()
        if elapsed >= telemetry["startup_grace_s"]:
            for name, state in self.states.items():
                if name == dropped:
                    # Intentional dropout: the break is expected, not a fault.
                    continue
                snapshot = state.snapshot(telemetry["freshness_s"],
                                          state.command_seen, self.coverage_denominator,
                                          telemetry["command_ack_timeout_s"])
                if (snapshot["telemetry_stale_channels"] or
                        snapshot["telemetry_missing_channels"]):
                    self._abort("corrupted_telemetry:%s:freshness" % name)
                if state.ack_timeout_ids:
                    self._abort("corrupted_telemetry:%s:ack_timeout" % name)
            for child, parents in self.tf_parents.items():
                vehicle_name = self.tf_vehicle.get(child)
                if vehicle_name == dropped:
                    continue
                last = self.tf_last_wall_s[child]
                if not parents or last is None:
                    self._abort("namespace_or_tf_cross_talk:missing_tf:%s" % child)
                elif time.monotonic() - last > telemetry["tf_freshness_s"]:
                    self._abort("namespace_or_tf_cross_talk:stale_tf:%s" % child)
            self._check_topic_owners()

    def report(self, active=True):
        if active:
            self._safety_watchdog()
        telemetry = self.safety["telemetry"]
        dropout_record = self._load_dropout_record()
        dropped_vehicle = dropout_record.get("vehicle") if dropout_record else None
        self._capture_dropout_baseline()
        if active:
            freshness_reference = time.monotonic()
            self.last_active_report_wall_s = freshness_reference
        else:
            # Final metrics describe the last active safety observation, not
            # callback/teardown latency after the stack has stopped.
            freshness_reference = self.last_active_report_wall_s
        vehicle_reports = {name: state.snapshot(
            telemetry["freshness_s"], state.command_seen, self.coverage_denominator,
            telemetry["command_ack_timeout_s"], freshness_reference,
            require_freshness_reference=not active)
                           for name, state in self.states.items()}
        maps = [state.coverage_voxels for state in self.states.values()]
        union = set().union(*maps)
        box = self.config["environment"]
        resolution = self.safety["metrics"]["voxel_resolution_m"]
        denominator = planner_box_voxels(box["planner_box_min"],
                                         box["planner_box_max"], resolution)
        if active:
            try:
                import rosnode
                live_nodes = set(rosnode.get_node_names())
            except Exception:
                live_nodes = set()
            liveness = liveness_state(self.expected_nodes, self.seen_nodes, live_nodes, True)
            self.seen_nodes = liveness["seen"]
            self.last_active_liveness = liveness
            if time.monotonic() - self.started_wall_s >= self.safety["telemetry"]["startup_grace_s"]:
                for node in liveness["process_death"]:
                    # The dropped UAV's nodes dying is the injected fault itself.
                    if self._vehicle_for_node(node) == dropped_vehicle:
                        continue
                    self._abort("process_death:" + node)
        else:
            liveness = self.last_active_liveness or liveness_state(
                self.expected_nodes, self.seen_nodes, set(), False)
        classifications = {}
        for name, report in vehicle_reports.items():
            classification = dropout_classification(
                name, dropout_record, liveness, report, active,
                vehicle_nodes=self.expected_nodes_by_vehicle.get(name))
            classifications[name] = classification
            report["dropout"] = classification == "intentional_dropout"
            report["dropout_classification"] = classification
            report["telemetry_expected"] = classification == "intentional_dropout"
            if classification == "intentional_dropout":
                apply_dropout_report(report, dropout_record)
            elif report["crash"]:
                self._abort("crash:" + name)
        continue_evidence = {}
        if self.dropout_baseline is None:
            for name in self.states:
                continue_evidence[name] = {"continued": None, "coverage_delta": None}
        else:
            for name, report in vehicle_reports.items():
                base = self.dropout_baseline["vehicles"].get(name)
                continue_evidence[name] = dropout_continue_evidence(
                    base, report, dropped=(name == dropped_vehicle))
        fleet_overlap, fleet_jaccard = pairwise_fleet_metrics(maps)
        fleet = {
            "fleet_coverage_voxels": len(union),
            "fleet_coverage_ratio": float(len(union)) / denominator,
            "coverage_denominator_voxels": denominator,
            "coverage_definition": self.safety["metrics"]["coverage_denominator"],
            "overlap_ratio": fleet_overlap,
            "minimum_inter_uav_distance_m": self.minimum_inter_uav_distance,
            "fleet_contact_count": self.fleet_contacts,
            "map_consistency_jaccard": fleet_jaccard,
            "task_allocation_state_samples": self.task_state_samples,
            "process_liveness": liveness["process_liveness"],
            "never_seen": liveness["never_seen"],
            "lost_after_seen": liveness["lost_after_seen"],
            "clock": {"samples": self.clock_samples, "last_sim_s": self.clock_last,
                      "monotonic": self.clock_monotonic},
            "telemetry_completeness": all(
                item["telemetry_complete"] for item in vehicle_reports.values()),
            "topic_owners": self.topic_owners,
            "tf_parents": {child: sorted(parents)
                           for child, parents in self.tf_parents.items()},
            "tf_last_wall_s": dict(self.tf_last_wall_s),
            "abort_reasons": list(self.abort_reasons),
        }
        if dropout_record is not None:
            fleet["dropout"] = dropout_record
            fleet["surviving_uavs_continue"] = {
                name: evidence["continued"] for name, evidence in continue_evidence.items()}
            fleet["post_dropout_coverage_delta"] = {
                name: evidence["coverage_delta"] for name, evidence in continue_evidence.items()}
        fleet["dropout_classifications"] = classifications
        return vehicle_reports, fleet

    def _flush(self, _event=None):
        self._process_occupancy_snapshots()
        vehicle_reports, fleet = self.report(active=True)
        for name, report in vehicle_reports.items():
            with open(self.runroot / name / "telemetry.jsonl", "a",
                      encoding="utf-8") as stream:
                stream.write(json.dumps(report, sort_keys=True) + "\n")
        with open(self.runroot / "fleet" / "telemetry.jsonl", "a",
                  encoding="utf-8") as stream:
            stream.write(json.dumps(fleet, sort_keys=True) + "\n")

    def finalize(self):
        if self.finalized:
            return
        self.finalized = True
        vehicle_reports, fleet = self.report(active=False)
        for name, report in vehicle_reports.items():
            with open(self.runroot / name / "metrics.json", "x",
                      encoding="utf-8") as stream:
                stream.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
        with open(self.runroot / "fleet" / "metrics.json", "x",
                  encoding="utf-8") as stream:
            stream.write(json.dumps(fleet, indent=2, sort_keys=True) + "\n")


def self_test():
    assert jaccard(set(), set()) == 0.0
    assert jaccard({1, 2}, {2, 3}) == 1.0 / 3.0
    assert overlap_ratio({1, 2}, {2, 3}) == 0.5
    assert planner_box_voxels([-1.0, -1.0, 0.0], [1.0, 1.0, 1.0], 0.5) == 32
    category, involved = contact_category("iris_0::base::collision",
                                          "ground_50x50::ground_collision")
    assert category == "ground" and involved == {"uav0"}
    assert not severe_contact(category, 100.0, 10.0, 8.0, 0.25)
    category, involved = contact_category("iris_0::base::collision",
                                          "building_ne::collision")
    assert category == "obstacle" and involved == {"uav0"}
    assert severe_contact(category, 8.0, 0.0, 8.0, 0.25)
    category, involved = contact_category("iris_0::base::collision",
                                          "iris_1::base::collision")
    assert category == "inter_uav" and involved == {"uav0", "uav1"}
    assert severe_contact(category, 0.1, 0.25, 8.0, 0.25)
    # D5: three-UAV alias map resolves uav2 / iris_2 and keeps 2-UAV tokens.
    three_alias = {"uav0": "uav0", "iris_0": "uav0",
                   "uav1": "uav1", "iris_1": "uav1",
                   "uav2": "uav2", "iris_2": "uav2"}
    category3, involved3 = contact_category("iris_1::base::collision",
                                            "iris_2::base::collision",
                                            alias_map=three_alias)
    assert category3 == "inter_uav" and involved3 == {"uav1", "uav2"}
    two_map = [{1, 2, 3}, {2, 3, 4}]
    assert pairwise_fleet_metrics(two_map) == (overlap_ratio(*two_map),
                                               jaccard(*two_map))
    three_map = [{1, 2, 3}, {2, 3, 4}, {4, 5, 6}]
    pairwise_overlap, pairwise_jaccard = pairwise_fleet_metrics(three_map)
    assert pairwise_overlap == min(overlap_ratio(a, b)
                                   for a, b in itertools.combinations(three_map, 2))
    assert pairwise_jaccard == min(jaccard(a, b)
                                   for a, b in itertools.combinations(three_map, 2))
    assert pairwise_fleet_metrics([]) == (0.0, 0.0)
    assert exactly_one_topic_owner(("/owner",))
    assert dropout_classification("uav0", {"vehicle": "uav0"}, {"lost_after_seen": []}, {}, True) == \
        "intentional_dropout"
    assert dropout_classification("uav1", None, {"lost_after_seen": ["/px4_bridge_2"]}, {}, True) == \
        "unexpected_loss"
    assert dropout_classification("uav1", None, {}, {"telemetry_missing_channels": ["frontier"]}, True) == \
        "telemetry_missing"
    assert dropout_classification("uav1", None, {}, {"telemetry_missing_channels": []}, False) == \
        "none"
    # D4: unexpected_loss is attributed to the vehicle whose *own* nodes died,
    # not fleet-wide (a dead px4_bridge_2 must not label uav0 unexpected_loss).
    uav0_nodes = {"/px4_bridge_1", "/exploration_node_1", "/traj_server_1"}
    uav1_nodes = {"/px4_bridge_2", "/exploration_node_2", "/traj_server_2"}
    lost_fleet = {"lost_after_seen": ["/px4_bridge_2", "/traj_server_2"]}
    assert dropout_classification("uav1", None, lost_fleet, {}, True,
                                  vehicle_nodes=uav1_nodes) == "unexpected_loss"
    assert dropout_classification("uav0", None, lost_fleet, {}, True,
                                  vehicle_nodes=uav0_nodes) == "none"
    assert dropout_classification("uav0", None, lost_fleet,
                                  {"telemetry_stale_channels": ["health"]}, True,
                                  vehicle_nodes=uav0_nodes) == "telemetry_missing"
    # D4: dropout_continue_evidence — survivor continues on coverage/telemetry/
    # path progress; the dropped vehicle is not a survivor.
    survivor_after = {"coverage": {"observed_voxels": 120}, "telemetry": {"ack": 10},
                      "path_length_m": 12.0}
    baseline = {"coverage_voxels": 100, "ack": 8, "pos_cmd": 8, "odometry": 8,
                "path_length_m": 10.0}
    evidence = dropout_continue_evidence(baseline, survivor_after)
    assert evidence == {"continued": True, "coverage_delta": 20}
    assert dropout_continue_evidence(baseline, survivor_after, dropped=True) == {
        "continued": False, "coverage_delta": None}
    no_progress = {"coverage": {"observed_voxels": 100}, "telemetry": {"ack": 8},
                   "path_length_m": 10.0}
    assert dropout_continue_evidence(baseline, no_progress) == {
        "continued": False, "coverage_delta": 0}
    assert dropout_continue_evidence(None, survivor_after) == {
        "continued": None, "coverage_delta": None}
    assert not exactly_one_topic_owner(("/owner_a", "/owner_b"))
    expected = {"/a", "/b"}
    first_live = liveness_state(expected, set(), {"/a"}, True)
    assert first_live["never_seen"] == ["/b"] and first_live["seen"] == {"/a"}
    active = liveness_state(expected, {"/a"}, {"/a"}, True)
    assert active["never_seen"] == ["/b"] and active["process_death"] == ["/b"]
    lost = liveness_state(expected, expected, {"/a"}, True)
    assert lost["lost_after_seen"] == ["/b"] and lost["process_death"] == ["/b"]
    teardown = liveness_state(expected, expected, set(), False)
    assert not teardown["process_death"] and teardown["lost_after_seen"] == ["/a", "/b"]
    spec = {"name": "uav0"}
    race_state = VehicleState(spec)
    # Deterministic captured-frame race: B arrives while A is parsed.  A must
    # establish startup presence/coverage and B must remain for the next cycle.
    captured_a = (object(), 1.0)
    pending_b = (object(), 3.0)
    race_state.pending_occupancy = captured_a
    race_state.occupancy_received = 1
    race_state.pending_occupancy = pending_b
    race_state.occupancy_received += 1
    race_state.occupancy_coalesced += 1
    commit_occupancy_snapshot(race_state, captured_a, {(1, 2, 3)}, 10.0)
    assert race_state.samples["occupancy"] == 1 and race_state.coverage_voxels == {(1, 2, 3)}
    assert race_state.pending_occupancy is pending_b
    commit_occupancy_snapshot(race_state, pending_b, {(4, 5, 6)}, 11.0)
    assert race_state.samples["occupancy"] == 2 and race_state.pending_occupancy is None
    assert race_state.occupancy_processed == 2 and race_state.occupancy_coalesced == 1
    state = VehicleState(spec)
    state.update_position((0.0, 0.0, 1.0))
    state.update_position((1.0, 0.0, 1.0))
    state.pending_commands[7] = time.monotonic() - 1.1
    report = state.snapshot(5.0, False, 32, 1.0)
    assert report["path_length_m"] == 1.0 and not report["crash"]
    assert report["ack_timeout"]["trajectory_ids"] == [7]
    assert not report["coverage"]["available"] and report["coverage"]["ratio"] is None
    now = time.monotonic()
    for key in ("odometry", "cloud", "health", "occupancy"):
        state.samples[key] = 1
        state.last_sample_wall_s[key] = now
    continuous, presence = telemetry_channel_contract(False, False)
    assert continuous == ["odometry", "cloud", "health"]
    assert presence == ["occupancy", "frontier"]
    missing_frontier = state.snapshot(5.0, False, 32, 1.0)
    assert not missing_frontier["telemetry_complete"]
    assert missing_frontier["telemetry_missing_channels"] == ["frontier"]
    state.samples["frontier"] = 1
    state.last_sample_wall_s["frontier"] = now - 60.0
    wait_trigger = state.snapshot(5.0, False, 32, 1.0)
    assert wait_trigger["telemetry_complete"]
    assert not wait_trigger["telemetry_stale_channels"]
    assert not wait_trigger["telemetry_missing_channels"]
    state.last_sample_wall_s["health"] = now - 60.0
    assert state.snapshot(5.0, False, 32, 1.0)["telemetry_stale_channels"] == ["health"]
    state.last_sample_wall_s["health"] = now
    command_missing = state.snapshot(5.0, True, 32, 1.0)
    assert set(command_missing["telemetry_stale_channels"]) == {"pos_cmd", "ack"}
    assert command_missing["telemetry_missing_channels"] == ["trajectory"]
    state.samples["trajectory"] = 1
    state.last_sample_wall_s["trajectory"] = now - 60.0
    for key in ("pos_cmd", "ack"):
        state.samples[key] = 1
        state.last_sample_wall_s[key] = now
    assert state.snapshot(5.0, True, 32, 1.0)["telemetry_complete"]
    state.last_sample_wall_s["pos_cmd"] = now - 60.0
    assert state.snapshot(5.0, True, 32, 1.0)["telemetry_stale_channels"] == ["pos_cmd"]
    state.last_sample_wall_s["pos_cmd"] = now
    state.last_sample_wall_s["ack"] = now - 60.0
    assert state.snapshot(5.0, True, 32, 1.0)["telemetry_stale_channels"] == ["ack"]
    state.last_sample_wall_s["ack"] = now
    state.completion["observed"] = True
    completed = state.snapshot(5.0, True, 32, 1.0)
    assert completed["telemetry_complete"]
    assert not completed["telemetry_stale_channels"]
    assert not completed["telemetry_missing_channels"]
    final_reference = now
    # Final metrics retain the last active reference even if teardown happens
    # much later; an active reference beyond 5 s still fails closed.
    final_report = state.snapshot(5.0, True, 32, 1.0, final_reference)
    assert final_report["telemetry_complete"]
    delayed_active_report = state.snapshot(5.0, True, 32, 1.0, final_reference + 5.1)
    assert "occupancy" not in delayed_active_report["telemetry_stale_channels"]
    state.pending_commands[9] = final_reference - 1.1
    assert 9 in state.snapshot(5.0, True, 32, 1.0, final_reference)["ack_timeout"]["trajectory_ids"]
    # ACK timeout remains tied to finalize's current wall time, not the older
    # active freshness reference.
    state.pending_commands[10] = time.monotonic()
    original_monotonic = time.monotonic
    try:
        time.monotonic = lambda: original_monotonic() + 1.1
        teardown_ack = state.snapshot(5.0, True, 32, 1.0, final_reference)
    finally:
        time.monotonic = original_monotonic
    assert 10 in teardown_ack["ack_timeout"]["trajectory_ids"]
    no_active_reference = state.snapshot(5.0, True, 32, 1.0, None, True)
    assert not no_active_reference["telemetry_complete"]
    assert "occupancy" not in no_active_reference["telemetry_stale_channels"]
    # Freeze is not a vehicle holding a reached goal with a live command chain.
    # RUN-20260822T173640Z: uav1 late-hover mislabelled freeze when pos_cmd was
    # still flowing and the vehicle was parked at its target.
    hold_state = VehicleState(spec)
    hold_state.update_position((0.0, 0.0, 1.0))
    hold_state.update_position((1.0, 0.0, 1.0))
    hold_state.last_motion_wall_s = time.monotonic() - 30.0  # not moving
    hold_state.last_command_position = (1.0, 0.0, 1.0)       # at target
    hold_state.last_command_wall_s = time.monotonic() - 2.0   # pos_cmd fresh
    hold_report = hold_state.snapshot(5.0, True, 32, 1.0)
    assert hold_report["freeze"] is False
    assert hold_report["hold_at_goal"] is True
    # Vehicle parked at a target but pos_cmd is stale: still a real freeze.
    stale_hold_state = VehicleState(spec)
    stale_hold_state.update_position((0.0, 0.0, 1.0))
    stale_hold_state.update_position((1.0, 0.0, 1.0))
    stale_hold_state.last_motion_wall_s = time.monotonic() - 30.0
    stale_hold_state.last_command_position = (1.0, 0.0, 1.0)
    stale_hold_state.last_command_wall_s = time.monotonic() - 30.0  # stale
    stale_hold_report = stale_hold_state.snapshot(5.0, True, 32, 1.0)
    assert stale_hold_report["freeze"] is True
    # Vehicle not at the commanded target with fresh pos_cmd: still frozen if
    # it has not moved (command chain active but progress stalled).
    stuck_state = VehicleState(spec)
    stuck_state.update_position((0.0, 0.0, 1.0))
    stuck_state.update_position((1.0, 0.0, 1.0))
    stuck_state.last_motion_wall_s = time.monotonic() - 30.0
    stuck_state.last_command_position = (10.0, 0.0, 1.0)     # far target
    stuck_state.last_command_wall_s = time.monotonic() - 2.0  # fresh
    stuck_report = stuck_state.snapshot(5.0, True, 32, 1.0)
    assert stuck_report["freeze"] is True
    assert stuck_report["hold_at_goal"] is False
    # apply_dropout_report overlays intentional-dropout semantics on a raw report.
    raw_report = {"crash": True, "freeze": True, "telemetry_complete": False,
                  "ack_timeout": {"count": 3, "trajectory_ids": [1, 2, 3],
                                  "recovered_count": 0, "recovered_trajectory_ids": [],
                                  "threshold_s": 1.0}}
    dropout_record = {"vehicle": "uav1", "mode": "control_chain", "sim_s": 60.0,
                      "pids": [123], "reason": "intentional_dropout"}
    dropped = apply_dropout_report(raw_report, dropout_record)
    assert dropped["dropout"] is True
    assert dropped["dropout_classification"] == "intentional_dropout"
    assert dropped["dropout_mode"] == "control_chain"
    assert dropped["dropout_sim_s"] == 60.0
    assert dropped["telemetry_expected"] is True
    assert dropped["telemetry_complete"] == "dropout_expected"
    assert dropped["freeze"] is False and dropped["crash"] is False
    assert dropped["ack_timeout"]["count"] == 0 and dropped["ack_timeout"]["trajectory_ids"] == []
    assert dropped["telemetry_dropout_breakpoint_sim_s"] == 60.0
    print("two_uav_collector self-test: PASS")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/2uav_static.yaml")
    parser.add_argument("--runroot")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.runroot:
        parser.error("--runroot is required")
    with open(args.config, encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    runroot = Path(args.runroot)
    for name in [spec["name"] for spec in config["vehicles"]] + ["fleet"]:
        (runroot / name).mkdir(parents=True, exist_ok=True)
    import rospy
    rospy.init_node("two_uav_collector", anonymous=False)
    collector = Collector(config, runroot)
    rospy.on_shutdown(collector.finalize)
    rospy.spin()


if __name__ == "__main__":
    main()
