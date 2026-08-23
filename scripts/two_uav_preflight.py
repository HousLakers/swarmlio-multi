#!/usr/bin/env python3
"""Fail-closed static/live evidence gate for the frozen 2-UAV contract."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

import yaml


ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = "REPLACE_WITH_VERIFIED_2UAV_LAUNCH_COMMAND"
FROZEN_RUNTIME = {
    "sdf_map/resolution": "0.10",
    "sdf_map/obstacles_inflation": "0.35",
    "sdf_map/max_ray_length": "20.0",
    "map_ros/depth_filter_maxdist": "20.5",
    "map_ros/all_map_publish_period": "2.0",
    "planner_escape/v2_progress_guard_enabled": "false",
    "trajectory_safety/global_postplan_guard_enabled": "false",
    "trajectory_safety/reject_unknown": "false",
    "perception_utils/max_dist": "20.0",
    "perception_utils/horizontal_model": "omnidirectional",
}
ENVIRONMENT_RUNTIME = {
    "sdf_map/map_size_x": "50.0",
    "sdf_map/map_size_y": "50.0",
    "sdf_map/box_min_x": "-24.5",
    "sdf_map/box_min_y": "-24.5",
    "sdf_map/box_max_x": "24.5",
    "sdf_map/box_max_y": "24.5",
}
EXPECTED_RUNTIME = {**FROZEN_RUNTIME, **ENVIRONMENT_RUNTIME}
LIVE_CLI_TIMEOUT_S = 15
LIVE_CLI_ATTEMPTS = 3
LIVE_CLI_BACKOFF_S = 0.5
LIVE_CLI_WALL_CAP_S = 50.0


def load_yaml(path):
    with open(path, encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_value(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()


def check(condition, name, detail, checks):
    checks.append({"name": name, "ok": bool(condition), "detail": str(detail)})


def runtime_value_matches(actual, expected):
    """rosparam normalizes YAML numeric output (0.10 -> 0.1); compare numerically."""
    try:
        return float(actual) == float(expected)
    except (TypeError, ValueError):
        return actual.strip().lower() == expected.strip().lower()


def unique(values):
    return len(values) == len(set(values))


def planner_params(path):
    root = ET.parse(path).getroot()
    return {node.attrib.get("name"): node.attrib.get("value")
            for node in root.iter("param") if node.attrib.get("name")}


def named_values(element, tag):
    return {node.attrib.get("name"): node.attrib.get("value")
            for node in element.iter(tag) if node.attrib.get("name")}


def static_checks(config_path, manifest_path):
    config_path = Path(config_path).resolve()
    manifest_path = Path(manifest_path).resolve()
    config = load_yaml(config_path)
    manifest = load_yaml(manifest_path)
    checks = []
    uav_count = config.get("uav_count")
    vehicles = config.get("vehicles", [])
    check(isinstance(uav_count, int) and not isinstance(uav_count, bool) and
          uav_count >= 2 and uav_count == len(vehicles),
          "contract.uav_count", {"uav_count": uav_count, "vehicles": len(vehicles)}, checks)
    launch_prefix = "%duav" % uav_count
    for field in ("namespace", "racer_id", "mavlink_system_id", "initial_position",
                  "log_subdir"):
        values = [json.dumps(v.get(field), sort_keys=True) for v in vehicles]
        check(unique(values), "isolation." + field, values, checks)
    ports = [value for vehicle in vehicles for value in vehicle.get("ports", {}).values()]
    check(unique(ports), "isolation.ports", ports, checks)
    children = [vehicle.get("frames", {}).get("child") for vehicle in vehicles]
    check(unique(children), "isolation.tf_child", children, checks)
    topics = [topic for vehicle in vehicles for topic in vehicle.get("topics", {}).values()]
    check(unique(topics), "isolation.vehicle_topics", topics, checks)
    check(config.get("clock") == {"topic": "/clock", "publishers": 1, "use_sim_time": True},
          "clock.contract", config.get("clock"), checks)
    check(config.get("registration_source") == "gt", "registration_source",
          config.get("registration_source"), checks)

    paths = config["paths"]
    frozen = config["frozen"]
    environment = config.get("environment", {})
    platform = Path(paths["platform_repository"])
    single = Path(paths["single_repository"])
    for label, repo, expected in (
            ("platform", platform, frozen["platform_commit"]),
            ("single", single, frozen["single_commit"])):
        try:
            head = git_value(repo, "rev-parse", "HEAD")
            tracked = git_value(repo, "status", "--porcelain", "--untracked-files=no")
            check(head == expected, "source.%s_commit" % label, head, checks)
            check(not tracked, "source.%s_tracked_clean" % label,
                  tracked or "clean", checks)
        except (OSError, subprocess.CalledProcessError) as exc:
            check(False, "source.%s_git" % label, exc, checks)
    manifest_hash_path = single / frozen["overlay_manifest"]
    installer_path = single / frozen["overlay_installer"]
    for label, path, expected in (
            ("overlay_manifest", manifest_hash_path, frozen["overlay_manifest_sha256"]),
            ("overlay_installer", installer_path, frozen["overlay_installer_sha256"])):
        actual = sha256(path) if path.is_file() else "missing"
        check(actual == expected, "source.%s_sha256" % label, actual, checks)

    world_path = Path(paths.get("world", ""))
    baseline_path = Path(environment.get("baseline_manifest", ""))
    world_actual = sha256(world_path) if world_path.is_file() else "missing"
    baseline_actual = sha256(baseline_path) if baseline_path.is_file() else "missing"
    check(environment.get("baseline_id") == "racer_outdoor_50x50_v1",
          "environment.baseline_id", environment.get("baseline_id"), checks)
    check(world_actual == environment.get("world_sha256"),
          "environment.world_sha256", world_actual, checks)
    check(baseline_actual == environment.get("baseline_manifest_sha256"),
          "environment.manifest_sha256", baseline_actual, checks)
    try:
        baseline = load_yaml(baseline_path)
        check(baseline.get("baseline_id") == environment.get("baseline_id"),
              "environment.manifest_id", baseline.get("baseline_id"), checks)
        check(baseline.get("world", {}).get("sha256") == world_actual,
              "environment.manifest_world_sha256",
              baseline.get("world", {}).get("sha256"), checks)
        check(baseline.get("geometry", {}).get("planner_map_size_m") ==
              environment.get("map_size_m"), "environment.map_size",
              baseline.get("geometry", {}).get("planner_map_size_m"), checks)
    except (OSError, TypeError, yaml.YAMLError) as exc:
        check(False, "environment.manifest", exc, checks)
    roots = {
        "racer": Path(paths["racer_workspace"]) / "src/RACER",
        "swarm": Path(paths["swarm_workspace"]) / "src/Swarm-LIO2",
        "auto": Path("/home/houslakers/auto_tune_racer"),
    }
    installed_mismatches = []
    installed_count = 0
    if manifest_hash_path.is_file():
        for raw_line in manifest_hash_path.read_text(encoding="utf-8").splitlines():
            if not raw_line or raw_line.startswith("#"):
                continue
            expected, _mode, _source, root_name, target = raw_line.split("|", 4)
            installed_count += 1
            target_path = roots[root_name] / target
            actual = sha256(target_path) if target_path.is_file() else "missing"
            if actual != expected:
                installed_mismatches.append({"path": str(target_path), "actual": actual,
                                             "expected": expected})
    check(installed_count == 21 and not installed_mismatches,
          "source.overlay_installed_21_of_21",
          installed_mismatches or "21/21 CURRENT", checks)

    planner = (Path(paths["racer_workspace"]) /
               "src/RACER/swarm_exploration/exploration_manager/launch/single_drone_planner.xml")
    try:
        params = planner_params(planner)
        for name, expected in FROZEN_RUNTIME.items():
            check(params.get(name) == expected, "frozen_param." + name,
                  params.get(name), checks)
    except (OSError, ET.ParseError) as exc:
        check(False, "frozen_param.planner_xml", exc, checks)

    for relpath in ("launch/%s_px4_sitl.launch" % launch_prefix,
                    "launch/%s_bridges.launch" % launch_prefix,
                    "launch/%s_racer.launch" % launch_prefix):
        path = ROOT / relpath
        try:
            ET.parse(path)
            check(True, "launch.xml." + relpath, "well-formed", checks)
        except (OSError, ET.ParseError) as exc:
            check(False, "launch.xml." + relpath, exc, checks)
    try:
        bridge_root = ET.parse(ROOT / ("launch/%s_bridges.launch" % launch_prefix)).getroot()
        bridge_nodes = {node.attrib["name"]: named_values(node, "param")
                        for node in bridge_root.findall("node")}
        racer_root = ET.parse(ROOT / ("launch/%s_racer.launch" % launch_prefix)).getroot()
        racer_includes = [named_values(node, "arg")
                          for node in racer_root.findall("include")]
        px4_root = ET.parse(ROOT / ("launch/%s_px4_sitl.launch" % launch_prefix)).getroot()
        px4_world = px4_root.find("arg[@name='world']")
        check(px4_world is not None and px4_world.attrib.get("default") == str(world_path),
              "environment.px4_world", None if px4_world is None else
              px4_world.attrib.get("default"), checks)
        racer_args = {name: racer_root.find("arg[@name='%s']" % name).attrib.get("default")
                      for name in ("map_size_x", "map_size_y", "map_size_z")}
        check(racer_args == {"map_size_x": "50.0", "map_size_y": "50.0",
                             "map_size_z": "3.0"},
              "environment.racer_map_size", racer_args, checks)
        racer_params = named_values(racer_root, "param")
        expected_bounds = {
            "/exploration_node_%s/sdf_map/%s" % (spec["racer_id"], bound): value
            for spec in vehicles
            for bound, value in (("box_min_x", "-24.5"),
                                 ("box_min_y", "-24.5"),
                                 ("box_max_x", "24.5"),
                                 ("box_max_y", "24.5"))
        }
        check(all(racer_params.get(name) == value
                  for name, value in expected_bounds.items()),
              "environment.racer_box_bounds", racer_params, checks)
        px4_groups = {}
        for group in px4_root.findall("group"):
            values = named_values(group, "arg")
            direct_id = group.find("arg[@name='ID']")
            if direct_id is not None:
                values["ID"] = direct_id.attrib.get("value")
            px4_groups[group.attrib["ns"]] = values
        for spec in vehicles:
            racer_id = str(spec["racer_id"])
            bridge = bridge_nodes.get("px4_bridge_" + racer_id, {})
            check(bridge.get("drone_id") == racer_id and
                  bridge.get("mavros_ns") == spec["namespace"],
                  "wiring.%s_bridge" % spec["name"], bridge, checks)
            racer = next((item for item in racer_includes
                          if item.get("drone_id") == racer_id), {})
            check(racer.get("drone_num") == str(uav_count),
                  "wiring.%s_racer" % spec["name"], racer, checks)
            px4 = px4_groups.get(spec["name"], {})
            expected_system_index = str(spec["mavlink_system_id"] - 1)
            check(px4.get("ID") == expected_system_index and
                  int(px4.get("mavlink_udp_port", -1)) == spec["ports"]["mavlink_udp"] and
                  int(px4.get("mavlink_tcp_port", -1)) == spec["ports"]["mavlink_tcp"] and
                  int(px4.get("mavlink_cam_udp_port", -1)) == spec["ports"]["camera_udp"],
                  "wiring.%s_px4" % spec["name"], px4, checks)
    except (OSError, ET.ParseError, TypeError, ValueError) as exc:
        check(False, "wiring.launch_contract", exc, checks)
    check(manifest.get("approval_status") ==
          "blocked_pending_verified_launch_and_preflight",
          "manifest.approval_status_candidate", manifest.get("approval_status"), checks)
    launch_command = manifest.get("launch_command", "")
    check(bool(launch_command) and PLACEHOLDER not in launch_command,
          "manifest.launch_command", launch_command, checks)
    whitelist = manifest.get("command_whitelist", [])
    check(isinstance(whitelist, list) and len(whitelist) == 5,
          "manifest.command_whitelist", whitelist, checks)
    check("runtime_parameter_readback" in manifest.get("required_preflight", []),
          "manifest.parameter_readback_gate", manifest.get("required_preflight"), checks)
    approval_contract_path = ROOT / manifest.get("approval_contract", "")
    try:
        approval_contract = load_yaml(approval_contract_path)
        check(approval_contract.get("schema_version") == 1 and
              approval_contract.get("approval_package") ==
              ("state/%s_approval.yaml" % launch_prefix) and
              approval_contract.get("manifest_status_must_remain") ==
              "blocked_pending_verified_launch_and_preflight" and
              approval_contract.get("issued_by_must_be") == "sol" and
              approval_contract.get("max_uses") == 1,
              "approval.immutable_package_contract", approval_contract, checks)
    except (OSError, TypeError, yaml.YAMLError) as exc:
        check(False, "approval.immutable_package_contract", exc, checks)
    manifest_environment = manifest.get("environment_baseline", {})
    check(manifest_environment.get("id") == environment.get("baseline_id") and
          manifest_environment.get("manifest_sha256") == baseline_actual and
          manifest_environment.get("world_sha256") == world_actual and
          manifest_environment.get("runtime_validation") == "not_run",
          "manifest.environment_baseline", manifest_environment, checks)
    telemetry_contract = config.get("safety_contract", {}).get("telemetry", {})
    metrics_contract = config.get("safety_contract", {}).get("metrics", {})
    check(telemetry_contract.get("preflight_soak_s", 0) >=
          telemetry_contract.get("startup_grace_s", 0) and
          telemetry_contract.get("tf_freshness_s", 0) > 0 and
          telemetry_contract.get("occupancy_contract") == "startup_presence" and
          metrics_contract.get("coverage_missing_policy") ==
          "abort_after_startup_grace" and
          metrics_contract.get("coverage_coalesce_sim_s") == 2.0 and
          metrics_contract.get("resource_sample_wall_s") == 1.0 and
          metrics_contract.get("resource_startup_mem_available_gib") == 8 and
          isinstance(metrics_contract.get("resource_running_mem_available_gib"), int) and
          1 <= metrics_contract.get("resource_running_mem_available_gib") <= 8 and
          metrics_contract.get("resource_startup_load1_max") == 10.0 and
          metrics_contract.get("resource_swap_activity") == "abort",
          "safety.watchdog_contract", {"telemetry": telemetry_contract,
                                         "metrics": metrics_contract}, checks)

    source_manifest = ROOT / ("config/%s_source_hashes.sha256" % launch_prefix)
    source_manifest_mismatches = []
    if source_manifest.is_file():
        for raw_line in source_manifest.read_text(encoding="utf-8").splitlines():
            if not raw_line or raw_line.startswith("#"):
                continue
            expected, relative = raw_line.split(None, 1)
            relative = relative.lstrip(" *")
            path = ROOT / relative
            actual = sha256(path) if path.is_file() else "missing"
            if actual != expected:
                source_manifest_mismatches.append({
                    "path": relative, "actual": actual, "expected": expected})
    else:
        source_manifest_mismatches.append({"path": str(source_manifest),
                                           "actual": "missing"})
    check(not source_manifest_mismatches, "source.multi_hash_manifest",
          source_manifest_mismatches or "all entries match", checks)

    source_files = [
        ROOT / ("config/%s_static.yaml" % launch_prefix),
        ROOT / ("config/%s_approval_contract.yaml" % launch_prefix),
        ROOT / ("launch/%s_px4_sitl.launch" % launch_prefix),
        ROOT / ("launch/%s_bridges.launch" % launch_prefix),
        ROOT / ("launch/%s_racer.launch" % launch_prefix),
        ROOT / "scripts/two_uav_gt_mapper.py",
        ROOT / "scripts/two_uav_preflight.py",
        ROOT / "scripts/two_uav_collector.py",
        ROOT / "scripts/two_uav_runner.py",
        ROOT / ("scripts/validate_%s_outdoor_world.py" % launch_prefix),
        ROOT / ("worlds/%s_outdoor_50x50_v1.world" % launch_prefix),
        ROOT / ("config/%s_source_hashes.sha256" % launch_prefix),
        Path(manifest_path),
    ]
    hashes = {str(path.relative_to(ROOT)): sha256(path)
              for path in source_files if path.is_file()}
    return checks, hashes


def readonly_cli_retry(argv, execute=subprocess.run, monotonic=time.monotonic,
                       sleep=time.sleep):
    """Run a fixed read-only ROS CLI argv with bounded, auditable retries."""
    started = monotonic()
    attempts = []
    for number in range(1, LIVE_CLI_ATTEMPTS + 1):
        if monotonic() - started >= LIVE_CLI_WALL_CAP_S:
            break
        try:
            result = execute(argv, check=False, text=True, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, timeout=LIVE_CLI_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            attempts.append({"attempt": number, "status": "timeout"})
        else:
            if result.returncode == 0:
                attempts.append({"attempt": number, "status": "success"})
                return {"ok": True, "argv": list(argv), "stdout": result.stdout.strip(),
                        "attempts": attempts}
            attempts.append({"attempt": number, "status": "error",
                             "returncode": result.returncode,
                             "stderr": result.stderr.strip()})
        if number < LIVE_CLI_ATTEMPTS and monotonic() - started < LIVE_CLI_WALL_CAP_S:
            sleep(LIVE_CLI_BACKOFF_S)
    return {"ok": False, "argv": list(argv), "stdout": "", "attempts": attempts}


def ros_output(*argv):
    result = readonly_cli_retry(list(argv))
    if not result["ok"]:
        raise RuntimeError("live CLI failed: " + json.dumps(result, sort_keys=True))
    return result["stdout"]


def tf_echo_argv():
    """Sample complete TFMessage payloads; transforms is the message array."""
    return ["rostopic", "echo", "-n", "10", "/tf"]


def parse_tf_parent_sets(output):
    """Return every observed parent for each child in rostopic TF YAML output."""
    if isinstance(output, bytes):
        output = output.decode(errors="replace")
    output = output or ""
    parents = re.findall(r"^\s*frame_id:\s*['\"]?([^'\"\s]+)", output,
                         re.MULTILINE)
    children = re.findall(r"^\s*child_frame_id:\s*['\"]?([^'\"\s]+)", output,
                          re.MULTILINE)
    result = {}
    for parent, child in zip(parents, children):
        result.setdefault(child, set()).add(parent)
    return result


def tf_parent_sets():
    try:
        result = subprocess.run(
            tf_echo_argv(), check=False, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=5)
        output = result.stdout
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
    return parse_tf_parent_sets(output)


def expected_tf_contract(parents_by_child, vehicles):
    """Reject absent, extra, or wrong parents instead of treating empty TF as clean."""
    expected = {vehicle["frames"]["child"]: vehicle["frames"]["parent"]
                for vehicle in vehicles}
    failures = {}
    for child, parent in expected.items():
        observed = parents_by_child.get(child, set())
        if observed != {parent}:
            failures[child] = sorted(observed)
    return not failures, failures or "all expected TF edges observed"


def topic_has_payload(topic, timeout_s=12):
    try:
        result = subprocess.run(
            ["rostopic", "echo", "-n", "1", "--noarr", topic], check=False,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return False, "timeout"
    return payload_observed(result.returncode, result.stdout, result.stderr)


def payload_observed(returncode, stdout, stderr=""):
    """A visible topic still fails until echo returns a non-empty payload."""
    ok = returncode == 0 and bool(stdout.strip())
    return ok, "payload" if ok else "no payload: " + stderr.strip()


def live_checks(config_path, runroot):
    config = load_yaml(config_path)
    checks = []
    topics = set(ros_output("rostopic", "list").splitlines())
    required = {config["clock"]["topic"]}
    for vehicle in config["vehicles"]:
        required.update(vehicle["topics"].values())
    missing = sorted(required - topics)
    check(not missing, "live.required_topics", missing or "all present", checks)
    clock_info = ros_output("rostopic", "info", "/clock")
    publisher_block = clock_info.split("Subscribers:", 1)[0]
    publishers = len(re.findall(r"^ \* /", publisher_block, re.MULTILINE))
    check(publishers == 1, "live.clock_single_publisher", publishers, checks)
    use_sim_time = ros_output("rosparam", "get", "/use_sim_time").lower()
    check(use_sim_time == "true", "live.use_sim_time", use_sim_time, checks)
    tf_parents = tf_parent_sets()
    tf_ok, tf_detail = expected_tf_contract(tf_parents, config["vehicles"])
    check(tf_ok, "live.tf_expected_unique_dynamic_edges", tf_detail, checks)
    for vehicle in config["vehicles"]:
        for key in ("raw_cloud", "mavros_odom", "registered_cloud", "registered_odom", "frontier"):
            payload_ok, payload_detail = topic_has_payload(vehicle["topics"][key])
            check(payload_ok, "live.payload.%s.%s" % (vehicle["name"], key),
                  payload_detail, checks)
    for vehicle in config["vehicles"]:
        node = "/exploration_node_%s" % vehicle["racer_id"]
        for name, expected in EXPECTED_RUNTIME.items():
            actual = ros_output("rosparam", "get", node + "/" + name)
            check(runtime_value_matches(actual, expected), "readback.%s.%s"
                  % (vehicle["name"], name), actual, checks)
        logdir = Path(runroot) / vehicle["log_subdir"]
        check(logdir.is_dir(), "logdir.%s" % vehicle["name"], logdir, checks)
    check((Path(runroot) / config["fleet"]["log_subdir"]).is_dir(),
          "logdir.fleet", Path(runroot) / config["fleet"]["log_subdir"], checks)
    profile = Path(runroot) / "resource_usage.jsonl"
    try:
        sample = json.loads(profile.read_text(encoding="utf-8").splitlines()[0])
        profile_ok = resource_profile_schema_valid(sample)
        profile_detail = "schema complete" if profile_ok else "schema incomplete"
    except (OSError, ValueError, json.JSONDecodeError, IndexError):
        profile_ok, profile_detail = False, "resource profile missing or unreadable"
    check(profile_ok, "live.resource_profile", profile_detail, checks)
    return checks


def resource_profile_schema_valid(sample):
    return (isinstance(sample, dict) and
            isinstance(sample.get("wall_monotonic_s"), (int, float)) and
            "wall_delta_s" in sample and "sim_s" in sample and
            isinstance(sample.get("sim_evidence_missing"), bool) and
            isinstance(sample.get("clk_tck"), int) and sample["clk_tck"] > 0 and
            isinstance(sample.get("roles"), dict) and isinstance(sample.get("system"), dict) and
            (sample["sim_s"] is not None or sample["sim_evidence_missing"]))


def self_test():
    assert runtime_value_matches("0.1", "0.10")
    assert runtime_value_matches("20", "20.0")
    assert runtime_value_matches("omnidirectional", "omnidirectional")
    assert runtime_value_matches("TRUE", "true")
    assert not runtime_value_matches("0.2", "0.10")
    assert not runtime_value_matches("omni", "omnidirectional")

    class Result:
        def __init__(self, returncode=0, stdout="", stderr=""):
            self.returncode, self.stdout, self.stderr = returncode, stdout, stderr

    def scripted(outcomes):
        queue = list(outcomes)
        def execute(_argv, **_kwargs):
            item = queue.pop(0)
            if item == "timeout":
                raise subprocess.TimeoutExpired("rosparam", LIVE_CLI_TIMEOUT_S)
            return item
        return execute

    argv = ["rosparam", "get", "/uav0/sdf_map/obstacles_inflation"]
    timeout_then_success = readonly_cli_retry(
        argv, execute=scripted(["timeout", Result(stdout="0.35\n")]), sleep=lambda _: None)
    assert timeout_then_success["ok"] and [item["status"] for item in
                                             timeout_then_success["attempts"]] == ["timeout", "success"]
    error_then_success = readonly_cli_retry(
        argv, execute=scripted([Result(1, stderr="busy"), Result(stdout="0.35\n")]),
        sleep=lambda _: None)
    assert error_then_success["ok"] and error_then_success["attempts"][0]["status"] == "error"
    all_timeout = readonly_cli_retry(argv, execute=scripted(["timeout"] * LIVE_CLI_ATTEMPTS),
                                     sleep=lambda _: None)
    assert not all_timeout["ok"] and {item["status"] for item in all_timeout["attempts"]} == {"timeout"}
    all_error = readonly_cli_retry(argv, execute=scripted([Result(2, stderr="down")] * LIVE_CLI_ATTEMPTS),
                                   sleep=lambda _: None)
    assert not all_error["ok"] and {item["status"] for item in all_error["attempts"]} == {"error"}
    assert timeout_then_success["stdout"] == "0.35"
    assert timeout_then_success["stdout"] != "0.40"
    clock = [0.0]
    def wall_clock(): return clock[0]
    def advance(_argv, **_kwargs):
        clock[0] += LIVE_CLI_WALL_CAP_S
        return Result(1, stderr="late")
    capped = readonly_cli_retry(argv, execute=advance, monotonic=wall_clock, sleep=lambda _: None)
    assert not capped["ok"] and len(capped["attempts"]) == 1
    vehicles = [
        {"frames": {"parent": "world", "child": "uav0/base_link"}},
        {"frames": {"parent": "world", "child": "uav1/base_link"}},
    ]
    tf_fixture = """transforms:
