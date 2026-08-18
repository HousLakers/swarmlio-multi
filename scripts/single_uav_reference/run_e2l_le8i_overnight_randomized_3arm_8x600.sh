#!/usr/bin/env bash
# Final single-UAV robustness matrix, randomized at the individual-repetition level.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
[[ "${1:-}" == "" || "${1:-}" == "--dry-run" ]] || {
  echo "usage: $0 [--dry-run]" >&2
  exit 64
}
DRY=0
[[ "${1:-}" == "--dry-run" ]] && DRY=1

STAMP="$(date +%Y%m%d_%H%M%S)"
SEED="${E2L_LE8I_NIGHT_SEED:-$RANDOM$RANDOM}"
RUNROOT="${E2L_LE8I_NIGHT_ROOT:-$ROOT/POST_E1_E2L_LE8I_RANDOMIZED_3ARM_8X600_$STAMP}"
[[ ! -e "$RUNROOT" ]] || { echo "refusing existing root: $RUNROOT" >&2; exit 74; }
mkdir -p "$RUNROOT/raw"

python3 -m py_compile topology_t1s4r_runner.py verify_e2l_le8h_patch.py
bash -n "$0" run_e2l_le8c_pure_postplan_gate.sh
python3 verify_e2l_le8h_patch.py \
  --manager-source /home/houslakers/racer_ws/src/RACER/swarm_exploration/plan_manage/src/planner_manager.cpp \
  --manager-header /home/houslakers/racer_ws/src/RACER/swarm_exploration/plan_manage/include/plan_manage/planner_manager.h \
  --exploration-source /home/houslakers/racer_ws/src/RACER/swarm_exploration/exploration_manager/src/fast_exploration_manager.cpp \
  --exploration-header /home/houslakers/racer_ws/src/RACER/swarm_exploration/exploration_manager/include/exploration_manager/fast_exploration_manager.h \
  --xml /home/houslakers/racer_ws/src/RACER/swarm_exploration/exploration_manager/launch/single_drone_planner.xml

cat > "$RUNROOT/experiment_contract.md" <<'MD'
# E2-L Final Randomized Single-UAV Matrix

This is the terminal 3x8x600 single-UAV evidence matrix. The arms are selected
from the completed preflight and historical evidence. The 24 independent 600 s
repetitions are interleaved by a pre-generated, reproducible random sequence;
the same arm cannot occupy adjacent slots. This balances time-on-machine and
thermal/load drift across configurations.

| Arm | Configuration | Preflight interpretation |
| --- | --- | --- |
| `le8i_safe_unknown_tolerant` | inflation 0.40, progress on, global guard on, unknown allowed | 2/3 clean in latest 3x300; safety regression removed, liveness remains variable. |
| `le8g_high_coverage_reference` | inflation 0.40, progress on, global guard off | Historical 0.942 600 s result; latest 1x300 froze, so included as explicitly uncertain reference. |
| `le8e_reliability_reference` | inflation 0.35, progress off, global guard off | Historical 7/8 completion, completed coverage median 0.794; latest 1x300 clean. |

This matrix estimates reliability; it is not a qualification rerun. A crash,
contact deeper than 10 mm, or three contacts in one repetition ends that one
arm invocation. The sequence continues with the other planned repetitions.
All results are reported arm-wise and are never pooled as one configuration.
MD

python3 - "$RUNROOT/randomized_schedule.tsv" "$SEED" <<'PY'
import random
import sys

out, seed = sys.argv[1], int(sys.argv[2])
remaining = {
    "le8i_safe_unknown_tolerant": 8,
    "le8g_high_coverage_reference": 8,
    "le8e_reliability_reference": 8,
}
rng = random.Random(seed)
last = None
rows = []
while sum(remaining.values()):
    choices = [arm for arm, count in remaining.items() if count and arm != last]
    if not choices:
        choices = [arm for arm, count in remaining.items() if count]
    arm = rng.choice(choices)
    remaining[arm] -= 1
    rows.append(arm)
    last = arm
with open(out, "w") as handle:
    handle.write("slot\tarm\tarm_rep\tseed\n")
    counts = {arm: 0 for arm in remaining}
    for slot, arm in enumerate(rows, 1):
        counts[arm] += 1
        handle.write(f"{slot}\t{arm}\t{counts[arm]}\t{seed}\n")
PY

exec 9>"$ROOT/.e2l_le8i_randomized_overnight.lock"
if ! flock -n 9; then
  echo "refusing concurrent randomized overnight matrix: lock is held" >&2
  exit 75
fi
if [[ "$DRY" == "0" ]] && ps -eo cmd | grep -E '[s]corer.py --duration (300|600)' >/dev/null; then
  echo "refusing randomized overnight matrix while another scored experiment is active" >&2
  exit 75
fi

