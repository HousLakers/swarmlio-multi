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
import subprocess
import sys
import tempfile
import time

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


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_yaml(path):
    with open(path, encoding="utf-8") as stream:
        return yaml.safe_load(stream)


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
    return environment


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


def readiness_state(processes, payload_seen, observed_nodes=(), required_nodes=()):
    """Pure short-poll decision used by payload and bridge readiness gates."""
    exited = process_exit_reason(processes)
    if exited:
        return "failed", exited
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
    try:
        result = subprocess.run(argv, env=environment, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, timeout=3)
    except subprocess.TimeoutExpired:
        return set()
    return set(result.stdout.splitlines()) if result.returncode == 0 else set()


def wait_readiness(runroot, label, timeout_s, processes, payload_probe, required_nodes=(),
                   node_probe=None, monotonic=time.monotonic, sleep=time.sleep):
    """Poll payload/nodes and every already-started Popen in the same gate."""
    node_probe = node_probe or (lambda: ros_node_names(runroot))

    def sample():
        # Read nodes after payload: a bridge cannot pass on a pre-probe snapshot.
        payload_seen = payload_probe()
        nodes = node_probe() if required_nodes else set()
        return readiness_state(processes, payload_seen, nodes, required_nodes)

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
    try:
        for name, argv in specs:
            log = open(runroot / "logs" / (name + ".log"), "wb")
            process = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True,
                                       env=ros_subprocess_environment(runroot))
            processes[name] = {"pid": process.pid, "argv": argv}
            live_processes[name] = process
            if name == "gazebo":
                wait_readiness(runroot, "clock", 120, live_processes,
                               lambda: topic_payload_seen(runroot, "/clock"))
            elif name == "gt_mapper":
                config = load_yaml(CONFIG)
                for vehicle in config["vehicles"]:
                    for key in ("raw_cloud", "mavros_odom", "registered_cloud", "registered_odom"):
                        wait_readiness(
                            runroot, "%s:%s" % (vehicle["name"], key), 120, live_processes,
                            lambda topic=vehicle["topics"][key]: topic_payload_seen(runroot, topic))
            elif name == "bridges":
                wait_readiness(runroot, "bridges", 60, live_processes, lambda: True,
                               required_nodes=("/px4_bridge_1", "/px4_bridge_2"))
            elif name == "racer":
                for vehicle in load_yaml(CONFIG)["vehicles"]:
                    wait_readiness(
                        runroot, "%s:frontier" % vehicle["name"], 180, live_processes,
                        lambda topic=vehicle["topics"]["frontier"]: topic_payload_seen(runroot, topic),
                        required_nodes=("/px4_bridge_1", "/px4_bridge_2"))
    except Exception:
        stop_active({"processes": processes})
        raise
    active = {"runroot": str(runroot), "processes": processes,
              "ros_environment": runroot_ros_environment(runroot),
              "manifest": str(manifest_path), "started_utc": dt.datetime.now(
                  dt.timezone.utc).isoformat()}
    ACTIVE.write_text(json.dumps(active, indent=2) + "\n", encoding="utf-8")
    return active


def load_active():
    if not ACTIVE.is_file():
        raise RuntimeError("no active 2-UAV lifecycle")
    active = json.loads(ACTIVE.read_text(encoding="utf-8"))
    active["ros_environment"] = active_ros_environment(active)
    return active


def stop_active(active):
    outcomes = {}
    for name, spec in reversed(list(active["processes"].items())):
        pid = int(spec["pid"])
        try:
            os.killpg(pid, signal.SIGTERM)
            outcomes[name] = "sigterm"
        except ProcessLookupError:
            outcomes[name] = "already_exited"
    time.sleep(2.0)
    for name, spec in reversed(list(active["processes"].items())):
        pid = int(spec["pid"])
        try:
            os.killpg(pid, signal.SIGKILL)
            outcomes[name] += "+sigkill"
        except ProcessLookupError:
            pass
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


def monitor_until(active, duration_sim_s):
    runroot = Path(active["runroot"])
    start_sim_s = None
    wall_deadline = time.monotonic() + max(600.0, duration_sim_s * 10.0)
    while time.monotonic() < wall_deadline:
        abort_file = runroot / "fleet" / "abort.request"
        if abort_file.is_file():
            return "abort_requested"
        for name, spec in active["processes"].items():
            try:
                os.kill(int(spec["pid"]), 0)
            except ProcessLookupError:
                return "process_death:" + name
        try:
            current_sim_s = sim_time_s(runroot)
        except (OSError, ValueError, subprocess.SubprocessError):
            time.sleep(1.0)
            continue
        if start_sim_s is None:
            start_sim_s = current_sim_s
        if current_sim_s - start_sim_s >= duration_sim_s:
            return "duration_complete"
        time.sleep(1.0)
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
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
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


def final_safety_result(runroot):
    runroot = Path(runroot)
    if (runroot / "fleet" / "abort.request").is_file():
        return False, "abort.request exists"
    try:
        fleet = json.loads((runroot / "fleet" / "metrics.json").read_text(encoding="utf-8"))
        vehicles = [json.loads((runroot / name / "metrics.json").read_text(
            encoding="utf-8")) for name in ("uav0", "uav1")]
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return False, "missing final metrics: %s" % exc
    return final_metrics_valid(fleet, vehicles)


def final_metrics_valid(fleet, vehicles):
    if fleet.get("abort_reasons") or not fleet.get("telemetry_completeness"):
        return False, "fleet safety metrics failed"
    if any(report.get("crash") or not report.get("telemetry_complete") or
           not report.get("coverage", {}).get("available") for report in vehicles):
        return False, "per-UAV safety metrics failed"
    return True, "final safety metrics complete"


def action_preflight(manifest_path):
    _manifest, approval_bytes, approval_digest = approval_guard("preflight", manifest_path)
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
        {"passed": passed, "checks": checks}, indent=2, sort_keys=True) + "\n",
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
            report = {"passed": all(item["ok"] for item in checks), "checks": checks}
            (runroot / "live_preflight.json").write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            if not report["passed"]:
                raise RuntimeError("live preflight failed; smoke trigger withheld")
            config = load_yaml(CONFIG)
            soak_ok, soak_detail = watchdog_soak(
                runroot, config["safety_contract"]["telemetry"]["preflight_soak_s"])
            report["checks"].append({"name": "live.watchdog_soak", "ok": soak_ok,
                                     "detail": soak_detail})
            report["passed"] = all(item["ok"] for item in report["checks"])
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
            reason = monitor_until(active, int(manifest["duration_sim_s"]))
        outcomes = stop_active(active)
        stopped = True
        ACTIVE.unlink(missing_ok=True)
    finally:
        if not stopped:
            stop_active(active)
            ACTIVE.unlink(missing_ok=True)
    metrics_ready = wait_final_metrics(runroot)
    safe, safety_detail = final_safety_result(runroot) if metrics_ready else (
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
                    "coverage": {"available": True}}
    assert final_metrics_valid({"abort_reasons": [], "telemetry_completeness": True},
                               [good_vehicle, good_vehicle])[0]
    assert not final_metrics_valid({"abort_reasons": ["crash:uav0"],
                                    "telemetry_completeness": True},
                                   [good_vehicle, good_vehicle])[0]
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
