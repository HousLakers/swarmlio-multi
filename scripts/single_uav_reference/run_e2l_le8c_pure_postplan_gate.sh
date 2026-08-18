#!/usr/bin/env bash
# LE8-C: historical arm-3 comparator, pure post-plan guard, no fresh control.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

[[ "${1:-}" == "" || "${1:-}" == "--dry-run" ]] || {
  echo "usage: $0 [--dry-run]" >&2
  exit 64
}
DRY=0
[[ "${1:-}" == "--dry-run" ]] && DRY=1
DURATION="${E2L_LE8C_DURATION:-600}"
REPS="${E2L_LE8C_REPS:-3}"
[[ "$DURATION" =~ ^[0-9]+$ && "$DURATION" -ge 1 ]] || exit 64
[[ "$REPS" =~ ^[0-9]+$ && "$REPS" -ge 1 ]] || exit 64

python3 -m py_compile topology_t1s4r_runner.py analyze_e2l_readiness.py \
  analyze_e2l_path_frontier_loops.py analyze_e2l_target_selection_depth.py \
  e2l_runtime_param_gate.py
bash -n "$0" install_e2l_le8c_pure_postplan_diag_patch.sh run_e2l_le4_memory_600.sh

STAMP="$(date +%Y%m%d_%H%M%S)"
RUNROOT="${E2L_LE8C_ROOT:-$ROOT/POST_E1_E2L_LE8C_PURE_POSTPLAN_GATE_$STAMP}"
[[ ! -e "$RUNROOT" ]] || { echo "refusing existing run root: $RUNROOT" >&2; exit 74; }
mkdir -p "$RUNROOT"

cat > "$RUNROOT/experiment_contract.md" <<MD
# LE8-C Pure Post-plan Guard Contract

- Historical comparator only: LE8-A arm 3, 3x600 s, 3/3 non-frozen, zero true
  contact, median coverage 0.820. No fresh control and no inflation-0.50 run.
- Candidate boundary filtering is disabled. This removes the LE8-B B1
  confounder while retaining sticky center, failed-target memory and inflation
  0.35.
- The optimized escape B-spline is sampled every 0.05 s before publication.
  XY margin is 0.35 m, equal to the simulated rotor/body radius used by the
  project safety analysis.
- Repetitions run sequentially and each repetition passes a hard safety gate
  before the next starts.
- Promotion requires 3/3 non-frozen, zero true contact/crash, median coverage
  >= 0.76. Planner collision-replan events are reported separately and are not
  relabeled as physical contacts.
MD

printf 'variant\tduration\treps\tinflation\tboundary_candidate_guard\tpostplan_guard\tmargin_xy\tdt\n' > "$RUNROOT/variant_plan.tsv"
printf 'le8c_pure_postplan_600\t%s\t%s\t%s\tfalse\ttrue\t0.35\t0.05\n' \
  "$DURATION" "$REPS" "${T1S4R_OBSTACLES_INFLATION:-0.35}" >> "$RUNROOT/variant_plan.tsv"
printf 'runroot=%s\ndry_run=%s\nstarted=%s\n' "$RUNROOT" "$DRY" "$(date -Is)" > "$RUNROOT/run_status.log"

if [[ "${E2L_LE8C_SKIP_DIAG:-0}" == "1" ]]; then
  CPP=/home/houslakers/racer_ws/src/RACER/swarm_exploration/exploration_manager/src/fast_exploration_manager.cpp
  rg -q 'LE8(C postplan_guard|H global_postplan_guard) reject reason=' "$CPP"
  echo "LE8C_DIAG_INSTALL_SKIPPED_VERIFIED"
elif [[ "$DRY" == "1" ]]; then
  ./install_e2l_le8c_pure_postplan_diag_patch.sh --dry-run
else
  ./install_e2l_le8c_pure_postplan_diag_patch.sh
fi

if [[ "$DRY" == "1" ]]; then
  export T1S4R_DRY_PLANNER_XML="${T1S4R_DRY_PLANNER_XML:-/home/houslakers/racer_ws/src/RACER/swarm_exploration/exploration_manager/launch/single_drone_planner.xml}"