- header:
    seq: 1
    stamp: {secs: 1, nsecs: 0}
    frame_id: world
  child_frame_id: uav0/base_link
  transform: {}
- header:
    seq: 2
    stamp: {secs: 1, nsecs: 0}
    frame_id: world
  child_frame_id: uav1/base_link
  transform: {}
---
"""
    parsed = parse_tf_parent_sets(tf_fixture)
    assert parsed == {"uav0/base_link": {"world"},
                      "uav1/base_link": {"world"}}
    assert expected_tf_contract(parsed, vehicles)[0]
    assert not expected_tf_contract(parse_tf_parent_sets(""), vehicles)[0]
    missing_child = parse_tf_parent_sets("""transforms:
- header:
    frame_id: world
  child_frame_id: uav0/base_link
  transform: {}
---
""")
    assert not expected_tf_contract(missing_child, vehicles)[0]
    wrong_parent = parse_tf_parent_sets(tf_fixture.replace("frame_id: world",
                                                            "frame_id: map", 1))
    assert not expected_tf_contract(wrong_parent, vehicles)[0]
    assert not expected_tf_contract({"uav0/base_link": {"world", "map"},
                                     "uav1/base_link": {"world"}}, vehicles)[0]
    multi_parent = parse_tf_parent_sets(tf_fixture + """transforms:
