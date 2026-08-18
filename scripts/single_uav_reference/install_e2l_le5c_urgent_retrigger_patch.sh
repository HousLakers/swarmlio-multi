#!/usr/bin/env bash
# Install LE5c C++ patch: urgent cooldown lane for sustained pending low-speed retriggers.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CPP="/home/houslakers/racer_ws/src/RACER/swarm_exploration/exploration_manager/src/fast_exploration_manager.cpp"
HDR="/home/houslakers/racer_ws/src/RACER/swarm_exploration/exploration_manager/include/exploration_manager/fast_exploration_manager.h"
XML="/home/houslakers/racer_ws/src/RACER/swarm_exploration/exploration_manager/launch/single_drone_planner.xml"
[[ "${1:-}" == "" || "${1:-}" == "--dry-run" ]] || { echo "usage: $0 [--dry-run]" >&2; exit 64; }
for path in "$CPP" "$HDR" "$XML"; do
  [[ -f "$path" ]] || { echo "missing target: $path" >&2; exit 66; }
done

STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$ROOT/POST_E1_E2L_LE5C_URGENT_RETRIGGER_PATCH_$STAMP"
mkdir -p "$BACKUP_DIR"
cp "$CPP" "$BACKUP_DIR/fast_exploration_manager.cpp.pre_le5c_$STAMP"
cp "$HDR" "$BACKUP_DIR/fast_exploration_manager.h.pre_le5c_$STAMP"
cp "$XML" "$BACKUP_DIR/single_drone_planner.xml.pre_le5c_$STAMP"

python3 - "$CPP" "$HDR" "$XML" "${1:-}" <<'PY'
from pathlib import Path
import sys

cpp = Path(sys.argv[1])
hdr = Path(sys.argv[2])
xml = Path(sys.argv[3])
dry = sys.argv[4] == "--dry-run"
cpp_s = cpp.read_text()
hdr_s = hdr.read_text()
xml_s = xml.read_text()
if "\\n" in xml_s and xml_s.count("\n") <= 2:
    xml_s = xml_s.replace("\\n", "\n")

if "bool low_speed_escape_urgent_;" not in hdr_s:
    hdr_s = hdr_s.replace(
        "  bool low_speed_escape_requested_;\n",
        "  bool low_speed_escape_requested_;\n  bool low_speed_escape_urgent_;\n",
        1,
    )
if "planner_escape_urgent_cooldown_sec_" not in hdr_s:
    hdr_s = hdr_s.replace(
        "  double planner_escape_repeat_threshold_, planner_escape_cooldown_sec_;\n",
        "  double planner_escape_repeat_threshold_, planner_escape_cooldown_sec_;\n"
        "  double planner_escape_urgent_cooldown_sec_;\n",
        1,
    )

if 'nh.param("planner_escape/urgent_cooldown_sec"' not in cpp_s:
    cpp_s = cpp_s.replace(
        '  nh.param("planner_escape/cooldown_sec", planner_escape_cooldown_sec_, 45.0);\n',
        '  nh.param("planner_escape/cooldown_sec", planner_escape_cooldown_sec_, 45.0);\n'
        '  nh.param("planner_escape/urgent_cooldown_sec", planner_escape_urgent_cooldown_sec_, planner_escape_cooldown_sec_);\n',
        1,
    )
if "low_speed_escape_urgent_ = false;" not in cpp_s:
    cpp_s = cpp_s.replace(
        "  low_speed_escape_requested_ = false;\n",
        "  low_speed_escape_requested_ = false;\n  low_speed_escape_urgent_ = false;\n",
        1,
    )

old = "  double x = 0.0, y = 0.0, z = 0.0, action_id = 0.0;\n"
new = "  double x = 0.0, y = 0.0, z = 0.0, action_id = 0.0, urgent_retrigger = 0.0;\n"
if old in cpp_s:
    cpp_s = cpp_s.replace(old, new, 1)
elif new not in cpp_s:
    raise SystemExit("could not add urgent_retrigger local variable")