else
  ./install_t1s4r_integration.sh --build
  ./install_t1s4r_integration.sh --verify
fi

export RACER_GT_MAPPER=1 PYTHONUNBUFFERED=1 T1S4R_FSM_PROFILE=strict
export T1S4R_TRIGGER_GROUPS=low_speed_escape T1S4R_TRIGGER_TAGS=t1s4r_r1_center_fsm2
export T1S4R_TRIGGER_DURATION="$DURATION" T1S4R_TRIGGER_REPS=1
export T1S4R_LSE_MEAN_SPEED=0.50 T1S4R_LSE_TIME_PERSISTENCE=3
export T1S4R_LSE_MAX_ACTIONS="${T1S4R_LSE_MAX_ACTIONS:-8}" T1S4R_LSE_BRIDGE_COOLDOWN="${T1S4R_LSE_BRIDGE_COOLDOWN:-35}"
export T1S4R_LSE_MAX_ESCAPE_COUNT="${T1S4R_LSE_MAX_ESCAPE_COUNT:-8}" T1S4R_LSE_COOLDOWN_SEC="${T1S4R_LSE_COOLDOWN_SEC:-35}"
export T1S4R_LSE_URGENT_COOLDOWN_SEC="${T1S4R_LSE_URGENT_COOLDOWN_SEC:-35}" T1S4R_LSE_PENDING_RETRIGGER="${T1S4R_LSE_PENDING_RETRIGGER:-true}"
export T1S4R_LSE_RETRIGGER_GRACE="${T1S4R_LSE_RETRIGGER_GRACE:-0.0}" T1S4R_LSE_PENDING_URGENT_AFTER="${T1S4R_LSE_PENDING_URGENT_AFTER:-20}"
export T1S4R_LSE_PENDING_MIN_COOLDOWN="${T1S4R_LSE_PENDING_MIN_COOLDOWN:-35}" T1S4R_LSE_STALL_WATCHDOG="${T1S4R_LSE_STALL_WATCHDOG:-true}"
export T1S4R_LSE_STALL_WINDOW=4.0 T1S4R_LSE_STALL_MEAN_SPEED=0.22
export T1S4R_LSE_STALL_PEAK_SPEED=0.35 T1S4R_LSE_STALL_DISPLACEMENT=0.8
export T1S4R_LSE_STALL_DEBOUNCE=20.0

export T1S4R_LSE_V2_ENABLED=true T1S4R_LSE_V2_CLEAR_RADIUS_M=5.5
export T1S4R_LSE_V2_MIN_STEP_M=2.5 T1S4R_LSE_V2_MAX_STEP_M=5.0
export T1S4R_LSE_V2_TTL_SEC=45.0 T1S4R_LSE_V2_MIN_CLEARANCE_M=0.55
export T1S4R_LSE_V2_MAX_COST=2500.0 T1S4R_LSE_V2_TRIGGER_ON_PLANNER_FAIL=true
export T1S4R_LSE_V2_TARGET_REPEAT_THRESHOLD=8 T1S4R_LSE_V2_STICKY_CENTER=true
export T1S4R_LSE_V2_FAILED_TARGET_MEMORY=true T1S4R_LSE_V2_FAILED_TARGET_RADIUS_M=0.8
export T1S4R_LSE_FAIL_WINDOW_SEC=12.0
export T1S4R_OBSTACLES_INFLATION="${T1S4R_OBSTACLES_INFLATION:-0.35}"
export T1S4R_LSE_V2_BOUNDARY_GUARD_ENABLED=false
export T1S4R_LSE_V2_BOUNDARY_MARGIN_XY_M=0.35
export T1S4R_LSE_V2_POSTPLAN_GUARD_ENABLED=true
export T1S4R_LSE_V2_POSTPLAN_DT_SEC=0.05
export T1S4R_LSE_MEMORY_ENABLED=true T1S4R_LSE_MEMORY_ENFORCE=true
export T1S4R_LSE_MEMORY_ENFORCE_LOW_SPEED_ONLY=true T1S4R_LSE_MEMORY_HARD_PRUNE=false
export T1S4R_LSE_MEMORY_LOCAL_ENFORCE=true T1S4R_LSE_MEMORY_FRONTIER_SOFT_ENFORCE=true
export T1S4R_LSE_MEMORY_FRONTIER_MAX_FRACTION=0.67 T1S4R_LSE_MEMORY_FRONTIER_PENALTY_RATIO=0.25
export T1S4R_LSE_MEMORY_REGION_SIZE_M=4.8 T1S4R_LSE_MEMORY_COOLDOWN_SEC=90.0
export T1S4R_LSE_MEMORY_BLACKLIST_THRESHOLD=1 T1S4R_LSE_MEMORY_BLACKLIST_SEC=120.0
export T1S4R_LSE_MEMORY_FORGET_SEC=180.0 T1S4R_LSE_MEMORY_COST_PENALTY=3.0

