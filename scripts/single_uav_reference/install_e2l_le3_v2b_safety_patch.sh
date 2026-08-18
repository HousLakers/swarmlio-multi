#!/usr/bin/env bash
# Install L-E3 v2b safety-gated virtual escape patch.
# Scope: RACER C++/XML only. Creates timestamped backups under this workspace.
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
BACKUP_DIR="$ROOT/POST_E1_E2L_LE3_V2B_SAFETY_PATCH_$STAMP"
mkdir -p "$BACKUP_DIR"
cp "$CPP" "$BACKUP_DIR/fast_exploration_manager.cpp.pre_le3_v2b_$STAMP"
cp "$HDR" "$BACKUP_DIR/fast_exploration_manager.h.pre_le3_v2b_$STAMP"
cp "$XML" "$BACKUP_DIR/single_drone_planner.xml.pre_le3_v2b_$STAMP"

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

if "planner_escape_v2_max_cost_" not in hdr_s:
    hdr_s = hdr_s.replace(
        "  double planner_escape_v2_min_clearance_m_, planner_escape_v2_memory_ttl_sec_;\n"
        "  int planner_escape_v2_target_repeat_threshold_;\n",
        "  double planner_escape_v2_min_clearance_m_, planner_escape_v2_memory_ttl_sec_;\n"
        "  double planner_escape_v2_max_cost_;\n"
        "  int planner_escape_v2_target_repeat_threshold_;\n",
    )

if 'nh.param("planner_escape/v2_max_cost"' not in cpp_s:
    cpp_s = cpp_s.replace(
        '  nh.param("planner_escape/v2_min_clearance_m", planner_escape_v2_min_clearance_m_, 0.35);\n'
        '  nh.param("planner_escape/v2_memory_ttl_sec", planner_escape_v2_memory_ttl_sec_, 180.0);\n',
        '  nh.param("planner_escape/v2_min_clearance_m", planner_escape_v2_min_clearance_m_, 0.35);\n'
        '  nh.param("planner_escape/v2_memory_ttl_sec", planner_escape_v2_memory_ttl_sec_, 180.0);\n'
        '  nh.param("planner_escape/v2_max_cost", planner_escape_v2_max_cost_, 2500.0);\n',
    )

old_v2_block = '''  if (planner_escape_v2_enabled_ && planner_escape_v2_active_) {
    const ros::Time now = ros::Time::now();
    if (now > planner_escape_v2_until_) {
      planner_escape_v2_active_ = false;
      ROS_WARN("T1S4R v2_escape switch_back ttl_expired");
    } else {
      const double cur_dist = (pos.head<2>() - planner_escape_v2_center_.head<2>()).norm();
      const double target_dist = (next_pos.head<2>() - planner_escape_v2_center_.head<2>()).norm();
      const bool repeated_target = selected_target_id >= 0 &&
          target_repeat_counts_[selected_target_id] >= planner_escape_v2_target_repeat_threshold_;
      const bool should_override =
          target_dist < planner_escape_v2_clear_radius_m_ ||
          planner_consecutive_failures_ >= planner_escape_fail_threshold_ ||
          repeated_target;
      if (cur_dist >= planner_escape_v2_clear_radius_m_ &&
          planner_consecutive_failures_ < planner_escape_fail_threshold_ &&
          !repeated_target) {
        planner_escape_v2_active_ = false;
        ROS_WARN_STREAM("T1S4R v2_escape switch_back clear cur_dist=" << cur_dist);
      } else if (should_override) {
        Vector3d best = next_pos;
        double best_score = -std::numeric_limits<double>::infinity();
        vector<Vector3d> tmp_path;
        for (const auto& cand : ed_->points_) {
          if (!cand.allFinite()) continue;
          const double away = (cand.head<2>() - planner_escape_v2_center_.head<2>()).norm();
          const double step = (cand.head<2>() - pos.head<2>()).norm();
          if (away < planner_escape_v2_clear_radius_m_) continue;
          if (step < planner_escape_v2_min_step_m_) continue;
          if (step > planner_escape_v2_max_step_m_) continue;
          const double clearance = sdf_map_->getDistance(cand);
          if (clearance < planner_escape_v2_min_clearance_m_) continue;
          const double cost = ViewNode::computeCost(
              pos, cand, yaw[0], atan2(cand.y() - pos.y(), cand.x() - pos.x()), vel, yaw[1], tmp_path);
          if (!std::isfinite(cost) || cost <= 0.0 || cost > 10000.0) continue;
          const double score = 2.0 * away + 0.5 * step + 1.5 * clearance - 0.02 * cost;
          if (score > best_score) {
            best_score = score;
            best = cand;
          }
        }
        if (best_score == -std::numeric_limits<double>::infinity() &&
            planner_escape_v2_fallback_enabled_) {
          Vector3d dir = pos - planner_escape_v2_center_;
          dir.z() = 0.0;
          if (dir.head<2>().norm() < 1e-3) dir = Vector3d(std::cos(yaw[0]), std::sin(yaw[0]), 0.0);
          dir.normalize();
          Vector3d cand = pos + planner_escape_v2_min_step_m_ * dir;
          cand.z() = pos.z();
          const double clearance = sdf_map_->getDistance(cand);
          if (clearance >= planner_escape_v2_min_clearance_m_) {
            best = cand;
            best_score = 0.0;
          }
        }
        if (best_score > -std::numeric_limits<double>::infinity()) {
          const Vector3d old_next = next_pos;
          next_pos = best;
          next_yaw = atan2(next_pos.y() - pos.y(), next_pos.x() - pos.x());
          ROS_WARN_STREAM("T1S4R v2_escape virtual_target override old="
                          << old_next.transpose() << " new=" << next_pos.transpose()
                          << " center=" << planner_escape_v2_center_.transpose()
                          << " cur_dist=" << cur_dist << " target_dist=" << target_dist
                          << " repeated_target=" << repeated_target
                          << " fail_streak=" << planner_consecutive_failures_);
        } else {
          ROS_WARN_STREAM("T1S4R v2_escape no_safe_virtual_target cur_dist=" << cur_dist
                          << " target_dist=" << target_dist);
        }
      }
    }
  }
'''

