#!/usr/bin/env python3
"""Approval-gated lifecycle runner for the single allowed 2-UAV manifest."""

import argparse
from contextlib import contextmanager
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlparse

import yaml

from two_uav_preflight import live_checks, static_checks


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/2uav_static.yaml"
SOURCE_HASHES = ROOT / "config/2uav_source_hashes.sha256"
APPROVAL_CONTRACT = ROOT / "config/2uav_approval_contract.yaml"
APPROVAL_PACKAGE = ROOT / "state/2uav_approval.yaml"
APPROVAL_CONSUMPTIONS = ROOT / "results" / "approval-consumption"
ACTIVE = Path("/tmp/swarmlio_multi_2uav_active.json")
WORKSPACES = (
    (Path("/home/houslakers/swarm_ws/devel"), Path("/home/houslakers/swarm_ws/src")),
    (Path("/home/houslakers/racer_ws/devel"), Path("/home/houslakers/racer_ws/src")),
)
NODE_PROBE_TIMEOUT_S = 3
NODE_PROBE_ATTEMPTS = 2
NODE_PROBE_BACKOFF_S = 0.25
FRONTIER_INIT_SIM_BUDGET_S = 20.0
FRONTIER_INIT_WALL_HARD_CAP_S = 600.0
FRONTIER_CLOCK_STALL_WALL_S = 60.0
TEARDOWN_TERM_GRACE_S = 2.0
RESOURCE_SAMPLE_WALL_S = 1.0
RESOURCE_PROFILERS = {}
GIB = 1024 ** 3


def system_capacity(meminfo_path=Path("/proc/meminfo"), vmstat_path=Path("/proc/vmstat"),
                    loadavg=os.getloadavg):
    try:
        memory = {line.split()[0].rstrip(":"): int(line.split()[1]) * 1024
                  for line in Path(meminfo_path).read_text().splitlines()
                  if line.startswith("MemAvailable:")}
        vmstat = {line.split()[0]: int(line.split()[1])
                  for line in Path(vmstat_path).read_text().splitlines()
                  if line.startswith(("pswpin ", "pswpout "))}
        return {"mem_available_bytes": memory["MemAvailable"], "load1": float(loadavg()[0]),
                "swap_in": vmstat.get("pswpin", 0), "swap_out": vmstat.get("pswpout", 0)}
    except (OSError, ValueError, KeyError, IndexError):
        return None


SWAP_DELTA_ALLOWED_PAGES = 200000


def capacity_gate(facts, phase, baseline=None):
    if not isinstance(facts, dict):
        return False, "resource evidence missing"
    minimum = 8 * GIB if phase == "startup" else 3 * GIB
    if facts["mem_available_bytes"] < minimum:
        return False, "MemAvailable below %d GiB" % (minimum // GIB)
    if phase == "startup" and facts["load1"] >= 10.0:
        return False, "load1 >= 10"
    if phase != "startup":
        if not isinstance(baseline, dict):
            return False, "swap baseline missing"
        swap_in_delta = facts["swap_in"] - baseline["swap_in"]
        swap_out_delta = facts["swap_out"] - baseline["swap_out"]
        if swap_in_delta > SWAP_DELTA_ALLOWED_PAGES or swap_out_delta > SWAP_DELTA_ALLOWED_PAGES:
            return False, "swap activity exceeds allowed delta"
    return True, "resource capacity complete"


class ResourceProfiler:
    """Low-overhead /proc sampler; evidence failure never affects lifecycle control."""
    def __init__(self, runroot, processes, interval_s=RESOURCE_SAMPLE_WALL_S,
                 monotonic=time.monotonic, proc_root=Path("/proc"), clk_tck=None):
        self.runroot = Path(runroot)
        # start_stack mutates this mapping as roles are spawned; retain it so the
        # startup/readiness profile includes each role as soon as it exists.
        self.processes = processes
        self.interval_s = interval_s
        self.monotonic = monotonic
        self.proc_root = Path(proc_root)
        self.clk_tck = int(clk_tck if clk_tck is not None else os.sysconf("SC_CLK_TCK"))
        self.last_wall_s = None
        self.last_cpu = {}
        self.last_sim_s = None

    def sample(self, sim_s=None):
        now = self.monotonic()
        if self.last_wall_s is not None and now - self.last_wall_s < self.interval_s:
            return None
        wall_delta_s = None if self.last_wall_s is None else now - self.last_wall_s
        self.last_wall_s = now
        roles = {}
        snapshot = proc_snapshot(self.proc_root)
        for role, spec in self.processes.items():
            root_pid = int(spec["pid"])
            if root_pid not in snapshot:
                roles[role] = {"pid": root_pid, "evidence_missing": True}
                continue
            target_pids = sorted(descendant_closure({root_pid}, snapshot))
            cpu = rss_kb = threads = 0
            missing = []
            for pid in target_pids:
                try:
                    stat = (self.proc_root / str(pid) / "stat").read_text().split()
                    status = (self.proc_root / str(pid) / "status").read_text().splitlines()
                    cpu += int(stat[13]) + int(stat[14])
                    rss_kb += next(int(line.split()[1]) for line in status
                                   if line.startswith("VmRSS:"))
                    threads += next(int(line.split()[1]) for line in status
                                    if line.startswith("Threads:"))
                except (OSError, ValueError, StopIteration, IndexError):
                    missing.append(pid)
            previous = self.last_cpu.get(role)
            roles[role] = {"pid": root_pid, "pids": target_pids,
                           "cpu_ticks": cpu,
                           "cpu_delta_ticks": None if previous is None else cpu - previous,
                           "rss_kb": rss_kb, "threads": threads}
            if roles[role]["cpu_delta_ticks"] is not None and wall_delta_s and wall_delta_s > 0:
                roles[role]["cpu_cores"] = (roles[role]["cpu_delta_ticks"] /
                                              float(self.clk_tck * wall_delta_s))
            else:
                roles[role]["cpu_cores"] = None
            if missing:
                roles[role]["evidence_missing_pids"] = missing
            self.last_cpu[role] = cpu
        try:
            load = os.getloadavg()
            memory = {line.split()[0].rstrip(":"): int(line.split()[1])
                      for line in Path("/proc/meminfo").read_text().splitlines()
                      if line.startswith(("MemTotal:", "MemAvailable:"))}
            if isinstance(sim_s, (int, float)) and not isinstance(sim_s, bool):
                sim_s = float(sim_s)
            else:
                sim_s = None
            rt_factor = None
            if (sim_s is not None and self.last_sim_s is not None and wall_delta_s and
                    wall_delta_s > 0 and sim_s >= self.last_sim_s):
                rt_factor = (sim_s - self.last_sim_s) / wall_delta_s
            if sim_s is not None:
                self.last_sim_s = sim_s
            record = {"wall_monotonic_s": now, "wall_delta_s": wall_delta_s,
                      "sim_s": sim_s, "sim_evidence_missing": sim_s is None,
                      "rt_factor": rt_factor, "clk_tck": self.clk_tck, "roles": roles,
                      "system": {"loadavg": load, "memory_kb": memory}}
            with open(self.runroot / "resource_usage.jsonl", "a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, sort_keys=True) + "\n")
            return record
        except OSError:
            return None


def resource_profiler(runroot, processes=None):
    key = str(runroot)
    if key not in RESOURCE_PROFILERS and processes is not None:
        RESOURCE_PROFILERS[key] = ResourceProfiler(runroot, processes)
    return RESOURCE_PROFILERS.get(key)


def resource_usage_summary(runroot):
    path = Path(runroot) / "resource_usage.jsonl"
    if not path.is_file():
        return {"available": False}
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    values = {}
    cpu = {}
    rt = []
    for record in records:
        for role, fact in record.get("roles", {}).items():
            if "rss_kb" in fact:
                values.setdefault(role, []).append(fact["rss_kb"])
            if fact.get("cpu_delta_ticks") is not None:
                cpu.setdefault(role, []).append(fact["cpu_delta_ticks"])
            if fact.get("cpu_cores") is not None:
                cpu.setdefault(role + "_cores", []).append(fact["cpu_cores"])
        if record.get("rt_factor") is not None:
            rt.append(record["rt_factor"])
    def percentile(items, fraction):
        ordered = sorted(items)
        return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * fraction + 0.999999))]
    roles = {}
    for role, items in values.items():
        roles[role] = {"p50_rss_kb": percentile(items, 0.50),
                       "p95_rss_kb": percentile(items, 0.95),
                       "max_rss_kb": max(items),
                       "cpu_delta_ticks": sum(cpu.get(role, []))}
        cores = cpu.get(role + "_cores", [])
        if cores:
            roles[role].update({"p50_cpu_cores": percentile(cores, 0.50),
                                "p95_cpu_cores": percentile(cores, 0.95),
                                "max_cpu_cores": max(cores)})
    top_consumers = sorted(roles, key=lambda role: roles[role]["cpu_delta_ticks"], reverse=True)
    return {"available": True, "samples": len(records), "roles": roles,
            "top_cpu_consumers": top_consumers,
            "valid_rt_samples": len(rt),
            "rt_factor": (None if not rt else {"p50": percentile(rt, 0.50),
                                                 "p95": percentile(rt, 0.95),
                                                 "max": max(rt)})}


def recorded_sim_time(runroot):
    """Read collector's existing telemetry evidence; never invoke a CLI sampler."""
    try:
        line = (Path(runroot) / "fleet" / "telemetry.jsonl").read_text(
            encoding="utf-8").splitlines()[-1]
        value = json.loads(line).get("clock", {}).get("last_sim_s")
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
    except (OSError, ValueError, json.JSONDecodeError, IndexError):
        return None


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_yaml(path):
    with open(path, encoding="utf-8") as stream:
        return yaml.safe_load(stream)


DROPOUT_MODES = ("control_chain", "communication", "node_level")


def parse_dropout_config(manifest):
    """Parse the manifest `dropout:` section (D1). Fail-fast on any invalid field.

    Returns None when the section is absent so non-dropout runs behave unchanged.
    """
    dropout = manifest.get("dropout")
    if dropout is None:
        return None
    required = ("enabled", "vehicle", "mode", "trigger_sim_s", "cleanup_policy", "record")
    missing = [key for key in required if key not in dropout]
    if missing:
        raise RuntimeError("dropout config missing required field(s): %s" % ", ".join(missing))
    if not isinstance(dropout["enabled"], bool):
        raise RuntimeError("dropout.enabled must be a boolean")
    if not isinstance(dropout["trigger_sim_s"], (int, float)) or dropout["trigger_sim_s"] <= 0:
        raise RuntimeError("dropout.trigger_sim_s must be a positive number")
    if dropout["mode"] not in DROPOUT_MODES:
        raise RuntimeError("dropout.mode %r not in %s" % (dropout["mode"], DROPOUT_MODES))
    if not isinstance(dropout["record"], str) or not dropout["record"]:
        raise RuntimeError("dropout.record must be a non-empty relative path")
    vehicle_names = {vehicle["name"] for vehicle in load_yaml(CONFIG)["vehicles"]}
    if dropout["vehicle"] not in vehicle_names:
        raise RuntimeError("dropout.vehicle %r not in %s" % (
            dropout["vehicle"], sorted(vehicle_names)))
    return dropout