export T1S4R_LSE_REPEAT_FRONTIER_SOFT_ENFORCE=true T1S4R_LSE_REPEAT_FRONTIER_THRESHOLD=12
export T1S4R_LSE_REPEAT_FRONTIER_STRONG_THRESHOLD=16 T1S4R_LSE_REPEAT_FRONTIER_PENALTY_RATIO=0.15
export T1S4R_LSE_REPEAT_FRONTIER_MAX_FRACTION=0.67 T1S4R_LSE_REPEAT_FRONTIER_LOW_GAIN_THRESHOLD=2.0
export T1S4R_LSE_REPEAT_FRONTIER_COOLDOWN_SEC=35 T1S4R_LSE_REPEAT_FRONTIER_MAX_PENALTY_RATIO=0.30
export T1S4R_LSE_GAIN_RANK_ENFORCE=true T1S4R_LSE_GAIN_RANK_GAIN_WEIGHT=0.06
export T1S4R_LSE_GAIN_RANK_GAIN_CAP=20.0 T1S4R_LSE_GAIN_RANK_BONUS_RATIO=0.18
export T1S4R_LSE_GAIN_RANK_LOW_GAIN_THRESHOLD=2.0 T1S4R_LSE_GAIN_RANK_LOW_GAIN_PENALTY_RATIO=0.08
export T1S4R_LSE_GAIN_RANK_MAX_FRACTION=0.75