new_v2_block = '''  if (planner_escape_v2_enabled_ && planner_escape_v2_active_) {
    const ros::Time now = ros::Time::now();
    if (now > planner_escape_v2_until_) {
      planner_escape_v2_active_ = false;
      ROS_WARN("T1S4R v2_escape switch_back ttl_expired");
    } else {
      const double cur_dist = (pos.head<2>() - planner_escape_v2_center_.head<2>()).norm();
      const double target_dist = (next_pos.head<2>() - planner_escape_v2_center_.head<2>()).norm();
      const bool repeated_target = selected_target_id >= 0 &&
          target_repeat_counts_[selected_target_id] >= planner_escape_v2_target_repeat_threshold_;
      const bool near_escape_center = cur_dist < planner_escape_v2_clear_radius_m_;
      const bool target_near_escape_center = target_dist < planner_escape_v2_clear_radius_m_;
      const bool fail_streak_near_center =
          near_escape_center && planner_consecutive_failures_ >= planner_escape_fail_threshold_;
      const bool repeated_target_near_center = near_escape_center && repeated_target;
      const bool should_override =
          target_near_escape_center || fail_streak_near_center || repeated_target_near_center;
      if (!near_escape_center && !target_near_escape_center) {
        planner_escape_v2_active_ = false;
        if (planner_consecutive_failures_ >= planner_escape_fail_threshold_) planner_consecutive_failures_ = 0;
        ROS_WARN_STREAM("T1S4R v2_escape switch_back clear cur_dist=" << cur_dist
                        << " target_dist=" << target_dist << " stale_fail_reset=1");
      } else if (should_override) {
        Vector3d best = next_pos;
        double best_score = -std::numeric_limits<double>::infinity();
        vector<Vector3d> tmp_path;
        for (const auto& cand : ed_->points_) {
          if (!cand.allFinite()) continue;
          const double away = (cand.head<2>() - planner_escape_v2_center_.head<2>()).norm();
          const double step = (cand.head<2>() - pos.head<2>()).norm();
          if (away < planner_escape_v2_clear_radius_m_) continue;
          if (step < planner_escape_v2_min_step_m_) continue;
          if (step > planner_escape_v2_max_step_m_) continue;
          const double clearance = sdf_map_->getDistance(cand);
          if (clearance < planner_escape_v2_min_clearance_m_) continue;
          const double cost = ViewNode::computeCost(
              pos, cand, yaw[0], atan2(cand.y() - pos.y(), cand.x() - pos.x()), vel, yaw[1], tmp_path);
          if (!std::isfinite(cost) || cost <= 0.0 || cost > planner_escape_v2_max_cost_) continue;
          const double score = 2.0 * away + 0.35 * step + 2.0 * clearance - 0.02 * cost;
          if (score > best_score) {
            best_score = score;
            best = cand;
          }
        }
        if (best_score == -std::numeric_limits<double>::infinity() &&
            planner_escape_v2_fallback_enabled_ && near_escape_center) {
          Vector3d dir = pos - planner_escape_v2_center_;
          dir.z() = 0.0;
          if (dir.head<2>().norm() < 1e-3) dir = Vector3d(std::cos(yaw[0]), std::sin(yaw[0]), 0.0);
          dir.normalize();
          Vector3d cand = pos + planner_escape_v2_min_step_m_ * dir;
          cand.z() = pos.z();
          const double clearance = sdf_map_->getDistance(cand);
          const double step = (cand.head<2>() - pos.head<2>()).norm();
          if (clearance >= planner_escape_v2_min_clearance_m_ &&
              step <= planner_escape_v2_max_step_m_) {
            best = cand;
            best_score = 0.0;
          }
        }
        if (best_score > -std::numeric_limits<double>::infinity()) {
          const Vector3d old_next = next_pos;
          next_pos = best;
          next_yaw = atan2(next_pos.y() - pos.y(), next_pos.x() - pos.x());
          ROS_WARN_STREAM("T1S4R v2_escape virtual_target override old="
                          << old_next.transpose() << " new=" << next_pos.transpose()
                          << " center=" << planner_escape_v2_center_.transpose()
                          << " cur_dist=" << cur_dist << " target_dist=" << target_dist
                          << " near_center=" << near_escape_center
                          << " repeated_target=" << repeated_target
                          << " fail_streak=" << planner_consecutive_failures_
                          << " best_score=" << best_score);
        } else {
          ROS_WARN_STREAM("T1S4R v2_escape no_safe_virtual_target cur_dist=" << cur_dist
                          << " target_dist=" << target_dist
                          << " near_center=" << near_escape_center);
        }
      }
    }
  }
'''