def dropout_target_nodes(config, dropout_config):
    """Pure mapping of dropout vehicle+mode to the ROS nodes that get killed.

    D0 semantics (workflow 0.2): control_chain breaks exploration/traj so the
    vehicle can still fly/hover, which requires keeping px4_bridge (the pos_cmd
    relay) alive; communication breaks only the bridge heartbeat; node_level
    kills exploration + bridge + traj as the closest to real loss-of-link.
    """
    vehicle = next(item for item in config["vehicles"]
                   if item["name"] == dropout_config["vehicle"])
    racer_id = vehicle["racer_id"]
    control = ["/exploration_node_%d" % racer_id,
               "/traj_server_%d" % racer_id]
    node_level = ["/px4_bridge_%d" % racer_id] + list(control)
    return {"control_chain": list(control),
            "node_level": node_level,
            "communication": ["/px4_bridge_%d" % racer_id]}[dropout_config["mode"]]


def dropout_due(dropout_config, elapsed_sim_s, triggered):
    """Pure one-shot dropout trigger decision (D1)."""
    if not dropout_config or not dropout_config.get("enabled") or triggered:
        return False
    return elapsed_sim_s >= dropout_config["trigger_sim_s"]


def rosnode_pid(runroot, node_name):
    """Best-effort PID of a ROS node; None when the node is unknown."""
    argv, environment = ros_command_spec(
        runroot, "source /opt/ros/noetic/setup.bash; rosnode info %s" % shlex.quote(node_name))
    try:
        result = subprocess.run(argv, env=environment, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, timeout=5)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("Pid:"):
            try:
                return int(stripped.split(":", 1)[1].strip())
            except ValueError:
                return None
    return None


def rosnode_kill(runroot, node_name):
    """White-list rosnode kill used by the runner; never a bare shell kill."""
    argv, environment = ros_command_spec(
        runroot, "source /opt/ros/noetic/setup.bash; rosnode kill %s" % shlex.quote(node_name))
    try:
        result = subprocess.run(argv, env=environment, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, timeout=5)
    except (subprocess.TimeoutExpired, OSError):
        return False
    return result.returncode == 0


def execute_dropout(runroot, dropout_config, config, sim_s=None,
                    pid_probe=None, killer=None, sim_probe=recorded_sim_time,
                    monotonic=time.monotonic):
    """Execute the D1 white-list fault injection and record fleet/dropout.json.

    The killed nodes are descendants of the tracked bridges/racer process trees,
    so stop_active's existing descendant closure reclaims any residue.
    """
    runroot = Path(runroot)
    pid_probe = pid_probe or (lambda node: rosnode_pid(runroot, node))
    killer = killer or (lambda node: rosnode_kill(runroot, node))
    targets = dropout_target_nodes(config, dropout_config)
    pids = {}
    killed = []
    missing = []
    for node_name in targets:
        pid = pid_probe(node_name)
        if pid is not None:
            pids[node_name] = pid
        if killer(node_name):
            killed.append(node_name)
        else:
            missing.append(node_name)
    record = {
        "vehicle": dropout_config["vehicle"],
        "mode": dropout_config["mode"],
        "trigger_sim_s": dropout_config["trigger_sim_s"],
        "sim_s": (float(sim_s) if isinstance(sim_s, (int, float)) and not isinstance(sim_s, bool)
                  else sim_probe(runroot)),
        "wall_s": monotonic(),
        "pids": pids,
        "killed_nodes": killed,
        "missing_nodes": missing,
        "cleanup_policy": dropout_config["cleanup_policy"],
        "record": dropout_config["record"],
        "reason": "intentional_dropout",
    }
    record_path = runroot / "fleet" / "dropout.json"
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def verify_source_hashes():
    if not SOURCE_HASHES.is_file():
        raise RuntimeError("missing config/2uav_source_hashes.sha256")
    failures = []
    for raw_line in SOURCE_HASHES.read_text(encoding="utf-8").splitlines():
        if not raw_line or raw_line.startswith("#"):
            continue
        expected, relative = raw_line.split(None, 1)
        relative = relative.lstrip(" *")
        path = ROOT / relative
        actual = sha256(path) if path.is_file() else "missing"
        if actual != expected:
            failures.append("%s expected=%s actual=%s" % (relative, expected, actual))
    if failures:
        raise RuntimeError("source hash mismatch: " + "; ".join(failures))


def validate_approval_package(action, manifest, approval, manifest_hash, source_hash,
                              contract):
    expected_stage = "preflight" if action == "preflight" else "smoke"
    if manifest.get("approval_status") != "blocked_pending_verified_launch_and_preflight":
        raise RuntimeError("manifest approval_status must remain blocked candidate")
    if approval.get("schema_version") != 1:
        raise RuntimeError("approval package schema_version must be 1")
    if approval.get("stage") != expected_stage or approval.get("approved") is not True:
        raise RuntimeError("approval package does not approve %s stage" % expected_stage)
    if action not in approval.get("allowed_actions", []):
        raise RuntimeError("approval package does not allow action %s" % action)
    if approval.get("manifest_sha256") != manifest_hash:
        raise RuntimeError("approval package manifest hash drift")
    if approval.get("source_hash_manifest_sha256") != source_hash:
        raise RuntimeError("approval package source hash manifest drift")
    if approval.get("issued_by") != contract.get("issued_by_must_be"):
        raise RuntimeError("approval package issuer is not Sol")
    if approval.get("max_uses") != contract.get("max_uses"):
        raise RuntimeError("approval package max_uses is not contract-bound")


def approval_guard(action, manifest_path):
    manifest = load_yaml(manifest_path)
    if not APPROVAL_CONTRACT.is_file():
        raise RuntimeError("missing config/2uav_approval_contract.yaml")
    contract = load_yaml(APPROVAL_CONTRACT)
    if Path(contract.get("approval_package", "")).as_posix() != "state/2uav_approval.yaml":
        raise RuntimeError("approval contract package path is not fixed")
    if not APPROVAL_PACKAGE.is_file():
        raise RuntimeError("missing immutable state/2uav_approval.yaml")
    verify_source_hashes()
    package_bytes = APPROVAL_PACKAGE.read_bytes()
    validate_approval_package(action, manifest, yaml.safe_load(package_bytes),
                              sha256(manifest_path), sha256(SOURCE_HASHES), contract)
    digest = hashlib.sha256(package_bytes).hexdigest()
    receipt = APPROVAL_CONSUMPTIONS / (digest + ".json")
    if receipt.exists():
        raise RuntimeError("approval package has already been consumed")
    return manifest, package_bytes, digest