gate_rep() {
  local rep_root="$1"
  python3 - "$rep_root" <<'PY'
import json
import os
import pathlib
import sys
from e2l_runtime_param_gate import check_runtime_params

root = pathlib.Path(sys.argv[1])
states = list(root.rglob("*.state.json"))
if len(states) != 1:
    raise SystemExit(f"LE8C_REP_GATE_FAIL:state_count={len(states)}")
rows = json.loads(states[0].read_text()).get("rows", [])
if len(rows) != 1:
    raise SystemExit(f"LE8C_REP_GATE_FAIL:row_count={len(rows)}")
result = pathlib.Path(rows[0]["result_dir"])
metrics = json.loads((result / "metrics.json").read_text())
errors = []
quality_errors = []
raw_contacts = int(metrics.get("gazebo_contact_count", 0) or 0)
shallow_limit = float(os.environ.get("E2L_LE8C_SHALLOW_CONTACT_MAX_DEPTH_M", "0"))
abort_depth = float(os.environ.get("E2L_LE8C_BATCH_ABORT_CONTACT_DEPTH_M", str(shallow_limit)))
abort_count = int(os.environ.get("E2L_LE8C_BATCH_ABORT_CONTACT_COUNT", "1"))
depths = [float(x.get("max_depth", 0.0) or 0.0) for x in metrics.get("contact_details", [])]
max_contact_depth = max(depths, default=0.0)
severe_contacts = raw_contacts if raw_contacts and max_contact_depth > shallow_limit else 0
batch_abort_contact = bool(raw_contacts and (
    max_contact_depth > abort_depth or raw_contacts >= abort_count
))
if batch_abort_contact: errors.append("batch_abort_contact")
if bool(metrics.get("crashed", False)): errors.append("crashed")
if bool(metrics.get("frozen", False)): quality_errors.append("frozen")
racer = result / "ros_logs" / "launcher_logs" / "racer.log"
runtime = racer.read_text(errors="replace") if racer.exists() else ""
expected_runtime = {
    "/exploration_node_1/sdf_map/obstacles_inflation":
        float(os.environ.get("T1S4R_OBSTACLES_INFLATION", "0.35")),
    "/exploration_node_1/planner_escape/v2_boundary_guard_enabled": False,
    "/exploration_node_1/planner_escape/v2_boundary_margin_xy_m": 0.35,
    "/exploration_node_1/planner_escape/v2_postplan_guard_enabled": True,
    "/exploration_node_1/planner_escape/v2_postplan_dt_sec": 0.05,
}
if "T1S4R_LSE_V2_PROGRESS_GUARD_ENABLED" in os.environ:
    expected_runtime.update({
        "/exploration_node_1/planner_escape/v2_progress_guard_enabled":
            os.environ["T1S4R_LSE_V2_PROGRESS_GUARD_ENABLED"].lower() == "true",
        "/exploration_node_1/planner_escape/v2_progress_horizon_sec":
            float(os.environ["T1S4R_LSE_V2_PROGRESS_HORIZON_SEC"]),
        "/exploration_node_1/planner_escape/v2_min_progress_xy_m":
            float(os.environ["T1S4R_LSE_V2_MIN_PROGRESS_XY_M"]),
    })
if "T1S4R_GLOBAL_TRAJ_GUARD_ENABLED" in os.environ:
    expected_runtime.update({
        "/exploration_node_1/trajectory_safety/global_postplan_guard_enabled":
            os.environ["T1S4R_GLOBAL_TRAJ_GUARD_ENABLED"].lower() == "true",
        "/exploration_node_1/trajectory_safety/reject_unknown":
            os.environ["T1S4R_GLOBAL_TRAJ_REJECT_UNKNOWN"].lower() == "true",
        "/exploration_node_1/trajectory_safety/boundary_margin_xy_m":
            float(os.environ["T1S4R_GLOBAL_TRAJ_BOUNDARY_MARGIN_XY_M"]),
        "/exploration_node_1/trajectory_safety/extra_clearance_m":
            float(os.environ["T1S4R_GLOBAL_TRAJ_EXTRA_CLEARANCE_M"]),
        "/exploration_node_1/trajectory_safety/dt_sec":
            float(os.environ["T1S4R_GLOBAL_TRAJ_DT_SEC"]),
    })
runtime_parameters, runtime_errors = check_runtime_params(runtime, expected_runtime)
errors.extend(runtime_errors)
payload = {
    "result_dir": str(result),
    "coverage": metrics.get("spatial_coverage"),
    "frozen": bool(metrics.get("frozen", False)),
    "crashed": bool(metrics.get("crashed", False)),
    "true_contacts": raw_contacts,
    "severe_contacts": severe_contacts,
    "max_contact_depth_m": max_contact_depth,
    "shallow_contact_limit_m": shallow_limit,
    "batch_abort_contact": batch_abort_contact,
    "batch_abort_depth_m": abort_depth,
    "batch_abort_count": abort_count,
    "planner_collision_replans": int(metrics.get("collision_count", 0) or 0),
    "errors": errors,
    "quality_errors": quality_errors,
    "runtime_parameters": runtime_parameters,
    "hard_safety_pass": not errors,
}
(root / "le8c_rep_gate.json").write_text(json.dumps(payload, indent=2) + "\n")
print(json.dumps(payload, sort_keys=True))
if errors: raise SystemExit("LE8C_REP_GATE_FAIL:" + ";".join(errors))
PY
}

for rep in $(seq 1 "$REPS"); do
  REP_ROOT="$RUNROOT/rep_$rep"
  mkdir -p "$REP_ROOT"
  export E2L_LE4_ROOT="$REP_ROOT/run"
  export E2L_LE4_VARIANT=le8c_pure_postplan_600
  export E2L_LE4_VARIANT_NOTE="LE8-C pure postplan, historical arm-3 comparator, rep $rep/$REPS"
  echo "[$(date -Is)] start rep $rep/$REPS" | tee -a "$RUNROOT/run_status.log"
  if [[ "$DRY" == "1" ]]; then
    ./run_e2l_le4_memory_600.sh --dry-run
    python3 - "$REP_ROOT/dry_variant_env.json" <<'PY'
