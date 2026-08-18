#!/usr/bin/env bash
# Install LE5b C++ patch: treat zero/invalid trajectory as planner failure.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CPP="/home/houslakers/racer_ws/src/RACER/swarm_exploration/exploration_manager/src/fast_exploration_manager.cpp"
XML="/home/houslakers/racer_ws/src/RACER/swarm_exploration/exploration_manager/launch/single_drone_planner.xml"
[[ "${1:-}" == "" || "${1:-}" == "--dry-run" ]] || { echo "usage: $0 [--dry-run]" >&2; exit 64; }
for path in "$CPP" "$XML"; do
  [[ -f "$path" ]] || { echo "missing target: $path" >&2; exit 66; }
done

STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$ROOT/POST_E1_E2L_LE5B_INVALID_TRAJ_PATCH_$STAMP"
mkdir -p "$BACKUP_DIR"
cp "$CPP" "$BACKUP_DIR/fast_exploration_manager.cpp.pre_le5b_$STAMP"
cp "$XML" "$BACKUP_DIR/single_drone_planner.xml.pre_le5b_$STAMP"

python3 - "$CPP" "$XML" "${1:-}" <<'PY'
from pathlib import Path
import sys

cpp = Path(sys.argv[1])
xml = Path(sys.argv[2])
dry = sys.argv[3] == "--dry-run"
cpp_s = cpp.read_text()
xml_s = xml.read_text()
if "\\n" in xml_s and xml_s.count("\n") <= 2:
    xml_s = xml_s.replace("\\n", "\n")

old = '''  if (planner_manager_->local_data_.position_traj_.getTimeSum() < time_lb - 0.5)
    ROS_ERROR("Lower bound not satified!");

  double traj_plan_time = (ros::Time::now() - t1).toSec();
'''
new = '''  const double planned_duration = planner_manager_->local_data_.position_traj_.getTimeSum();
  if (!std::isfinite(planned_duration) || planned_duration < 0.05) {
    ROS_ERROR("T1S4R invalid_traj zero_duration duration=%lf time_lb=%lf", planned_duration, time_lb);
    recordViewpointFailure(pos, next_pos, "invalid_traj");
    notePlannerPlanFail("invalid_traj");
    return FAIL;
  }
  if (planned_duration < time_lb - 0.5) {
    ROS_ERROR("T1S4R invalid_traj lower_bound duration=%lf time_lb=%lf", planned_duration, time_lb);
    recordViewpointFailure(pos, next_pos, "invalid_traj");
    notePlannerPlanFail("invalid_traj");
    return FAIL;
  }

  double traj_plan_time = (ros::Time::now() - t1).toSec();
'''
if old in cpp_s:
    cpp_s = cpp_s.replace(old, new, 1)
elif "T1S4R invalid_traj zero_duration" not in cpp_s:
    raise SystemExit("could not patch invalid trajectory check")

if dry:
    print("LE5B_INVALID_TRAJ_PATCH_DRY_RUN_OK")
else:
    cpp.write_text(cpp_s)
    xml.write_text(xml_s)
    print("LE5B_INVALID_TRAJ_PATCH_WRITTEN")
PY

if [[ "${1:-}" == "--dry-run" ]]; then
  echo "LE5B_INVALID_TRAJ_PATCH_DRY_RUN_PASS: $BACKUP_DIR"
else
  echo "LE5B_INVALID_TRAJ_PATCH_COMPLETE: $BACKUP_DIR"
fi