def consume_approval(action, manifest_path, package_digest, runroot):
    APPROVAL_CONSUMPTIONS.mkdir(parents=True, exist_ok=True)
    receipt = APPROVAL_CONSUMPTIONS / (package_digest + ".json")
    payload = {"action": action, "manifest_sha256": sha256(manifest_path),
               "runroot": str(runroot), "consumed_utc": dt.datetime.now(
                   dt.timezone.utc).isoformat()}
    with open(receipt, "x", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def shell(command):
    return ["bash", "-lc", command]


def runroot_ros_environment(runroot):
    """Return the ROS state directories owned exclusively by *runroot*."""
    runroot = Path(runroot)
    return {
        "ROS_LOG_DIR": str(runroot / "logs" / "ros"),
        "ROS_HOME": str(runroot / "logs" / "ros-home"),
    }


def prepend_path(existing, entries):
    """Prepend deterministic, de-duplicated path entries."""
    values = [str(entry) for entry in entries]
    values.extend(item for item in existing.split(":") if item)
    return ":".join(dict.fromkeys(values))


def workspace_environment(inherited=None):
    """Compose both catkin workspaces without relying on setup.bash source order."""
    environment = dict(os.environ if inherited is None else inherited)
    devels = [devel for devel, _source in WORKSPACES]
    sources = [source for _devel, source in WORKSPACES]
    environment["ROS_PACKAGE_PATH"] = prepend_path(
        environment.get("ROS_PACKAGE_PATH", ""), sources)
    environment["CMAKE_PREFIX_PATH"] = prepend_path(
        environment.get("CMAKE_PREFIX_PATH", ""), devels)
    environment["PYTHONPATH"] = prepend_path(
        environment.get("PYTHONPATH", ""),
        [devel / "lib/python3/dist-packages" for devel in devels] +
        [Path("/opt/ros/noetic/lib/python3/dist-packages")])
    environment["LD_LIBRARY_PATH"] = prepend_path(
        environment.get("LD_LIBRARY_PATH", ""), [devel / "lib" for devel in devels])
    environment["PATH"] = prepend_path(
        environment.get("PATH", ""), [devel / "bin" for devel in devels])
    environment["PKG_CONFIG_PATH"] = prepend_path(
        environment.get("PKG_CONFIG_PATH", ""), [devel / "lib/pkgconfig" for devel in devels])
    return environment


def workspace_environment_exports(runroot):
    environment = workspace_environment()
    environment.update(runroot_ros_environment(runroot))
    names = ("ROS_PACKAGE_PATH", "CMAKE_PREFIX_PATH", "PYTHONPATH", "LD_LIBRARY_PATH",
             "PATH", "PKG_CONFIG_PATH", "ROS_LOG_DIR", "ROS_HOME")
    return "".join("export %s=%s; " % (name, shlex.quote(environment[name]))
                   for name in names)


def prepare_runroot_ros_environment(runroot):
    """Create and record runroot-local ROS state before any child can start."""
    environment = runroot_ros_environment(runroot)
    for directory in environment.values():
        Path(directory).mkdir(parents=True, exist_ok=True)
    (Path(runroot) / "runtime_environment.json").write_text(
        json.dumps({"ros_environment": environment,
                    "workspace_environment": {name: workspace_environment().get(name, "")
                                              for name in ("ROS_PACKAGE_PATH", "CMAKE_PREFIX_PATH",
                                                           "PYTHONPATH", "LD_LIBRARY_PATH")}},
                   indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return environment


def ros_subprocess_environment(runroot, inherited=None):
    """Build a child environment that overrides any caller ROS log/home paths."""
    environment = workspace_environment(inherited)
    environment.update(runroot_ros_environment(runroot))
    environment.setdefault("ROS_MASTER_URI", "http://127.0.0.1:11311")
    return environment


def teardown_identity(runroot):
    environment = ros_subprocess_environment(runroot)
    return {name: environment[name] for name in ("ROS_LOG_DIR", "ROS_HOME", "ROS_MASTER_URI")}


@contextmanager
def runroot_ros_environment_scope(runroot):
    """Scope default inheritance for ROS helpers implemented outside this module."""
    environment = runroot_ros_environment(runroot)
    previous = {name: os.environ.get(name) for name in environment}
    os.environ.update(environment)
    try:
        yield environment
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def ros_command_spec(runroot, command):
    """Return the argv/environment pair for every short-lived ROS CLI child."""
    return shell(command), ros_subprocess_environment(runroot)


def active_ros_environment(active):
    """Rebuild the original runroot's child environment after ACTIVE recovery."""
    runroot = active.get("runroot")
    if not isinstance(runroot, str) or not runroot:
        raise RuntimeError("active lifecycle has no runroot")
    return ros_subprocess_environment(runroot)


def ros_environment_exports(runroot):
    environment = runroot_ros_environment(runroot)
    return "".join("export %s=%s; " % (name, shlex.quote(directory))
                   for name, directory in environment.items())


def ros_runtime_prefix(runroot):
    """Restore the composed workspaces after Noetic setup resets path variables."""
    return "source /opt/ros/noetic/setup.bash; " + workspace_environment_exports(runroot)


def process_specs(runroot):
    env_prefix = ros_runtime_prefix(runroot)
    gazebo_env = (
        env_prefix +
        "export GAZEBO_PLUGIN_PATH=${GAZEBO_PLUGIN_PATH:-}:/home/houslakers/swarm_ws/devel/lib; "
        "export GAZEBO_MODEL_PATH=${GAZEBO_MODEL_PATH:-}:/home/houslakers/swarm_ws/src; "
        "cd /home/houslakers/PX4-Autopilot; "
        "source Tools/simulation/gazebo-classic/setup_gazebo.bash "
        "/home/houslakers/PX4-Autopilot "
        "/home/houslakers/PX4-Autopilot/build/px4_sitl_default; "
        "export ROS_PACKAGE_PATH=${ROS_PACKAGE_PATH:-}:/home/houslakers/PX4-Autopilot:"
        "/home/houslakers/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic; ")
    return [
        ("gazebo", shell(gazebo_env + "exec roslaunch " +
                         str(ROOT / "launch/2uav_px4_sitl.launch"))),
        ("gt_mapper", shell(env_prefix + "exec python3 " +
                            str(ROOT / "scripts/two_uav_gt_mapper.py") +
                            " --config " + str(CONFIG))),
        ("bridges", shell(env_prefix + "exec roslaunch " +
                          str(ROOT / "launch/2uav_bridges.launch"))),
        ("racer", shell(env_prefix + "exec roslaunch " +
                        str(ROOT / "launch/2uav_racer.launch"))),
        ("collector", shell(env_prefix + "exec python3 " +
                            str(ROOT / "scripts/two_uav_collector.py") +
                            " --config " + str(CONFIG) + " --runroot " + str(runroot))),
    ]


def process_exit_reason(processes):
    """Return one deterministic failure for any process that has already exited."""
    for name in sorted(processes):
        code = processes[name].poll()
        if code is not None:
            return "readiness process exited: %s code=%s" % (name, code)
    return None


def node_probe_result(status, nodes=(), detail=""):
    """Construct a machine-distinguishable ROS node probe observation."""
    if status not in {"success", "timeout", "error"}:
        raise ValueError("invalid node probe status")
    return {"status": status, "nodes": set(nodes), "detail": detail}


def normalize_node_probe(observation):
    """Keep pure callers concise while runtime probes retain failure classes."""
    if isinstance(observation, (set, tuple, list)):
        return node_probe_result("success", observation)
    if not isinstance(observation, dict):
        return node_probe_result("error", detail="malformed result")
    try:
        return node_probe_result(observation["status"], observation.get("nodes", ()),
                                 str(observation.get("detail", "")))
    except (KeyError, ValueError, TypeError):
        return node_probe_result("error", detail="malformed result")


def readiness_state(processes, payload_seen, observed_nodes=(), required_nodes=(),
                    node_probe=None):
    """Pure short-poll decision used by payload and bridge readiness gates."""
    exited = process_exit_reason(processes)
    if exited:
        return "failed", exited
    if required_nodes:
        probe = normalize_node_probe(node_probe if node_probe is not None else observed_nodes)
        if probe["status"] != "success":
            detail = probe["detail"] or "no detail"
            return "waiting", "node probe %s: %s" % (probe["status"], detail)
        observed_nodes = probe["nodes"]
    missing_nodes = sorted(set(required_nodes) - set(observed_nodes))
    if missing_nodes:
        return "waiting", "missing nodes: " + ", ".join(missing_nodes)
    if not payload_seen:
        return "waiting", "no payload"
    return "ready", "ready"


def topic_payload_seen(runroot, topic):
    """One short ROS CLI probe; a registered-but-silent topic returns False."""
    argv, environment = ros_command_spec(
        runroot, "source /opt/ros/noetic/setup.bash; rostopic echo -n 1 --noarr " +
        shlex.quote(topic))
    try:
        result = subprocess.run(argv, env=environment, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, timeout=3)
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0 and bool(result.stdout.strip())


def ros_node_names(runroot):
    argv, environment = ros_command_spec(
        runroot, "source /opt/ros/noetic/setup.bash; rosnode list")
    last = None
    for attempt in range(1, NODE_PROBE_ATTEMPTS + 1):
        try:
            result = subprocess.run(argv, env=environment, text=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=NODE_PROBE_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            last = node_probe_result("timeout", detail="attempt %d/%d" % (
                attempt, NODE_PROBE_ATTEMPTS))
        else:
            if result.returncode == 0:
                return node_probe_result("success", result.stdout.splitlines())
            last = node_probe_result("error", detail="returncode %d" % result.returncode)
        if attempt < NODE_PROBE_ATTEMPTS:
            time.sleep(NODE_PROBE_BACKOFF_S)
    return last


def wait_readiness(runroot, label, timeout_s, processes, payload_probe, required_nodes=(),
                   node_probe=None, monotonic=time.monotonic, sleep=time.sleep,
                   profile_sample=None):
    """Poll payload/nodes and every already-started Popen in the same gate."""
    node_probe = node_probe or (lambda: ros_node_names(runroot))

    def sample():
        if profile_sample is not None:
            profile_sample()
        # Read nodes after payload: a bridge cannot pass on a pre-probe snapshot.
        payload_seen = payload_probe()
        probe = node_probe() if required_nodes else None
        return readiness_state(processes, payload_seen, required_nodes=required_nodes,
                               node_probe=probe)

    deadline = monotonic() + timeout_s
    detail = "not probed"
    while monotonic() < deadline:
        state, detail = sample()
        if state == "ready":
            return
        if state == "failed":
            raise RuntimeError(detail)
        sleep(0.25)
    state, detail = sample()
    if state == "ready":
        return
    if state == "failed":
        raise RuntimeError(detail)
    raise RuntimeError("readiness timeout: %s: %s" % (label, detail))


def wait_frontier_readiness(runroot, label, processes, payload_probe, required_nodes,
                            node_probe=None, sim_time_probe=None,
                            monotonic=time.monotonic, sleep=time.sleep, profile_sample=None):
    """Require frontier payload within a sim-time budget and wall-time hard cap."""
    node_probe = node_probe or (lambda: ros_node_names(runroot))
    sim_time_probe = sim_time_probe or (lambda: sim_time_s(runroot))
    started_wall = monotonic()
    first_sim = None
    last_sim = None
    last_advance_wall = started_wall
    detail = "not probed"
    while True:
        if profile_sample is not None:
            profile_sample()
        payload_seen = payload_probe()
        probe = node_probe()
        state, detail = readiness_state(processes, payload_seen,
                                        required_nodes=required_nodes,
                                        node_probe=probe)
        if state == "ready":
            return
        if state == "failed":
            raise RuntimeError(detail)
        now = monotonic()
        try:
            sim_now = sim_time_probe()
        except (OSError, subprocess.SubprocessError):
            sim_now = None
        if isinstance(sim_now, (int, float)) and not isinstance(sim_now, bool):
            sim_now = float(sim_now)
            if sim_now == sim_now and sim_now not in (float("inf"), float("-inf")):
                if first_sim is None:
                    first_sim = sim_now
                if last_sim is None or sim_now > last_sim:
                    last_advance_wall = now
                last_sim = sim_now
                if sim_now - first_sim >= FRONTIER_INIT_SIM_BUDGET_S:
                    raise RuntimeError("readiness timeout: %s: frontier sim budget exhausted" % label)
        if now - last_advance_wall >= FRONTIER_CLOCK_STALL_WALL_S:
            raise RuntimeError("readiness timeout: %s: clock stalled" % label)
        if now - started_wall >= FRONTIER_INIT_WALL_HARD_CAP_S:
            raise RuntimeError("readiness timeout: %s: wall hard cap" % label)
        sleep(0.25)


def workspace_probe_specs(runroot):
    """Generate probes under exactly the same prefix used by long-lived processes."""
    probes = (
        ("swarm_lio", "rospack find swarm_lio"),
        ("exploration_manager", "rospack find exploration_manager"),
        ("quadrotor_msgs", "python3 -c 'import quadrotor_msgs.msg'"),
    )
    prefix = ros_runtime_prefix(runroot)
    return [(name, command, *ros_command_spec(runroot, prefix + command))
            for name, command in probes]


def verify_workspace_environment(runroot):
    """Fail before stack startup unless both workspaces resolve required runtime symbols."""
    results = {}
    for name, command, argv, environment in workspace_probe_specs(runroot):
        completed = subprocess.run(argv, env=environment, text=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, timeout=20)
        results[name] = {"ok": completed.returncode == 0,
                         "command": command, "returncode": completed.returncode,
                         "stdout": completed.stdout.strip(),
                         "stderr": completed.stderr.strip()}
    (Path(runroot) / "workspace_environment_probe.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failed = [name for name, result in results.items() if not result["ok"]]
    if failed:
        raise RuntimeError("workspace environment probe failed: " + ", ".join(failed))


def make_runroot(kind, manifest_path, approval_bytes):
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    runroot = ROOT / "results" / ("RUN-%s-2uav-%s" % (stamp, kind))
    runroot.mkdir(parents=True, exist_ok=False)
    for name in ("uav0", "uav1", "fleet", "logs"):
        (runroot / name).mkdir()
    prepare_runroot_ros_environment(runroot)
    shutil.copy2(manifest_path, runroot / "manifest.yaml")
    shutil.copy2(CONFIG, runroot / "2uav_static.yaml")
    (runroot / "2uav_approval.yaml").write_bytes(approval_bytes)
    return runroot


def start_stack(runroot, manifest_path):
    startup_capacity = system_capacity()
    startup_ok, startup_detail = capacity_gate(startup_capacity, "startup")
    (Path(runroot) / "resource_capacity_startup.json").write_text(
        json.dumps({"facts": startup_capacity, "ok": startup_ok, "detail": startup_detail},
                   indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not startup_ok:
        raise RuntimeError("startup resource gate failed: " + startup_detail)
    checks, hashes = static_checks(CONFIG, manifest_path)
    report = {"passed": all(item["ok"] for item in checks),
              "checks": checks, "source_hashes": hashes}
    (runroot / "static_preflight.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not report["passed"]:
        raise RuntimeError("static preflight failed")
    verify_workspace_environment(runroot)
    specs = process_specs(runroot)
    (runroot / "process_specs.json").write_text(
        json.dumps({"processes": [{"name": name, "argv": argv}
                                    for name, argv in specs]},
                   indent=2, sort_keys=True) + "\n", encoding="utf-8")
    processes = {}
    live_processes = {}
    profiler = resource_profiler(runroot, processes)
    profile_sample = lambda: profiler.sample(recorded_sim_time(runroot))
    try:
        for name, argv in specs:
            log = open(runroot / "logs" / (name + ".log"), "wb")
            process = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True,
                                       env=ros_subprocess_environment(runroot))
            processes[name] = {"pid": process.pid, "argv": argv}
            live_processes[name] = process
            profile_sample()
            if name == "gazebo":
                wait_readiness(runroot, "clock", 120, live_processes,
                               lambda: topic_payload_seen(runroot, "/clock"),
                               profile_sample=profile_sample)
            elif name == "gt_mapper":
                config = load_yaml(CONFIG)
                for vehicle in config["vehicles"]:
                    for key in ("raw_cloud", "mavros_odom", "registered_cloud", "registered_odom"):
                        wait_readiness(
                            runroot, "%s:%s" % (vehicle["name"], key), 120, live_processes,
                            lambda topic=vehicle["topics"][key]: topic_payload_seen(runroot, topic),
                            profile_sample=profile_sample)
            elif name == "bridges":
                wait_readiness(runroot, "bridges", 60, live_processes, lambda: True,
                               required_nodes=("/px4_bridge_1", "/px4_bridge_2"),
                               profile_sample=profile_sample)
            elif name == "racer":
                for vehicle in load_yaml(CONFIG)["vehicles"]:
                    wait_frontier_readiness(
                        runroot, "%s:frontier" % vehicle["name"], live_processes,
                        lambda topic=vehicle["topics"]["frontier"]: topic_payload_seen(runroot, topic),
                        required_nodes=("/px4_bridge_1", "/px4_bridge_2"),
                        profile_sample=profile_sample)
    except Exception:
        stop_active({"runroot": str(runroot), "processes": processes,
                     "teardown_identity": teardown_identity(runroot)})
        raise
    running_capacity = system_capacity()
    running_ok, running_detail = capacity_gate(running_capacity, "running", startup_capacity)
    (Path(runroot) / "resource_capacity_ready.json").write_text(
        json.dumps({"facts": running_capacity, "baseline": startup_capacity,
                    "ok": running_ok, "detail": running_detail}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    if not running_ok:
        stop_active({"runroot": str(runroot), "processes": processes,
                     "teardown_identity": teardown_identity(runroot)})
        raise RuntimeError("running resource gate failed: " + running_detail)
    active = {"runroot": str(runroot), "processes": processes,
              "ros_environment": runroot_ros_environment(runroot),
              "teardown_identity": teardown_identity(runroot),
              "manifest": str(manifest_path), "started_utc": dt.datetime.now(
                  dt.timezone.utc).isoformat()}
    profile_sample()
    ACTIVE.write_text(json.dumps(active, indent=2) + "\n", encoding="utf-8")
    return active


def load_active():
    if not ACTIVE.is_file():
        raise RuntimeError("no active 2-UAV lifecycle")
    active = json.loads(ACTIVE.read_text(encoding="utf-8"))
    active["ros_environment"] = active_ros_environment(active)
    return active


def proc_snapshot(proc_root=Path("/proc")):
    """Read only pid/ppid/environ facts used for narrowly scoped teardown."""
    snapshot = {}
    for entry in Path(proc_root).iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / "stat").read_text(encoding="utf-8").split()
            environ = dict(item.split("=", 1) for item in
                           (entry / "environ").read_bytes().decode(errors="ignore").split("\0")
                           if "=" in item)
            snapshot[int(entry.name)] = {"ppid": int(fields[3]), "environ": environ}
        except (OSError, ValueError, IndexError):
            continue
    return snapshot


def descendant_closure(root_pids, snapshot):
    selected = set(int(pid) for pid in root_pids)
    changed = True
    while changed:
        changed = False
        for pid, fact in snapshot.items():
            if fact.get("ppid") in selected and pid not in selected:
                selected.add(pid)
                changed = True
    return selected


def runroot_identity_matches(fact, runroot, master_uri):
    environment = fact.get("environ", {})
    expected = runroot_ros_environment(runroot)
    return (environment.get("ROS_LOG_DIR") == expected["ROS_LOG_DIR"] and
            environment.get("ROS_HOME") == expected["ROS_HOME"] and
            bool(master_uri) and environment.get("ROS_MASTER_URI") == master_uri)


def master_port_released(master_uri, connect=socket.create_connection):
    """Fail closed unless the runroot's exact ROS master endpoint refuses connects."""
    parsed = urlparse(master_uri or "")
    if not parsed.hostname or not parsed.port:
        return False
    try:
        connection = connect((parsed.hostname, parsed.port), timeout=0.2)
    except OSError:
        return True
    connection.close()
    return False


def teardown_targets(active, snapshot, include_roots=True):
    processes = active["processes"]
    runroot = active["runroot"]
    identity = active.get("teardown_identity", {})
    master_uri = identity.get("ROS_MASTER_URI")
    roots = {int(spec["pid"]) for spec in processes.values()}
    accepted_roots = {pid for pid in roots if pid in snapshot and
                      runroot_identity_matches(snapshot[pid], runroot, master_uri)}
    rejected_roots = roots - accepted_roots
    closure = descendant_closure(accepted_roots, snapshot) if include_roots else set()
    targets = set(closure)
    # Reparented descendants must still prove the exact runroot and master identity.
    targets.update(pid for pid, fact in snapshot.items()
                   if runroot_identity_matches(fact, runroot, master_uri))
    return {"roots": sorted(roots), "accepted_roots": sorted(accepted_roots),
            "rejected_roots": sorted(rejected_roots), "descendants": sorted(closure - roots),
            "targets": sorted(targets), "master_uri": master_uri,
            "identity_confirmed": bool(master_uri) and not rejected_roots}


def stop_active(active, snapshot_reader=proc_snapshot, kill=os.kill, sleep=time.sleep,
                master_probe=master_port_released):
    runroot = Path(active["runroot"])
    before = teardown_targets(active, snapshot_reader())
    outcomes = {"top_level": before["roots"], "descendants": before["descendants"],
                "term": [], "kill": [], "survivors": [],
                "identity_confirmed": before["identity_confirmed"]}
    # A rejected root makes the result fail-closed, but must not prevent cleanup
    # of separately reparented targets that do prove this runroot's identity.
    for pid in before["targets"]:
        try:
            kill(pid, signal.SIGTERM)
            outcomes["term"].append(pid)
        except ProcessLookupError:
            pass
    sleep(TEARDOWN_TERM_GRACE_S)
    after_term = teardown_targets(active, snapshot_reader(), include_roots=False)
    for pid in after_term["targets"]:
        try:
            kill(pid, signal.SIGKILL)
            outcomes["kill"].append(pid)
        except ProcessLookupError:
            pass
    final = teardown_targets(active, snapshot_reader(), include_roots=False)
    outcomes["survivors"] = final["targets"]
    outcomes["master_port_released"] = master_probe(before["master_uri"])
    outcomes["clean"] = (not outcomes["survivors"] and before["identity_confirmed"] and
                         outcomes["master_port_released"])
    return outcomes


def sim_time_s(runroot):
    command = (
        "source /opt/ros/noetic/setup.bash; "
        "rostopic echo -n 1 /clock --noarr")
    argv, environment = ros_command_spec(runroot, command)
    output = subprocess.run(
        argv, env=environment, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15).stdout
    secs = None
    nsecs = 0
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("secs:"):
            secs = int(stripped.split(":", 1)[1])
        elif stripped.startswith("nsecs:"):
            nsecs = int(stripped.split(":", 1)[1])
    if secs is None:
        raise RuntimeError("unable to parse /clock")
    return secs + nsecs / 1e9


def monitor_until(active, duration_sim_s, dropout_config=None, config=None,
                  sim_time_probe=None, dropout_executor=None,
                  monotonic=time.monotonic, sleep=time.sleep):
    """Run until duration, abort, or process death.

    When dropout_config is enabled the D1 white-list fault injection fires
    once at trigger_sim_s of elapsed sim time; the abort path stays active.
    """
    runroot = Path(active["runroot"])
    start_sim_s = None
    wall_deadline = monotonic() + max(600.0, duration_sim_s * 10.0)
    sim_time_probe = sim_time_probe or (lambda: sim_time_s(runroot))
    dropout_triggered = False
    while monotonic() < wall_deadline:
        profiler = resource_profiler(runroot, active["processes"])
        abort_file = runroot / "fleet" / "abort.request"
        if abort_file.is_file():
            return "abort_requested"
        for name, spec in active["processes"].items():
            try:
                os.kill(int(spec["pid"]), 0)
            except ProcessLookupError:
                return "process_death:" + name
        try:
            current_sim_s = sim_time_probe()
        except (OSError, ValueError, subprocess.SubprocessError):
            sleep(1.0)
            continue
        profiler.sample(current_sim_s)
        if start_sim_s is None:
            start_sim_s = current_sim_s
        if dropout_due(dropout_config, current_sim_s - start_sim_s, dropout_triggered):
            executor = dropout_executor or (
                lambda cfg, sim_s: execute_dropout(runroot, cfg, config, sim_s=sim_s))
            executor(dropout_config, current_sim_s)
            dropout_triggered = True
        if current_sim_s - start_sim_s >= duration_sim_s:
            return "duration_complete"
        sleep(1.0)
    return "wall_watchdog_timeout"


def last_jsonl(path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    if not lines:
        raise RuntimeError("empty telemetry evidence: %s" % path)
    return json.loads(lines[-1])


def exactly_one_topic_owner(owners):
    return (isinstance(owners, list) and len(owners) == 1 and
            isinstance(owners[0], str) and bool(owners[0]))


def watchdog_evidence(runroot):
    runroot = Path(runroot)
    if (runroot / "fleet" / "abort.request").is_file():
        return False, "abort.request exists"
    try:
        fleet = last_jsonl(runroot / "fleet" / "telemetry.jsonl")
        vehicles = [last_jsonl(runroot / name / "telemetry.jsonl")
                    for name in ("uav0", "uav1")]
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return False, "missing watchdog telemetry: %s" % exc
    if not fleet.get("telemetry_completeness"):
        return False, "fleet telemetry incomplete"
    config = load_yaml(CONFIG)
    expected_topics = {topic for vehicle in config["vehicles"]
                       for topic in vehicle["topics"].values()}
    topic_owners = fleet.get("topic_owners")
    if not isinstance(topic_owners, dict) or set(topic_owners) != expected_topics:
        return False, "topic owner evidence missing"
    if any(not exactly_one_topic_owner(topic_owners[topic])
           for topic in expected_topics):
        return False, "topic owner evidence incomplete"
    expected_children = {vehicle["frames"]["child"] for vehicle in config["vehicles"]}
    tf_last_wall_s = fleet.get("tf_last_wall_s")
    if (not isinstance(tf_last_wall_s, dict) or
            set(tf_last_wall_s) != expected_children or
            any(not isinstance(value, (int, float)) for value in tf_last_wall_s.values())):
        return False, "TF freshness evidence missing"
    if any(not report.get("coverage", {}).get("available") for report in vehicles):
        return False, "per-UAV coverage evidence missing"
    return True, "watchdog evidence complete"


def watchdog_soak(runroot, seconds):
    try:
        baseline = json.loads((Path(runroot) / "resource_capacity_startup.json").read_text(
            encoding="utf-8"))["facts"]
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return False, "resource capacity baseline missing"
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        profiler = resource_profiler(runroot)
        if profiler is not None:
            profiler.sample(recorded_sim_time(runroot))
        capacity_ok, capacity_detail = capacity_gate(system_capacity(), "running", baseline)
        if not capacity_ok:
            return False, "resource gate failed: " + capacity_detail
        if (Path(runroot) / "fleet" / "abort.request").is_file():
            return False, "abort.request exists during soak"
        time.sleep(1.0)
    return watchdog_evidence(runroot)


def wait_final_metrics(runroot, timeout_s=10):
    paths = [Path(runroot) / name / "metrics.json" for name in ("uav0", "uav1", "fleet")]
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if all(path.is_file() for path in paths):
            return True
        time.sleep(0.25)
    return False


def final_safety_result(runroot, require_command_chain=False):
    runroot = Path(runroot)
    if (runroot / "fleet" / "abort.request").is_file():
        return False, "abort.request exists"
    try:
        fleet = json.loads((runroot / "fleet" / "metrics.json").read_text(encoding="utf-8"))
        vehicles = [json.loads((runroot / name / "metrics.json").read_text(
            encoding="utf-8")) for name in ("uav0", "uav1")]
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return False, "missing final metrics: %s" % exc
    safe, detail = final_metrics_valid(fleet, vehicles)
    profile = resource_usage_summary(runroot)
    if not profile.get("available") or not profile.get("samples") or not profile.get("roles"):
        return False, "resource profile missing or incomplete"
    if not safe or not require_command_chain:
        return safe, detail
    return smoke_command_chain_valid(vehicles)


def final_metrics_valid(fleet, vehicles):
    if fleet.get("abort_reasons") or not fleet.get("telemetry_completeness"):
        return False, "fleet safety metrics failed"
    if any(report.get("crash") or not report.get("telemetry_complete") or
           not report.get("coverage", {}).get("available") for report in vehicles):
        return False, "per-UAV safety metrics failed"
    return True, "final safety metrics complete"


def smoke_command_chain_valid(vehicles):
    """Require both vehicles to have entered the post-goal command loop."""
    if not isinstance(vehicles, (list, tuple)) or len(vehicles) != 2:
        return False, "smoke command chain requires exactly uav0 and uav1 metrics"
    failures = []
    for name, report in zip(("uav0", "uav1"), vehicles):
        if not isinstance(report, dict):
            failures.append("%s metrics missing" % name)
            continue
        declared_name = report.get("name")
        if declared_name is not None and declared_name != name:
            failures.append("%s metrics name mismatch" % name)
            continue
        telemetry = report.get("telemetry")
        ack_timeout = report.get("ack_timeout")
        if not isinstance(telemetry, dict):
            failures.append("%s telemetry missing" % name)
            continue
        for key in ("trajectory", "pos_cmd", "ack"):
            value = telemetry.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                failures.append("%s telemetry.%s must be > 0" % (name, key))
        count = ack_timeout.get("count") if isinstance(ack_timeout, dict) else None
        if not isinstance(count, int) or isinstance(count, bool) or count != 0:
            failures.append("%s ack_timeout.count must be 0" % name)
    return (not failures, "smoke command chain complete" if not failures else
            "; ".join(failures))


def action_preflight(manifest_path):
    manifest, approval_bytes, approval_digest = approval_guard("preflight", manifest_path)
    parse_dropout_config(manifest)  # D1 fail-fast: reject invalid dropout before runroot
    runroot = make_runroot("preflight", manifest_path, approval_bytes)
    consume_approval("preflight", manifest_path, approval_digest, runroot)
    checks = []
    runtime_error = None
    try:
        with runroot_ros_environment_scope(runroot):
            start_stack(runroot, manifest_path)
            checks = live_checks(CONFIG, runroot)
            config = load_yaml(CONFIG)
            soak_ok, soak_detail = watchdog_soak(
                runroot, config["safety_contract"]["telemetry"]["preflight_soak_s"])
            checks.append({"name": "live.watchdog_soak", "ok": soak_ok,
                           "detail": soak_detail})
    except Exception as exc:
        runtime_error = str(exc)
    finally:
        if ACTIVE.is_file():
            active = load_active()
            outcomes = stop_active(active)
            (runroot / "stop_result.json").write_text(
                json.dumps(outcomes, indent=2) + "\n", encoding="utf-8")
            ACTIVE.unlink()
            if not outcomes.get("clean") and runtime_error is None:
                runtime_error = "teardown verification failed"
    metrics_ready = wait_final_metrics(runroot)
    safe, safety_detail = final_safety_result(runroot) if metrics_ready else (
        False, "final metrics timeout")
    checks.append({"name": "final.metrics", "ok": metrics_ready,
                   "detail": "available" if metrics_ready else "timeout"})
    checks.append({"name": "final.safety", "ok": safe, "detail": safety_detail})
    if runtime_error:
        checks.append({"name": "preflight.runtime", "ok": False,
                       "detail": runtime_error})
    passed = all(item["ok"] for item in checks)
    (runroot / "live_preflight.json").write_text(json.dumps(
        {"passed": passed, "checks": checks,
         "resource_usage": resource_usage_summary(runroot)}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return 0 if passed else 2


def action_launch(manifest_path):
    manifest, approval_bytes, approval_digest = approval_guard("launch", manifest_path)
    runroot = make_runroot("smoke", manifest_path, approval_bytes)
    consume_approval("launch", manifest_path, approval_digest, runroot)
    active = start_stack(runroot, manifest_path)
    stopped = False
    try:
        with runroot_ros_environment_scope(runroot):
            checks = live_checks(CONFIG, runroot)
            report = {"passed": all(item["ok"] for item in checks), "checks": checks,
                      "resource_usage": resource_usage_summary(runroot)}
            (runroot / "live_preflight.json").write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            if not report["passed"]:
                raise RuntimeError("live preflight failed; smoke trigger withheld")
            config = load_yaml(CONFIG)
            manifest_dropout = parse_dropout_config(load_yaml(manifest_path))
            soak_ok, soak_detail = watchdog_soak(
                runroot, config["safety_contract"]["telemetry"]["preflight_soak_s"])
            report["checks"].append({"name": "live.watchdog_soak", "ok": soak_ok,
                                     "detail": soak_detail})
            report["passed"] = all(item["ok"] for item in report["checks"])
            report["resource_usage"] = resource_usage_summary(runroot)
            (runroot / "live_preflight.json").write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            if not soak_ok:
                raise RuntimeError("watchdog soak failed; smoke trigger withheld: " + soak_detail)
            trigger = (
                "source /opt/ros/noetic/setup.bash; rostopic pub -1 /move_base_simple/goal "
                "geometry_msgs/PoseStamped "
                "'{header: {frame_id: world}, pose: {orientation: {w: 1.0}}}'")
            argv, environment = ros_command_spec(runroot, trigger)
            subprocess.run(argv, env=environment, check=True, timeout=15)
            reason = monitor_until(active, int(manifest["duration_sim_s"]),
                                   dropout_config=manifest_dropout, config=config)
        outcomes = stop_active(active)
        stopped = True
        ACTIVE.unlink(missing_ok=True)
    finally:
        if not stopped:
            stop_active(active)
            ACTIVE.unlink(missing_ok=True)
    metrics_ready = wait_final_metrics(runroot)
    safe, safety_detail = final_safety_result(runroot, require_command_chain=True) if metrics_ready else (
        False, "final metrics timeout")
    summary = {
        "runroot": str(runroot),
        "exit_reason": reason,
        "stop": outcomes,
        "uav0_metrics": (runroot / "uav0/metrics.json").is_file(),
        "uav1_metrics": (runroot / "uav1/metrics.json").is_file(),
        "fleet_metrics": (runroot / "fleet/metrics.json").is_file(),
        "final_safety_passed": safe,
        "final_safety_detail": safety_detail,
        "resource_usage": resource_usage_summary(runroot),
    }
    (runroot / "execution_result.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if reason == "duration_complete" and safe and all(summary[key] for key in (
        "uav0_metrics", "uav1_metrics", "fleet_metrics")) else 2


def action_monitor():
    active = load_active()
    runroot = Path(active["runroot"])
    statuses = {}
    for name, spec in active["processes"].items():
        try:
            os.kill(int(spec["pid"]), 0)
            statuses[name] = "alive"
        except ProcessLookupError:
            statuses[name] = "dead"
    abort_file = runroot / "fleet" / "abort.request"
    report = {"runroot": str(runroot), "processes": statuses,
              "abort_requested": abort_file.is_file()}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 2 if abort_file.is_file() or "dead" in statuses.values() else 0


def action_stop():
    active = load_active()
    outcomes = stop_active(active)
    runroot = Path(active["runroot"])
    (runroot / "stop_result.json").write_text(
        json.dumps(outcomes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ACTIVE.unlink(missing_ok=True)
    print(json.dumps(outcomes, indent=2, sort_keys=True))
    return 0


def action_collect():
    active = load_active()
    runroot = Path(active["runroot"])
    result = action_monitor()
    summary = {"runroot": str(runroot), "monitor_exit": result,
               "uav0_metrics": (runroot / "uav0/metrics.json").is_file(),
               "uav1_metrics": (runroot / "uav1/metrics.json").is_file(),
               "fleet_metrics": (runroot / "fleet/metrics.json").is_file()}
    (runroot / "collection_result.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if all(summary[key] for key in (
        "uav0_metrics", "uav1_metrics", "fleet_metrics")) else 2


def self_test():
    class FakeProcess:
        def __init__(self, code=None):
            self.code = code

        def poll(self):
            return self.code

    alive = {"gazebo": FakeProcess(), "bridges": FakeProcess()}
    assert readiness_state(alive, True) == ("ready", "ready")
    assert readiness_state(alive, False)[0] == "waiting"
    assert readiness_state(alive, True, {"/px4_bridge_1"},
                           ("/px4_bridge_1", "/px4_bridge_2"))[0] == "waiting"
    current_dead = {"racer": FakeProcess(17)}
    assert readiness_state(current_dead, True) == (
        "failed", "readiness process exited: racer code=17")
    previous_dead = {"gazebo": FakeProcess(9), "racer": FakeProcess()}
    assert readiness_state(previous_dead, True) == (
        "failed", "readiness process exited: gazebo code=9")

    def expect_gate_error(expected, **kwargs):
        try:
            wait_readiness("unused", timeout_s=0, monotonic=lambda: 0.0,
                           sleep=lambda _seconds: None, **kwargs)
            raise AssertionError("readiness gate unexpectedly passed")
        except RuntimeError as exc:
            assert str(exc) == expected, str(exc)

    wait_readiness("unused", "payload", 0, alive, lambda: True,
                   monotonic=lambda: 0.0, sleep=lambda _seconds: None)
    expect_gate_error("readiness timeout: silent: no payload", label="silent",
                      processes=alive, payload_probe=lambda: False)
    expect_gate_error("readiness process exited: racer code=17", label="current-dead",
                      processes=current_dead, payload_probe=lambda: True)
    expect_gate_error("readiness process exited: gazebo code=9", label="previous-dead",
                      processes=previous_dead, payload_probe=lambda: True)
    bridge_nodes = {"/px4_bridge_1"}
    expect_gate_error("readiness timeout: bridges: missing nodes: /px4_bridge_2",
                      label="bridges", processes=alive, payload_probe=lambda: True,
                      required_nodes=("/px4_bridge_1", "/px4_bridge_2"),
                      node_probe=lambda: bridge_nodes)
    bridge_nodes = {"/px4_bridge_1", "/px4_bridge_2"}

    def payload_loses_bridge():
        bridge_nodes.remove("/px4_bridge_2")
        return True

    expect_gate_error("readiness timeout: frontier: missing nodes: /px4_bridge_2",
                      label="frontier", processes=alive,
                      payload_probe=payload_loses_bridge,
                      required_nodes=("/px4_bridge_1", "/px4_bridge_2"),
                      node_probe=lambda: bridge_nodes)
    bridge_nodes = {"/px4_bridge_1", "/px4_bridge_2"}
    node_success = node_probe_result("success", bridge_nodes)
    assert readiness_state(alive, True, required_nodes=(
        "/px4_bridge_1", "/px4_bridge_2"), node_probe=node_success) == ("ready", "ready")
    assert readiness_state(alive, True, required_nodes=(
        "/px4_bridge_1", "/px4_bridge_2"), node_probe=node_probe_result(
            "success", {"/px4_bridge_1"}))[1] == "missing nodes: /px4_bridge_2"
    assert readiness_state(alive, True, required_nodes=(
        "/px4_bridge_1", "/px4_bridge_2"), node_probe=node_probe_result(
            "timeout", detail="attempt 2/2"))[1] == "node probe timeout: attempt 2/2"
    assert readiness_state(alive, True, required_nodes=(
        "/px4_bridge_1", "/px4_bridge_2"), node_probe=node_probe_result(
            "error", detail="returncode 1"))[1] == "node probe error: returncode 1"

    class FakeTime:
        def __init__(self):
            self.now = 0.0

        def monotonic(self):
            return self.now

        def sleep(self, seconds):
            self.now += seconds

    def expect_frontier_error(expected, **kwargs):
        try:
            wait_frontier_readiness("unused", "uav0:frontier", **kwargs)
            raise AssertionError("frontier gate unexpectedly passed")
        except RuntimeError as exc:
            assert str(exc) == expected, str(exc)

    # At RT~0.005, the old 180-wall-s limit passes with <1 sim s; the new
    # gate keeps waiting until payload arrives because its sim budget remains.
    slow_time = FakeTime()
    wait_frontier_readiness(
        "unused", "uav0:frontier", alive,
        payload_probe=lambda: slow_time.now >= 181.0,
        required_nodes=("/px4_bridge_1", "/px4_bridge_2"),
        node_probe=lambda: node_success, sim_time_probe=lambda: slow_time.now / 200.0,
        monotonic=slow_time.monotonic, sleep=slow_time.sleep)
    assert slow_time.now >= 181.0 and slow_time.now / 200.0 < FRONTIER_INIT_SIM_BUDGET_S
    sim_budget_time = FakeTime()
    expect_frontier_error(
        "readiness timeout: uav0:frontier: frontier sim budget exhausted",
        processes=alive, payload_probe=lambda: False,
        required_nodes=("/px4_bridge_1", "/px4_bridge_2"),
        node_probe=lambda: node_success, sim_time_probe=lambda: sim_budget_time.now,
        monotonic=sim_budget_time.monotonic, sleep=sim_budget_time.sleep)
    wall_cap_time = FakeTime()
    expect_frontier_error("readiness timeout: uav0:frontier: wall hard cap",
                          processes=alive, payload_probe=lambda: False,
                          required_nodes=("/px4_bridge_1", "/px4_bridge_2"),
                          node_probe=lambda: node_success,
                          sim_time_probe=lambda: wall_cap_time.now / 100.0,
                          monotonic=wall_cap_time.monotonic, sleep=wall_cap_time.sleep)
    stalled_time = FakeTime()
    expect_frontier_error("readiness timeout: uav0:frontier: clock stalled",
                          processes=alive, payload_probe=lambda: False,
                          required_nodes=("/px4_bridge_1", "/px4_bridge_2"),
                          node_probe=lambda: node_success, sim_time_probe=lambda: 0.0,
                          monotonic=stalled_time.monotonic, sleep=stalled_time.sleep)
    expect_frontier_error("readiness process exited: racer code=17",
                          processes=current_dead, payload_probe=lambda: True,
                          required_nodes=("/px4_bridge_1", "/px4_bridge_2"),
                          node_probe=lambda: node_success, sim_time_probe=lambda: 0.0,
                          monotonic=lambda: 0.0, sleep=lambda _seconds: None)
    runroot = Path("/tmp/runner-self-test-runroot")
    identity = {"ROS_LOG_DIR": str(runroot / "logs/ros"),
                "ROS_HOME": str(runroot / "logs/ros-home"),
                "ROS_MASTER_URI": "http://127.0.0.1:11311"}
    snapshot = {
        10: {"ppid": 1, "environ": dict(identity)},
        11: {"ppid": 10, "environ": {}},
        12: {"ppid": 1, "environ": dict(identity)},  # reparented matching descendant
        99: {"ppid": 1, "environ": {"ROS_MASTER_URI": identity["ROS_MASTER_URI"]}},
    }
    test_active = {"runroot": str(runroot), "processes": {"gazebo": {"pid": 10}},
                   "teardown_identity": identity}
    teardown = teardown_targets(test_active, snapshot)
    assert teardown["roots"] == [10] and teardown["descendants"] == [11]
    assert teardown["targets"] == [10, 11, 12] and teardown["identity_confirmed"]
    assert 99 not in teardown["targets"]
    mismatched = dict(snapshot)
    mismatched[12] = {"ppid": 1, "environ": dict(identity, ROS_HOME="/wrong")}
    assert 12 not in teardown_targets(test_active, mismatched)["targets"]
    reused_root = dict(snapshot)
    reused_root[10] = {"ppid": 1, "environ": dict(identity, ROS_HOME="/reused")}
    root_rejected = teardown_targets(test_active, reused_root)
    assert root_rejected["accepted_roots"] == [] and root_rejected["targets"] == [12]
    assert not root_rejected["identity_confirmed"] and 11 not in root_rejected["targets"]
    partial_snapshots = iter([reused_root, {}, {}])
    partial_sent = []
    partial = stop_active(test_active, snapshot_reader=lambda: next(partial_snapshots),
                          kill=lambda pid, sig: partial_sent.append((pid, sig)),
                          sleep=lambda _: None, master_probe=lambda _uri: True)
    assert partial_sent == [(12, signal.SIGTERM)]
    assert not partial["clean"] and partial["survivors"] == []
    snapshots = iter([snapshot, {}, {}])
    sent = []
    clean = stop_active(test_active,
                        snapshot_reader=lambda: next(snapshots),
                        kill=lambda pid, sig: sent.append((pid, sig)), sleep=lambda _: None,
                        master_probe=lambda _uri: True)
    assert clean["clean"] and {pid for pid, _sig in sent} == {10, 11, 12}
    survivors = stop_active(test_active,
                            snapshot_reader=lambda: snapshot,
                            kill=lambda _pid, _sig: None, sleep=lambda _: None,
                            master_probe=lambda _uri: True)
    assert not survivors["clean"] and survivors["survivors"] == [10, 12]
    manifest = {"approval_status": "blocked_pending_verified_launch_and_preflight"}
    contract = {"issued_by_must_be": "sol", "max_uses": 1}
    base = {"schema_version": 1, "approved": True, "issued_by": "sol", "max_uses": 1,
            "manifest_sha256": "manifest", "source_hash_manifest_sha256": "source"}
    try:
        validate_approval_package("preflight", manifest, {}, "manifest", "source", contract)
        raise AssertionError("missing package accepted")
    except RuntimeError:
        pass
    preflight = dict(base, stage="preflight", allowed_actions=["preflight"])
    validate_approval_package("preflight", manifest, preflight, "manifest", "source", contract)
    smoke = dict(base, stage="smoke", allowed_actions=["launch"])
    validate_approval_package("launch", manifest, smoke, "manifest", "source", contract)
    try:
        validate_approval_package("preflight", manifest,
                                  dict(preflight, max_uses=2), "manifest", "source", contract)
        raise AssertionError("multi-use approval accepted")
    except RuntimeError:
        pass
    try:
        validate_approval_package("launch", manifest, smoke, "manifest", "drift", contract)
        raise AssertionError("hash drift accepted")
    except RuntimeError:
        pass
    good_vehicle = {"crash": False, "telemetry_complete": True,
                    "coverage": {"available": True},
                    "telemetry": {"trajectory": 1, "pos_cmd": 1, "ack": 1},
                    "ack_timeout": {"count": 0}}
    assert final_metrics_valid({"abort_reasons": [], "telemetry_completeness": True},
                               [good_vehicle, good_vehicle])[0]
    assert not final_metrics_valid({"abort_reasons": ["crash:uav0"],
                                    "telemetry_completeness": True},
                                   [good_vehicle, good_vehicle])[0]
    assert smoke_command_chain_valid([good_vehicle, good_vehicle])[0]
    no_command = dict(good_vehicle, telemetry={"trajectory": 0, "pos_cmd": 1, "ack": 1})
    assert not smoke_command_chain_valid([no_command, good_vehicle])[0]
    no_ack = dict(good_vehicle, ack_timeout={"count": 1})
    assert not smoke_command_chain_valid([good_vehicle, no_ack])[0]
    for invalid in (None, True, "1", 1.0, float("nan"), float("inf"), 0, -1):
        invalid_command = dict(good_vehicle, telemetry={
            "trajectory": invalid, "pos_cmd": 1, "ack": 1})
        assert not smoke_command_chain_valid([invalid_command, good_vehicle])[0]
    for invalid in (None, True, "0", 0.0, float("nan"), float("inf"), -1):
        invalid_ack = dict(good_vehicle, ack_timeout={"count": invalid})
        assert not smoke_command_chain_valid([good_vehicle, invalid_ack])[0]
    assert not smoke_command_chain_valid([])[0]
    assert not smoke_command_chain_valid([good_vehicle])[0]
    assert not smoke_command_chain_valid([good_vehicle, good_vehicle, good_vehicle])[0]
    assert not smoke_command_chain_valid({"uav0": good_vehicle, "uav1": good_vehicle})[0]
    assert final_metrics_valid({"abort_reasons": [], "telemetry_completeness": True},
                               [dict(good_vehicle, telemetry={}), dict(good_vehicle, telemetry={})])[0]
    config = load_yaml(CONFIG)
    topic_owners = {topic: ["/owner"] for vehicle in config["vehicles"]
                    for topic in vehicle["topics"].values()}
    tf_last_wall_s = {vehicle["frames"]["child"]: 1.0 for vehicle in config["vehicles"]}
    with tempfile.TemporaryDirectory() as tempdir:
        root = Path(tempdir)
        for name in ("uav0", "uav1", "fleet"):
            (root / name).mkdir()
        for name in ("uav0", "uav1"):
            (root / name / "telemetry.jsonl").write_text(
                json.dumps(good_vehicle) + "\n", encoding="utf-8")
        fleet = {"telemetry_completeness": True, "topic_owners": topic_owners,
                 "tf_last_wall_s": tf_last_wall_s}
        (root / "fleet" / "telemetry.jsonl").write_text(
            json.dumps(fleet) + "\n", encoding="utf-8")
        assert watchdog_evidence(root)[0]
        duplicate_topic = next(iter(topic_owners))
        fleet["topic_owners"][duplicate_topic] = ["/owner_a", "/owner_b"]
        (root / "fleet" / "telemetry.jsonl").write_text(
            json.dumps(fleet) + "\n", encoding="utf-8")
        assert not watchdog_evidence(root)[0]
        fleet["topic_owners"][duplicate_topic] = ["/owner"]
        fleet["tf_last_wall_s"] = {}
        (root / "fleet" / "telemetry.jsonl").write_text(
            json.dumps(fleet) + "\n", encoding="utf-8")
        assert not watchdog_evidence(root)[0]
    with tempfile.TemporaryDirectory() as tempdir:
        profile_root = Path(tempdir)
        fake_proc = profile_root / "proc"
        fake_proc.mkdir()
        def fake_process(pid, ppid, cpu_ticks, rss_kb):
            directory = fake_proc / str(pid)
            directory.mkdir(exist_ok=True)
            fields = ["0"] * 52
            fields[3], fields[13], fields[14] = str(ppid), str(cpu_ticks), "0"
            (directory / "stat").write_text(" ".join(fields), encoding="utf-8")
            (directory / "environ").write_bytes(b"")
            (directory / "status").write_text(
                "VmRSS:\t%d kB\nThreads:\t2\n" % rss_kb, encoding="utf-8")
        fake_process(10, 1, 100, 1000)
        fake_time = [0.0]
        roles = {"startup": {"pid": 10}, "disappeared": {"pid": 99}}
        profiler = ResourceProfiler(profile_root, roles, interval_s=0,
                                    monotonic=lambda: fake_time[0], proc_root=fake_proc,
                                    clk_tck=100)
        first_sample = profiler.sample(None)
        fake_time[0] = 1.0
        fake_process(10, 1, 120, 1200)
        fake_process(11, 10, 30, 600)
        roles["racer"] = {"pid": 11}
        second_sample = profiler.sample(2.0)
        fake_time[0] = 2.0
        fake_process(10, 1, 140, 1300)
        fake_process(11, 10, 50, 700)
        third_sample = profiler.sample(2.5)
        assert first_sample["sim_evidence_missing"] and first_sample["sim_s"] is None
        assert second_sample["roles"]["startup"]["cpu_cores"] == 0.5
        assert third_sample["rt_factor"] == 0.5
        assert second_sample["roles"]["racer"]["cpu_delta_ticks"] is None
        assert second_sample["roles"]["disappeared"]["evidence_missing"]
        profile_summary = resource_usage_summary(profile_root)
        assert profile_summary["available"] and profile_summary["samples"] == 3
        assert profile_summary["roles"]["startup"]["p95_rss_kb"] == 2000
        assert profile_summary["roles"]["startup"]["p95_cpu_cores"] == 0.5
        assert profile_summary["valid_rt_samples"] == 1
    baseline = {"mem_available_bytes": 8 * GIB, "load1": 9.9, "swap_in": 4, "swap_out": 5}
    assert capacity_gate(baseline, "startup")[0]
    assert not capacity_gate(dict(baseline, mem_available_bytes=8 * GIB - 1), "startup")[0]
    assert not capacity_gate(dict(baseline, load1=10.0), "startup")[0]
    running = dict(baseline, mem_available_bytes=3 * GIB)
    assert capacity_gate(running, "running", baseline)[0]
    assert capacity_gate(dict(running, swap_out=6), "running", baseline)[0]  # delta=1 可接受
    assert not capacity_gate(dict(running, swap_out=200006), "running", baseline)[0]  # delta=200001>200000
    assert not capacity_gate(None, "running", baseline)[0]
    with tempfile.TemporaryDirectory() as tempdir:
        first_runroot = Path(tempdir) / "RUN-first"
        second_runroot = Path(tempdir) / "RUN-second"
        first_runroot.mkdir()
        second_runroot.mkdir()
        first_environment = prepare_runroot_ros_environment(first_runroot)
        second_environment = prepare_runroot_ros_environment(second_runroot)
        assert first_environment != second_environment
        assert all(Path(directory).is_dir() for directory in first_environment.values())
        assert all(Path(directory).is_dir() for directory in second_environment.values())
        assert json.loads((first_runroot / "runtime_environment.json").read_text(
            encoding="utf-8"))["ros_environment"] == first_environment
        commands = [argv[2] for _, argv in process_specs(first_runroot)]
        runtime_prefix = ros_runtime_prefix(first_runroot)
        assert runtime_prefix.startswith("source /opt/ros/noetic/setup.bash; ")
        for name in ("ROS_PACKAGE_PATH", "CMAKE_PREFIX_PATH", "PYTHONPATH",
                     "LD_LIBRARY_PATH", "ROS_LOG_DIR", "ROS_HOME"):
            assert runtime_prefix.index("export %s=" % name) > runtime_prefix.index(
                "source /opt/ros/noetic/setup.bash")
        assert all(command.startswith(runtime_prefix) for command in commands)
        probe_specs = workspace_probe_specs(first_runroot)
        assert {name for name, _command, _argv, _environment in probe_specs} == {
            "swarm_lio", "exploration_manager", "quadrotor_msgs"}
        for _name, probe_command, argv, environment in probe_specs:
            assert argv[2].startswith(runtime_prefix)
            assert argv[2] == runtime_prefix + probe_command
            assert environment["ROS_LOG_DIR"] == first_environment["ROS_LOG_DIR"]
            assert environment["ROS_HOME"] == first_environment["ROS_HOME"]
            assert "~/.ros" not in argv[2]
        assert all("export ROS_LOG_DIR=" in command and "export ROS_HOME=" in command
                   for command in commands)
        assert all(first_environment["ROS_LOG_DIR"] in command and
                   first_environment["ROS_HOME"] in command and "~/.ros" not in command
                   for command in commands)
        inherited = {"ROS_LOG_DIR": "/shared/ros", "ROS_HOME": "/shared/ros-home"}
        first_child_environment = ros_subprocess_environment(first_runroot, inherited)
        second_child_environment = ros_subprocess_environment(second_runroot, inherited)
        assert first_child_environment["ROS_LOG_DIR"] == first_environment["ROS_LOG_DIR"]
        assert first_child_environment["ROS_HOME"] == first_environment["ROS_HOME"]
        assert second_child_environment["ROS_LOG_DIR"] == second_environment["ROS_LOG_DIR"]
        assert second_child_environment["ROS_HOME"] == second_environment["ROS_HOME"]
        assert first_child_environment != second_child_environment
        restored_environment = active_ros_environment({"runroot": str(second_runroot)})
        assert restored_environment["ROS_LOG_DIR"] == second_environment["ROS_LOG_DIR"]
        assert restored_environment["ROS_HOME"] == second_environment["ROS_HOME"]
        for command in (
                "source /opt/ros/noetic/setup.bash; rostopic list",
                "source /opt/ros/noetic/setup.bash; rostopic echo -n 1 /clock --noarr",
                "source /opt/ros/noetic/setup.bash; rostopic pub -1 /move_base_simple/goal"):
            argv, environment = ros_command_spec(first_runroot, command)
            assert argv == ["bash", "-lc", command]
            assert environment["ROS_LOG_DIR"] == first_environment["ROS_LOG_DIR"]
            assert environment["ROS_HOME"] == first_environment["ROS_HOME"]
        previous = {name: os.environ.get(name) for name in first_environment}
        with runroot_ros_environment_scope(first_runroot):
            assert all(os.environ[name] == value for name, value in first_environment.items())
        assert all(os.environ.get(name) == value for name, value in previous.items())

    # ── D1 dropout self-test ────────────────────────────────────────────────
    # parse_dropout_config: valid and absent
    assert parse_dropout_config({}) is None
    assert parse_dropout_config({"dropout": None}) is None
    valid_dropout = {"enabled": False, "vehicle": "uav1", "mode": "control_chain",
                     "trigger_sim_s": 60, "cleanup_policy": "stop_active_reclaim",
                     "record": "fleet/dropout.json"}
    parsed = parse_dropout_config({"dropout": valid_dropout})
    assert parsed is not None
    assert parsed["enabled"] is False
    # parse_dropout_config: fail-fast on missing fields
    for key in tuple(valid_dropout):
        partial = dict(valid_dropout)
        del partial[key]
        try:
            parse_dropout_config({"dropout": partial})
            raise AssertionError("expected RuntimeError for missing %s" % key)
        except RuntimeError:
            pass
    # parse_dropout_config: invalid mode
    try:
        parse_dropout_config({"dropout": {**valid_dropout, "mode": "invalid"}})
        raise AssertionError("expected RuntimeError for invalid mode")
    except RuntimeError:
        pass
    # parse_dropout_config: invalid vehicle
    try:
        parse_dropout_config({"dropout": {**valid_dropout, "vehicle": "invalid"}})
        raise AssertionError("expected RuntimeError for invalid vehicle")
    except RuntimeError:
        pass
    # parse_dropout_config: zero trigger_sim_s
    try:
        parse_dropout_config({"dropout": {**valid_dropout, "trigger_sim_s": 0}})
        raise AssertionError("expected RuntimeError for zero trigger_sim_s")
    except RuntimeError:
        pass
    # parse_dropout_config: enabled must be bool
    try:
        parse_dropout_config({"dropout": {**valid_dropout, "enabled": "yes"}})
        raise AssertionError("expected RuntimeError for non-bool enabled")
    except RuntimeError:
        pass

    # dropout_target_nodes: pure mapping
    config = load_yaml(CONFIG)
    dropout_cfg = {**valid_dropout, "vehicle": "uav0"}
    nodes = dropout_target_nodes(config, dropout_cfg)
    assert "/px4_bridge_1" not in nodes
    assert "/exploration_node_1" in nodes
    assert "/traj_server_1" in nodes
    assert len(nodes) == 2
    dropout_cfg_uav1 = {**valid_dropout, "vehicle": "uav1"}
    nodes_uav1 = dropout_target_nodes(config, dropout_cfg_uav1)
    assert "/px4_bridge_2" not in nodes_uav1
    assert "/exploration_node_2" in nodes_uav1
    assert "/traj_server_2" in nodes_uav1
    # dropout_target_nodes: communication mode only kills bridge
    nodes_comm = dropout_target_nodes(config, {**valid_dropout, "mode": "communication"})
    assert nodes_comm == ["/px4_bridge_2"]
    # dropout_target_nodes: node_level kills bridge + exploration + traj
    nodes_nl = dropout_target_nodes(config, {**valid_dropout, "mode": "node_level"})
    assert set(nodes_nl) == {"/px4_bridge_2", "/exploration_node_2", "/traj_server_2"}
    assert len(nodes_nl) == 3

    # dropout_due: pure one-shot trigger decision
    dcfg_enabled = {**valid_dropout, "enabled": True, "trigger_sim_s": 60}
    assert dropout_due(dcfg_enabled, 60.0, False) is True
    assert dropout_due(dcfg_enabled, 59.999, False) is False
    assert dropout_due(dcfg_enabled, 120.0, False) is True
    assert dropout_due(dcfg_enabled, 60.0, True) is False  # already triggered
    assert dropout_due({**valid_dropout, "enabled": False}, 60.0, False) is False
    assert dropout_due(None, 60.0, False) is False

    # execute_dropout: writes fleet/dropout.json with correct fields
    with tempfile.TemporaryDirectory() as tempdir:
        ex_runroot = Path(tempdir) / "RUN-dropout"
        ex_runroot.mkdir()
        fake_pid = os.getpid()
        ex_cfg = {**valid_dropout, "enabled": True, "vehicle": "uav0"}
        killed_nodes = []
        def pid_probe(node):
            return fake_pid
        def killer(node):
            killed_nodes.append(node)
            return True
        record = execute_dropout(str(ex_runroot), ex_cfg, config, sim_s=65.0,
                                 pid_probe=pid_probe, killer=killer)
        assert record["vehicle"] == "uav0"
        assert record["mode"] == "control_chain"
        assert record["sim_s"] == 65.0
        assert record["pids"] == {"/exploration_node_1": fake_pid,
                                  "/traj_server_1": fake_pid}
        assert record["reason"] == "intentional_dropout"
        assert record["killed_nodes"] == ["/exploration_node_1", "/traj_server_1"]
        assert record["missing_nodes"] == []
        assert record["record"] == "fleet/dropout.json"
        # Verify file written
        dropout_path = ex_runroot / "fleet" / "dropout.json"
        assert dropout_path.is_file()
        saved = json.loads(dropout_path.read_text(encoding="utf-8"))
        assert saved["vehicle"] == "uav0"
        assert saved["reason"] == "intentional_dropout"

    # monitor_until: dropout trigger via injected probes
    with tempfile.TemporaryDirectory() as tempdir:
        mu_runroot = Path(tempdir) / "RUN-monitor"
        mu_runroot.mkdir()
        mu_active = {"runroot": str(mu_runroot),
                     "processes": {"test": {"pid": str(os.getpid())}}}
        # Inject a sim_time_probe that returns 0, then 30, then 70, then 80
        sim_times = iter([0.0, 30.0, 70.0, 80.0, 100.0])
        def sim_probe():
            return next(sim_times)
        dropout_calls = []
        def dropout_executor(cfg, sim_s):
            dropout_calls.append((cfg, sim_s))
        # monotonic advances by 1 per call, sleep is no-op
        mu_time = [0.0]
        def mu_monotonic():
            val = mu_time[0]
            mu_time[0] += 1.0
            return val
        def mu_sleep(_s):
            pass
        # duration_sim_s = 100, trigger_sim_s = 60 (relative to start_sim_s)
        mu_dcfg = {**valid_dropout, "enabled": True, "trigger_sim_s": 60}
        reason = monitor_until(mu_active, 100, dropout_config=mu_dcfg, config=config,
                               sim_time_probe=sim_probe, dropout_executor=dropout_executor,
                               monotonic=mu_monotonic, sleep=mu_sleep)
        # First success at sim_times[0] = 0.0 → start_sim_s = 0.0
        # sim_times[1] = 30.0 → 30 - 0 < 60, no trigger
        # sim_times[2] = 70.0 → 70 - 0 >= 60, TRIGGER → dropout_calls = [(config, 70.0)]
        # sim_times[3] = 80.0 → trigger already fired, no repeat
        # sim_times[4] = 100.0 → 100 - 0 >= 100, duration_complete
        assert reason == "duration_complete"
        assert len(dropout_calls) == 1
        assert dropout_calls[0][1] == 70.0  # sim_s at trigger

    # monitor_until: dropout disabled — no trigger
    with tempfile.TemporaryDirectory() as tempdir:
        mu_runroot2 = Path(tempdir) / "RUN-nodrop"
        mu_runroot2.mkdir()
        mu_active2 = {"runroot": str(mu_runroot2),
                      "processes": {"test": {"pid": str(os.getpid())}}}
        sim_times2 = iter([0.0, 50.0, 100.0])
        def sim_probe2():
            return next(sim_times2)
        dropout_calls2 = []
        def dropout_executor2(cfg, sim_s):
            dropout_calls2.append((cfg, sim_s))
        mu_time2 = [0.0]
        def mu_monotonic2():
            val = mu_time2[0]
            mu_time2[0] += 1.0
            return val
        disabled_dcfg = {**valid_dropout, "enabled": False, "trigger_sim_s": 30}
        reason2 = monitor_until(mu_active2, 100, dropout_config=disabled_dcfg, config=config,
                                sim_time_probe=sim_probe2, dropout_executor=dropout_executor2,
                                monotonic=mu_monotonic2, sleep=mu_sleep)
        assert reason2 == "duration_complete"
        assert len(dropout_calls2) == 0  # no trigger when disabled

    # monitor_until: one-shot — no repeat if sim time keeps advancing
    with tempfile.TemporaryDirectory() as tempdir:
        mu_runroot3 = Path(tempdir) / "RUN-oneshot"
        mu_runroot3.mkdir()
        mu_active3 = {"runroot": str(mu_runroot3),
                      "processes": {"test": {"pid": str(os.getpid())}}}
        sim_times3 = iter([0.0, 60.0, 90.0, 120.0, 150.0])
        def sim_probe3():
            return next(sim_times3)
        dropout_calls3 = []
        def dropout_executor3(cfg, sim_s):
            dropout_calls3.append((cfg, sim_s))
        mu_time3 = [0.0]
        def mu_monotonic3():
            val = mu_time3[0]
            mu_time3[0] += 1.0
            return val
        reason3 = monitor_until(mu_active3, 150, dropout_config=mu_dcfg, config=config,
                                sim_time_probe=sim_probe3, dropout_executor=dropout_executor3,
                                monotonic=mu_monotonic3, sleep=mu_sleep)
        assert reason3 == "duration_complete"
        assert len(dropout_calls3) == 1  # exactly one trigger
        assert dropout_calls3[0][1] == 60.0  # at first threshold crossing

    # monitor_until: backward compat — no dropout_config, no dropout_executor called
    with tempfile.TemporaryDirectory() as tempdir:
        mu_runroot4 = Path(tempdir) / "RUN-backward"
        mu_runroot4.mkdir()
        mu_active4 = {"runroot": str(mu_runroot4),
                      "processes": {"test": {"pid": str(os.getpid())}}}
        sim_times4 = iter([0.0, 60.0, 120.0])
        def sim_probe4():
            return next(sim_times4)
        mu_time4 = [0.0]
        def mu_monotonic4():
            val = mu_time4[0]
            mu_time4[0] += 1.0
            return val
        reason4 = monitor_until(mu_active4, 120, monotonic=mu_monotonic4, sleep=mu_sleep,
                                sim_time_probe=sim_probe4)
        assert reason4 == "duration_complete"  # no dropout, no crash

    print("two_uav_runner self-test: PASS")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", nargs="?",
                        choices=("preflight", "launch", "monitor", "stop", "collect"))
    parser.add_argument("--manifest", default=str(
        ROOT / "experiments/manifests/2uav_smoke.yaml"))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.action:
        parser.error("action is required unless --self-test is used")
    manifest_path = Path(args.manifest).resolve()
    allowed = (ROOT / "experiments/manifests/2uav_smoke.yaml").resolve()
    if manifest_path != allowed:
        parser.error("only experiments/manifests/2uav_smoke.yaml is allowed")
    try:
        if args.action == "preflight":
            return action_preflight(manifest_path)
        if args.action == "launch":
            return action_launch(manifest_path)
        if args.action == "monitor":
            return action_monitor()
        if args.action == "stop":
            return action_stop()
        return action_collect()
    except Exception as exc:
        print("two_uav_runner: REFUSED: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