import json
import os
import pathlib
import sys

expected = {
    "T1S4R_TRIGGER_DURATION": os.environ["T1S4R_TRIGGER_DURATION"],
    "T1S4R_TRIGGER_REPS": "1",
    "T1S4R_OBSTACLES_INFLATION": os.environ["T1S4R_OBSTACLES_INFLATION"],
    "T1S4R_LSE_V2_STICKY_CENTER": "true",
    "T1S4R_LSE_V2_FAILED_TARGET_MEMORY": "true",
    "T1S4R_LSE_V2_BOUNDARY_GUARD_ENABLED": "false",
    "T1S4R_LSE_V2_BOUNDARY_MARGIN_XY_M": "0.35",
    "T1S4R_LSE_V2_POSTPLAN_GUARD_ENABLED": "true",
    "T1S4R_LSE_V2_POSTPLAN_DT_SEC": "0.05",
    "T1S4R_SAMPLER_WALL_FACTOR": os.environ.get("T1S4R_SAMPLER_WALL_FACTOR", "3.0"),
    "T1S4R_LSE_URGENT_COOLDOWN_SEC": os.environ["T1S4R_LSE_URGENT_COOLDOWN_SEC"],
    "T1S4R_LSE_PENDING_URGENT_AFTER": os.environ["T1S4R_LSE_PENDING_URGENT_AFTER"],
    "T1S4R_LSE_PENDING_MIN_COOLDOWN": os.environ["T1S4R_LSE_PENDING_MIN_COOLDOWN"],
}
if "T1S4R_LSE_V2_PROGRESS_GUARD_ENABLED" in os.environ:
    expected.update({
        "T1S4R_LSE_V2_PROGRESS_GUARD_ENABLED":
            os.environ["T1S4R_LSE_V2_PROGRESS_GUARD_ENABLED"],
        "T1S4R_LSE_V2_PROGRESS_HORIZON_SEC":
            os.environ["T1S4R_LSE_V2_PROGRESS_HORIZON_SEC"],
        "T1S4R_LSE_V2_MIN_PROGRESS_XY_M":
            os.environ["T1S4R_LSE_V2_MIN_PROGRESS_XY_M"],
    })
if "T1S4R_GLOBAL_TRAJ_GUARD_ENABLED" in os.environ:
    expected.update({
        "T1S4R_GLOBAL_TRAJ_GUARD_ENABLED":
            os.environ["T1S4R_GLOBAL_TRAJ_GUARD_ENABLED"],
        "T1S4R_GLOBAL_TRAJ_REJECT_UNKNOWN":
            os.environ["T1S4R_GLOBAL_TRAJ_REJECT_UNKNOWN"],
        "T1S4R_GLOBAL_TRAJ_BOUNDARY_MARGIN_XY_M":
            os.environ["T1S4R_GLOBAL_TRAJ_BOUNDARY_MARGIN_XY_M"],
        "T1S4R_GLOBAL_TRAJ_EXTRA_CLEARANCE_M":
            os.environ["T1S4R_GLOBAL_TRAJ_EXTRA_CLEARANCE_M"],
        "T1S4R_GLOBAL_TRAJ_DT_SEC":
            os.environ["T1S4R_GLOBAL_TRAJ_DT_SEC"],
    })
actual = {key: os.environ.get(key) for key in expected}
errors = {key: {"expected": value, "actual": actual[key]}
          for key, value in expected.items() if actual[key] != value}
path = pathlib.Path(sys.argv[1])
path.write_text(json.dumps({"values": actual, "errors": errors}, indent=2) + "\n")
if errors:
    raise SystemExit("LE8C_DRY_PARAM_FAIL:" + json.dumps(errors, sort_keys=True))
PY
  else
    ./run_e2l_le4_memory_600.sh
    gate_rep "$REP_ROOT"
  fi
  echo "[$(date -Is)] pass rep $rep/$REPS" | tee -a "$RUNROOT/run_status.log"