- header:
    frame_id: map
  child_frame_id: uav0/base_link
  transform: {}
---
""")
    assert multi_parent["uav0/base_link"] == {"world", "map"}
    assert not expected_tf_contract(multi_parent, vehicles)[0]
    # D5: TF contract and parse are vehicle-list driven (uav_count=3 coverage).
    three_vehicles = [{"frames": {"parent": "world", "child": "uav0/base_link"}},
                      {"frames": {"parent": "world", "child": "uav1/base_link"}},
                      {"frames": {"parent": "world", "child": "uav2/base_link"}}]
    three_fixture = tf_fixture + """transforms:
- header:
    seq: 3
    stamp: {secs: 1, nsecs: 0}
    frame_id: world
  child_frame_id: uav2/base_link
  transform: {}
---
"""
    parsed_three = parse_tf_parent_sets(three_fixture)
    assert parsed_three == {"uav0/base_link": {"world"},
                            "uav1/base_link": {"world"},
                            "uav2/base_link": {"world"}}
    assert expected_tf_contract(parsed_three, three_vehicles)[0]
    assert not expected_tf_contract(
        {"uav0/base_link": {"world"}, "uav1/base_link": {"world"}},
        three_vehicles)[0]
    assert tf_echo_argv()[-1] == "/tf"
    assert "--noarr" not in tf_echo_argv()
    assert payload_observed(0, "header: {}\n")[0]
    assert not payload_observed(0, "", "topic registered but silent")[0]
    profile_sample = {"wall_monotonic_s": 1.0, "wall_delta_s": None, "sim_s": None,
                      "sim_evidence_missing": True, "clk_tck": 100,
                      "roles": {}, "system": {}}
    assert resource_profile_schema_valid(profile_sample)
    assert not resource_profile_schema_valid(dict(profile_sample, clk_tck=0))
    assert not resource_profile_schema_valid(dict(profile_sample, sim_evidence_missing=False))
    print("two_uav_preflight self-test: PASS")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("static", "live"))
    parser.add_argument("--config", default=str(ROOT / "config/2uav_static.yaml"))
    parser.add_argument("--manifest", default=str(ROOT / "experiments/manifests/2uav_smoke.yaml"))
    parser.add_argument("--runroot")
    parser.add_argument("--output")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.mode:
        parser.error("--mode is required unless --self-test is used")
    if args.mode == "static":
        checks, hashes = static_checks(args.config, args.manifest)
    else:
        if not args.runroot:
            parser.error("--runroot is required for live mode")
        checks, hashes = live_checks(args.config, args.runroot), {}
    report = {
        "schema_version": 1,
        "mode": args.mode,
        "passed": all(item["ok"] for item in checks),
        "checks": checks,
        "source_hashes": hashes,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    sys.exit(main())