if old_v2_block not in cpp_s and "stale_fail_reset=1" not in cpp_s:
    raise SystemExit("could not find LE3 v2 block to replace")
if old_v2_block in cpp_s:
    cpp_s = cpp_s.replace(old_v2_block, new_v2_block)

old_fail = '''  if (planner_escape_v2_enabled_ && planner_escape_v2_trigger_on_planner_fail_ &&
      planner_consecutive_failures_ >= planner_escape_fail_threshold_) {
    planner_escape_v2_active_ = true;
    planner_escape_v2_center_ = planner_last_fail_pos_;
    planner_escape_v2_until_ = ros::Time::now() + ros::Duration(planner_escape_v2_ttl_sec_);
    ROS_WARN_STREAM("T1S4R v2_escape armed_by_planner_fail kind=" << kind
                    << " center=" << planner_escape_v2_center_.transpose()
                    << " fail_streak=" << planner_consecutive_failures_);
  }
'''

new_fail = '''  const double startup_age = idle_origin_set_ ? (ros::Time::now() - idle_origin_).toSec() : 0.0;
  const bool v2_startup_ready = !idle_origin_set_ ||
      planner_escape_startup_guard_sec_ <= 0.0 ||
      startup_age >= planner_escape_startup_guard_sec_;
  if (planner_escape_v2_enabled_ && planner_escape_v2_trigger_on_planner_fail_ &&
      v2_startup_ready && planner_consecutive_failures_ >= planner_escape_fail_threshold_) {
    planner_escape_v2_active_ = true;
    planner_escape_v2_center_ = planner_last_fail_pos_;
    planner_escape_v2_until_ = ros::Time::now() + ros::Duration(planner_escape_v2_ttl_sec_);
    ROS_WARN_STREAM("T1S4R v2_escape armed_by_planner_fail kind=" << kind
                    << " center=" << planner_escape_v2_center_.transpose()
                    << " fail_streak=" << planner_consecutive_failures_
                    << " startup_age=" << startup_age);
  }
'''

if old_fail not in cpp_s and "v2_startup_ready" not in cpp_s:
    raise SystemExit("could not find v2 planner-fail arming block")
if old_fail in cpp_s:
    cpp_s = cpp_s.replace(old_fail, new_fail)

old_success = '''  if (planTrajToView(pos, vel, acc, yaw, next_pos, next_yaw) == FAIL) {
    return FAIL;
  }

  double total = (ros::Time::now() - t2).toSec();
'''
new_success = '''  if (planTrajToView(pos, vel, acc, yaw, next_pos, next_yaw) == FAIL) {
    return FAIL;
  }
  if (planner_consecutive_failures_ > 0) planner_consecutive_failures_ = 0;

  double total = (ros::Time::now() - t2).toSec();
'''
if old_success in cpp_s:
    cpp_s = cpp_s.replace(old_success, new_success)
elif "if (planner_consecutive_failures_ > 0) planner_consecutive_failures_ = 0;" not in cpp_s:
    raise SystemExit("could not patch success fail-streak reset")

if '<param name="planner_escape/v2_max_cost"' not in xml_s:
    xml_s = xml_s.replace(
        '    <param name="planner_escape/v2_min_clearance_m" value="0.35" type="double"/>\n'
        '    <param name="planner_escape/v2_memory_ttl_sec" value="180.0" type="double"/>\n',
        '    <param name="planner_escape/v2_min_clearance_m" value="0.35" type="double"/>\n'
        '    <param name="planner_escape/v2_memory_ttl_sec" value="180.0" type="double"/>\n'
        '    <param name="planner_escape/v2_max_cost" value="2500.0" type="double"/>\n',
    )

if dry:
    print("LE3_V2B_PATCH_DRY_RUN_OK")
else:
    hdr.write_text(hdr_s)
    cpp.write_text(cpp_s)
    xml.write_text(xml_s)
    print("LE3_V2B_PATCH_WRITTEN")
PY

if [[ "${1:-}" == "--dry-run" ]]; then
  echo "LE3_V2B_SAFETY_PATCH_DRY_RUN_PASS: $BACKUP_DIR"
else
  echo "LE3_V2B_SAFETY_PATCH_COMPLETE: $BACKUP_DIR"
fi