done

if [[ "$DRY" == "0" ]]; then
  python3 analyze_e2l_path_frontier_loops.py "$RUNROOT" --out-dir "$RUNROOT/path_frontier_audit"
  python3 analyze_e2l_target_selection_depth.py "$RUNROOT" --out-dir "$RUNROOT/target_selection_audit"
  python3 analyze_e2l_readiness.py "$RUNROOT" --out-dir "$RUNROOT/readiness_audit"
  python3 - "$RUNROOT" "$REPS" <<'PY'
import json
import os
import pathlib
import re
import statistics
import sys

root = pathlib.Path(sys.argv[1])
expected = int(sys.argv[2])
reps = [json.loads(p.read_text()) for p in sorted(root.glob("rep_*/le8c_rep_gate.json"))]
errors = []
if len(reps) != expected: errors.append(f"missing_reps={len(reps)}/{expected}")
if any(not x["hard_safety_pass"] for x in reps): errors.append("hard_safety_failure")
non_frozen = sum(not x["frozen"] and not x["crashed"] for x in reps)
min_non_frozen = int(os.environ.get("E2L_LE8C_MIN_NON_FROZEN", str(expected)))
if non_frozen < min_non_frozen:
    errors.append(f"non_frozen={non_frozen}<{min_non_frozen}")
coverages = [float(x["coverage"] or 0.0) for x in reps]
median_cov = statistics.median(coverages) if coverages else 0.0
min_median_cov = float(os.environ.get("E2L_LE8C_MIN_MEDIAN_COVERAGE", "0.76"))
if median_cov < min_median_cov:
    errors.append(f"median_coverage={median_cov:.3f}<{min_median_cov:.3f}")
events = {"boundary": 0, "inflated_occupancy": 0, "unknown": 0,
          "clearance": 0, "legacy_unclassified": 0}
for rep in reps:
    log = pathlib.Path(rep["result_dir"]) / "ros_logs" / "rosout.log"
    text = log.read_text(errors="replace") if log.exists() else ""
    for reason in re.findall(r"LE8C postplan_guard reject reason=(\w+)", text):
        events[reason] = events.get(reason, 0) + 1
    for reason in re.findall(r"LE8H global_postplan_guard reject reason=(\w+)", text):
        events[reason] = events.get(reason, 0) + 1
    events["legacy_unclassified"] += text.count("LE8B postplan_guard reject")
payload = {
    "decision": "promote" if not errors else "reject",
    "historical_comparator": {"name": "le8a_arm3", "n": 3, "median_coverage": 0.8198653198653199,
                              "frozen": 0, "true_contacts": 0},
    "runs": len(reps), "expected_runs": expected,
    "non_frozen": non_frozen, "min_non_frozen": min_non_frozen,
    "true_contacts": sum(x["true_contacts"] for x in reps),
    "coverages": coverages, "median_coverage": median_cov,
    "min_median_coverage": min_median_cov,
    "planner_collision_replans": [x["planner_collision_replans"] for x in reps],
    "postplan_rejects": events, "errors": errors,
}
(root / "le8c_gate.json").write_text(json.dumps(payload, indent=2) + "\n")
report = ["# LE8-C Pure Post-plan Result", "", f"Decision: **{payload['decision'].upper()}**", "",
          f"- runs: {len(reps)}/{expected}; non-frozen: {payload['non_frozen']}/{expected}",
          f"- true contacts: {payload['true_contacts']}",
          f"- coverage: {coverages}; median: {median_cov:.3f}",
          f"- post-plan rejects by reason: {events}",
          f"- planner collision-replan counts (not physical contacts): {payload['planner_collision_replans']}",
          f"- gate errors: {errors or 'none'}", ""]
(root / "le8c_result.md").write_text("\n".join(report))
print(json.dumps(payload, sort_keys=True))
PY
fi

echo "finished=$(date -Is)" >> "$RUNROOT/run_status.log"
echo "LE8C_PURE_POSTPLAN_GATE_COMPLETE: $RUNROOT"