run_rep() {
  local slot="$1" arm="$2" arm_rep="$3"
  local inflation progress global_guard
  case "$arm" in
    le8i_safe_unknown_tolerant) inflation=0.40; progress=true; global_guard=true ;;
    le8g_high_coverage_reference) inflation=0.40; progress=true; global_guard=false ;;
    le8e_reliability_reference) inflation=0.35; progress=false; global_guard=false ;;
    *) echo "unknown arm: $arm" >&2; return 64 ;;
  esac
  local rep_root="$RUNROOT/raw/$arm/slot_${slot}_rep_${arm_rep}"
  local status
  local -a args=()
  [[ "$DRY" == "1" ]] && args+=(--dry-run)
  (
    export T1S4R_SAMPLER_WALL_FACTOR=3.0 E2L_LE8C_SKIP_DIAG=1
    export T1S4R_LSE_MAX_ACTIONS=12 T1S4R_LSE_MAX_ESCAPE_COUNT=12
    export T1S4R_LSE_BRIDGE_COOLDOWN=35 T1S4R_LSE_COOLDOWN_SEC=35
    export T1S4R_LSE_URGENT_COOLDOWN_SEC=15
    export T1S4R_LSE_PENDING_RETRIGGER=true T1S4R_LSE_PENDING_URGENT_AFTER=5
    export T1S4R_LSE_PENDING_MIN_COOLDOWN=15 T1S4R_LSE_STALL_DEBOUNCE=15
    export T1S4R_OBSTACLES_INFLATION="$inflation"
    export T1S4R_LSE_V2_PROGRESS_GUARD_ENABLED="$progress"
    export T1S4R_LSE_V2_PROGRESS_HORIZON_SEC=1.6
    export T1S4R_LSE_V2_MIN_PROGRESS_XY_M=0.25
    export T1S4R_GLOBAL_TRAJ_GUARD_ENABLED="$global_guard"
    export T1S4R_GLOBAL_TRAJ_REJECT_UNKNOWN=false
    export T1S4R_GLOBAL_TRAJ_BOUNDARY_MARGIN_XY_M=0.50
    export T1S4R_GLOBAL_TRAJ_EXTRA_CLEARANCE_M=0.10
    export T1S4R_GLOBAL_TRAJ_DT_SEC=0.05
    export E2L_LE8C_SHALLOW_CONTACT_MAX_DEPTH_M=0.003
    export E2L_LE8C_BATCH_ABORT_CONTACT_DEPTH_M=0.010
    export E2L_LE8C_BATCH_ABORT_CONTACT_COUNT=3
    E2L_LE8C_ROOT="$rep_root" E2L_LE8C_REPS=1 E2L_LE8C_DURATION=600 \
      E2L_LE8C_MIN_NON_FROZEN=0 E2L_LE8C_MIN_MEDIAN_COVERAGE=0 \
      ./run_e2l_le8c_pure_postplan_gate.sh "${args[@]}"
  )
  status=$?
  printf '%s\t%s\t%s\t%s\n' "$slot" "$arm" "$arm_rep" "$status" >> "$RUNROOT/rep_exit_status.tsv"
  return 0
}

printf 'slot\tarm\tarm_rep\texit_status\n' > "$RUNROOT/rep_exit_status.tsv"
set +e
while IFS=$'\t' read -r slot arm arm_rep seed; do
  [[ "$slot" == "slot" ]] && continue
  run_rep "$slot" "$arm" "$arm_rep"
done < "$RUNROOT/randomized_schedule.tsv"
set -e

python3 - "$RUNROOT" <<'PY'
import json
import pathlib
import statistics
import sys

root = pathlib.Path(sys.argv[1])
arms = {}
for gate_path in root.glob("raw/*/slot_*_rep_*/rep_1/le8c_rep_gate.json"):
    arm = gate_path.relative_to(root / "raw").parts[0]
    gate = json.loads(gate_path.read_text())
    row = {
        "result_dir": gate["result_dir"],
        "coverage": float(gate.get("coverage") or 0.0),
        "frozen": bool(gate.get("frozen")),
        "crashed": bool(gate.get("crashed")),
        "contacts": int(gate.get("true_contacts") or 0),
        "max_contact_depth_m": float(gate.get("max_contact_depth_m") or 0.0),
        "hard_safety_pass": bool(gate.get("hard_safety_pass")),
    }
    arms.setdefault(arm, []).append(row)
summary = []
for arm, rows in sorted(arms.items()):
    coverage = [row["coverage"] for row in rows]
    completed = [row for row in rows if not row["frozen"] and not row["crashed"]]
    summary.append({
        "arm": arm,
        "runs": len(rows),
        "completed": len(completed),
        "frozen": sum(row["frozen"] for row in rows),
        "crashed": sum(row["crashed"] for row in rows),
        "coverage_median": statistics.median(coverage) if coverage else None,
        "coverage_completed_median": statistics.median([row["coverage"] for row in completed]) if completed else None,
        "contacts": sum(row["contacts"] for row in rows),
        "contact_over_3mm_runs": sum(row["max_contact_depth_m"] > 0.003 for row in rows),
        "hard_safety_failures": sum(not row["hard_safety_pass"] for row in rows),
        "rows": rows,
    })
payload = {"schema_version": 1, "arms": summary}
(root / "randomized_matrix_summary.json").write_text(json.dumps(payload, indent=2) + "\n")
lines = ["# E2-L Randomized 3x8x600 Matrix", ""]
for arm in summary:
    lines.append(
        f"- `{arm['arm']}`: runs={arm['runs']}, completed={arm['completed']}, "
        f"frozen={arm['frozen']}, coverage median={arm['coverage_median']}, "
        f"contacts={arm['contacts']}, >3mm runs={arm['contact_over_3mm_runs']}")
(root / "E2L_LE8I_RANDOMIZED_MATRIX_SUMMARY.md").write_text("\n".join(lines) + "\n")
PY

echo "LE8I_RANDOMIZED_3ARM_8X600_COMPLETE: $RUNROOT"