old = '''  if (extract_number("action_id", action_id)) {
    low_speed_escape_request_id_ = static_cast<int>(std::llround(action_id));
  } else {
    ++low_speed_escape_request_id_;
  }
  low_speed_escape_request_time_ = now;
'''
new = '''  if (extract_number("action_id", action_id)) {
    low_speed_escape_request_id_ = static_cast<int>(std::llround(action_id));
  } else {
    ++low_speed_escape_request_id_;
  }
  low_speed_escape_urgent_ =
      extract_number("urgent_retrigger", urgent_retrigger) && urgent_retrigger > 0.5;
  low_speed_escape_request_time_ = now;
'''
if old in cpp_s:
    cpp_s = cpp_s.replace(old, new, 1)
elif "low_speed_escape_urgent_ =" not in cpp_s:
    raise SystemExit("could not patch urgent flag extraction")

old = '''  ROS_WARN_STREAM("T1S4R low_speed_escape request action_id=" << low_speed_escape_request_id_
                  << " pos=" << low_speed_escape_request_pos_.transpose());
'''
new = '''  ROS_WARN_STREAM("T1S4R low_speed_escape request action_id=" << low_speed_escape_request_id_
                  << " urgent=" << low_speed_escape_urgent_
                  << " pos=" << low_speed_escape_request_pos_.transpose());
'''
if old in cpp_s:
    cpp_s = cpp_s.replace(old, new, 1)

old = '''  const double cooldown = (ros::Time::now() - planner_escape_last_time_).toSec();
  if (cooldown < planner_escape_cooldown_sec_) return;
'''
new = '''  const double cooldown = (ros::Time::now() - planner_escape_last_time_).toSec();
  const double required_cooldown =
      low_speed_escape_urgent_ ? planner_escape_urgent_cooldown_sec_ : planner_escape_cooldown_sec_;
  if (cooldown < required_cooldown) return;
'''
if old in cpp_s:
    cpp_s = cpp_s.replace(old, new, 1)
elif "planner_escape_urgent_cooldown_sec_" not in cpp_s:
    raise SystemExit("could not patch cooldown gate")

old = '''  fusion_escape_armed_ = false;
  low_speed_escape_requested_ = false;
  planner_consecutive_failures_ = 0;
'''
new = '''  fusion_escape_armed_ = false;
  low_speed_escape_requested_ = false;
  low_speed_escape_urgent_ = false;
  planner_consecutive_failures_ = 0;
'''
if old in cpp_s:
    cpp_s = cpp_s.replace(old, new, 1)

old = '''  ROS_WARN_STREAM("T1S4R fusion_execute mode=" << planner_escape_trigger_mode_
                  << " suppress_center=" << planner_suppressed_center_.transpose()
                  << " escape_count=" << planner_escape_count_);
'''
new = '''  ROS_WARN_STREAM("T1S4R fusion_execute mode=" << planner_escape_trigger_mode_
                  << " suppress_center=" << planner_suppressed_center_.transpose()
                  << " cooldown=" << cooldown
                  << " required_cooldown=" << required_cooldown
                  << " escape_count=" << planner_escape_count_);
'''
if old in cpp_s:
    cpp_s = cpp_s.replace(old, new, 1)

if 'name="planner_escape/urgent_cooldown_sec"' not in xml_s:
    xml_s = xml_s.replace(
        '    <param name="planner_escape/cooldown_sec" value="60.0" type="double"/>\n',
        '    <param name="planner_escape/cooldown_sec" value="60.0" type="double"/>\n'
        '    <param name="planner_escape/urgent_cooldown_sec" value="60.0" type="double"/>\n',
        1,
    )

if dry:
    print("LE5C_URGENT_RETRIGGER_PATCH_DRY_RUN_OK")
else:
    cpp.write_text(cpp_s)
    hdr.write_text(hdr_s)
    xml.write_text(xml_s)
    print("LE5C_URGENT_RETRIGGER_PATCH_WRITTEN")
PY

if [[ "${1:-}" == "--dry-run" ]]; then
  echo "LE5C_URGENT_RETRIGGER_PATCH_DRY_RUN_PASS: $BACKUP_DIR"
else
  echo "LE5C_URGENT_RETRIGGER_PATCH_COMPLETE: $BACKUP_DIR"
fi
