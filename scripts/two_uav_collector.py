#!/usr/bin/env python3
"""Per-UAV and fleet telemetry collector for the 2-UAV smoke contract."""

import argparse
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


def vehicle_names(collision_name):
    name = collision_name.lower()
    found = set()
    if "uav0" in name or "iris_0" in name:
        found.add("uav0")
    if "uav1" in name or "iris_1" in name:
        found.add("uav1")
    return found


def contact_category(collision1, collision2):
    names = (collision1 + " " + collision2).lower()
    vehicles = vehicle_names(names)
    if len(vehicles) == 2:
        return "inter_uav", vehicles
    if not vehicles:
        return "unrelated", vehicles
    if "ground" in names or "plane" in names:
        return "ground", vehicles
    return "obstacle", vehicles


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


def telemetry_channel_contract(require_command_channels, completion_observed):
    """Return continuous and startup-presence telemetry channels for one UAV.

    Frontier markers establish planner/topic wiring at startup, but they are emitted
    only when the planner has visualizable frontier state.  They are therefore not a
    periodic health heartbeat during WAIT_TRIGGER or no-coverable-frontier periods.
    """
    continuous = ["odometry", "cloud", "health", "occupancy"]
    presence = [] if completion_observed else ["frontier"]
    if require_command_channels and not completion_observed:
        continuous.extend(("trajectory", "pos_cmd", "ack"))
    return continuous, presence


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
        self.coverage_voxels = set()
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
                 ack_timeout_s):
        with self.lock:
            now = time.monotonic()
            for trajectory_id, sent_s in self.pending_commands.items():
                if now - sent_s >= ack_timeout_s:
                    self.ack_timeout_ids.add(trajectory_id)
            moved = self.path_length_m >= 0.25
            frozen = bool(moved and self.last_motion_wall_s is not None and
                          now - self.last_motion_wall_s >= 15.0)
            continuous, presence = telemetry_channel_contract(
                require_command_channels, self.completion["observed"])
            stale = [key for key in continuous if self.last_sample_wall_s[key] is None or
                     now - self.last_sample_wall_s[key] > freshness_s]
            missing = [key for key in presence if self.samples[key] == 0]
            return {
                "completion": dict(self.completion),
                "freeze": frozen,
                "crash": self.crash,
                "contact": dict(self.contacts),
                "coverage": {
                    "available": self.samples["occupancy"] > 0,
                    "observed_voxels": len(self.coverage_voxels),
                    "denominator_voxels": coverage_denominator,
                    "ratio": (float(len(self.coverage_voxels)) / coverage_denominator
                              if self.samples["occupancy"] > 0 else None),
                    "missing_policy": "abort_after_startup_grace",
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
                                 self._occupancy_cb, state),
            ])
        self._subs.append(rospy.Subscriber("/clock", Clock, self._clock_cb))
        self._subs.append(rospy.Subscriber("/rosout", Log, self._rosout_cb))
        self._subs.append(rospy.Subscriber("/tf", TFMessage, self._tf_cb))
        self._subs.append(rospy.Subscriber(
            config["fleet"]["contact_topic"], ContactsState, self._contact_cb))
        self._subs.append(rospy.Subscriber(
            config["fleet"]["task_state_topic"], rospy.AnyMsg, self._task_cb))
        self.timer = rospy.Timer(rospy.Duration(2.0), self._flush)
        self.expected_nodes = {
            "/two_uav_gt_mapper", "/two_uav_collector",
            "/px4_bridge_1", "/px4_bridge_2",
            "/exploration_node_1", "/exploration_node_2",
            "/traj_server_1", "/traj_server_2",
        }
        self.seen_nodes = set()
        self.last_active_liveness = None

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
        if len(positions) == 2:
            distance = math.dist(positions[0], positions[1])
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

    def _occupancy_cb(self, message, state):
        from sensor_msgs import point_cloud2
        voxels = set()
        try:
            for index, point in enumerate(point_cloud2.read_points(
                    message, field_names=("x", "y", "z"), skip_nans=True)):
                if index % 4 == 0:
                    voxels.add(tuple(int(math.floor(axis / 0.25)) for axis in point))
        except Exception as exc:
            self._abort("corrupted_telemetry:%s:%s" % (state.spec["name"], exc))
            return
        with state.lock:
            state.note_sample("occupancy")
            state.coverage_voxels.update(voxels)

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
            category, involved = contact_category(contact.collision1_name,
                                                  contact.collision2_name)
            if not involved:
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
        required = sorted(topic for state in self.states.values()
                          for topic in state.spec["topics"].values())
        current = {topic: owners.get(topic, ()) for topic in required}
        if any(not nodes for nodes in current.values()):
            self._abort("corrupted_telemetry:topic_owner_missing")
        for topic, nodes in current.items():
            if nodes and not exactly_one_topic_owner(nodes):
                self._abort("namespace_or_tf_cross_talk:topic_owner_cardinality:" + topic)
        if self.topic_owners is None:
            self.topic_owners = current
        elif current != self.topic_owners:
            self._abort("namespace_or_tf_cross_talk:topic_owner_drift")

    def _safety_watchdog(self):
        elapsed = time.monotonic() - self.started_wall_s
        telemetry = self.safety["telemetry"]
        if elapsed >= telemetry["startup_grace_s"]:
            for name, state in self.states.items():
                snapshot = state.snapshot(telemetry["freshness_s"],
                                          state.command_seen, self.coverage_denominator,
                                          telemetry["command_ack_timeout_s"])
                if (snapshot["telemetry_stale_channels"] or
                        snapshot["telemetry_missing_channels"]):
                    self._abort("corrupted_telemetry:%s:freshness" % name)
                if state.ack_timeout_ids:
                    self._abort("corrupted_telemetry:%s:ack_timeout" % name)
            for child, parents in self.tf_parents.items():
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
        vehicle_reports = {name: state.snapshot(
            telemetry["freshness_s"], state.command_seen, self.coverage_denominator,
            telemetry["command_ack_timeout_s"])
                           for name, state in self.states.items()}
        maps = [state.coverage_voxels for state in self.states.values()]
        union = maps[0] | maps[1]
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
                    self._abort("process_death:" + node)
        else:
            liveness = self.last_active_liveness or liveness_state(
                self.expected_nodes, self.seen_nodes, set(), False)
        for name, report in vehicle_reports.items():
            if report["crash"]:
                self._abort("crash:" + name)
        fleet = {
            "fleet_coverage_voxels": len(union),
            "fleet_coverage_ratio": float(len(union)) / denominator,
            "coverage_denominator_voxels": denominator,
            "coverage_definition": self.safety["metrics"]["coverage_denominator"],
            "overlap_ratio": overlap_ratio(maps[0], maps[1]),
            "minimum_inter_uav_distance_m": self.minimum_inter_uav_distance,
            "fleet_contact_count": self.fleet_contacts,
            "map_consistency_jaccard": jaccard(maps[0], maps[1]),
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
        return vehicle_reports, fleet

    def _flush(self, _event=None):
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
    assert exactly_one_topic_owner(("/owner",))
    assert not exactly_one_topic_owner(("/owner_a", "/owner_b"))
    assert not exactly_one_topic_owner(())
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
    assert continuous == ["odometry", "cloud", "health", "occupancy"]
    assert presence == ["frontier"]
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
    active_channels = state.snapshot(5.0, True, 32, 1.0)["telemetry_stale_channels"]
    assert set(active_channels) == {"trajectory", "pos_cmd", "ack"}
    for key in ("trajectory", "pos_cmd", "ack"):
        state.samples[key] = 1
        state.last_sample_wall_s[key] = now
    assert state.snapshot(5.0, True, 32, 1.0)["telemetry_complete"]
    state.completion["observed"] = True
    completed = state.snapshot(5.0, True, 32, 1.0)
    assert completed["telemetry_complete"]
    assert not completed["telemetry_stale_channels"]
    assert not completed["telemetry_missing_channels"]
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
    for name in ("uav0", "uav1", "fleet"):
        (runroot / name).mkdir(parents=True, exist_ok=True)
    import rospy
    rospy.init_node("two_uav_collector", anonymous=False)
    collector = Collector(config, runroot)
    rospy.on_shutdown(collector.finalize)
    rospy.spin()


if __name__ == "__main__":
    main()
