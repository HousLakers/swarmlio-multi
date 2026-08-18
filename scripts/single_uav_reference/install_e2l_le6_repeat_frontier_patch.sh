#!/usr/bin/env bash
# Install L-E6 repeat-frontier soft selection patch.
#
# The patch adds a second guarded soft-cost layer before the frontier TSP solve:
# repeated, low-gain frontier targets receive a bounded incoming-column penalty
# instead of being hard-pruned.  Defaults are disabled; runners enable variants
# through T1S4R_LSE_REPEAT_FRONTIER_* ROS params.
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
BACKUP_DIR="$ROOT/POST_E1_E2L_LE6_REPEAT_FRONTIER_PATCH_$STAMP"
mkdir -p "$BACKUP_DIR"
cp "$CPP" "$BACKUP_DIR/fast_exploration_manager.cpp.pre_le6_$STAMP"
cp "$HDR" "$BACKUP_DIR/fast_exploration_manager.h.pre_le6_$STAMP"
cp "$XML" "$BACKUP_DIR/single_drone_planner.xml.pre_le6_$STAMP"

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

if "applyTargetRepeatCosts" not in hdr_s:
    hdr_s = hdr_s.replace(
        "  void applyFailureMemoryCosts(\n"
        "      Eigen::MatrixXd& mat, const vector<int>& ftr_ids, int drone_num);\n",
        "  void applyFailureMemoryCosts(\n"
        "      Eigen::MatrixXd& mat, const vector<int>& ftr_ids, int drone_num);\n"
        "  void applyTargetRepeatCosts(\n"
        "      Eigen::MatrixXd& mat, const vector<int>& ftr_ids, int drone_num);\n",
    )

if "repeat_frontier_soft_enforce_" not in hdr_s:
    hdr_s = hdr_s.replace(
        "  double failure_frontier_max_fraction_, failure_frontier_penalty_ratio_;\n"
        "  bool all_frontiers_suppressed_;\n",
        "  double failure_frontier_max_fraction_, failure_frontier_penalty_ratio_;\n"
        "  bool repeat_frontier_soft_enforce_;\n"
        "  int repeat_frontier_threshold_, repeat_frontier_strong_threshold_;\n"
        "  double repeat_frontier_penalty_ratio_, repeat_frontier_max_fraction_;\n"
        "  double repeat_frontier_low_gain_threshold_, repeat_frontier_cooldown_sec_;\n"
        "  std::map<int, double> repeat_frontier_blocked_until_;\n"
        "  bool all_frontiers_suppressed_;\n",
    )

if "repeat_frontier_blocked_until_.clear();" not in cpp_s:
    cpp_s = cpp_s.replace(
        "  target_repeat_counts_.clear();\n",
        "  target_repeat_counts_.clear();\n"
        "  repeat_frontier_blocked_until_.clear();\n",
        1,
    )

if 'nh.param("planner_escape/repeat_frontier_soft_enforce"' not in cpp_s:
    cpp_s = cpp_s.replace(
        '  nh.param("planner_escape/fail_window_sec", planner_escape_fail_window_sec_, 12.0);\n',
        '  nh.param("planner_escape/fail_window_sec", planner_escape_fail_window_sec_, 12.0);\n'
        '  nh.param("planner_escape/repeat_frontier_soft_enforce", repeat_frontier_soft_enforce_, false);\n'
        '  nh.param("planner_escape/repeat_frontier_threshold", repeat_frontier_threshold_, 8);\n'
        '  nh.param("planner_escape/repeat_frontier_strong_threshold", repeat_frontier_strong_threshold_, 12);\n'
        '  nh.param("planner_escape/repeat_frontier_penalty_ratio", repeat_frontier_penalty_ratio_, 0.15);\n'
        '  nh.param("planner_escape/repeat_frontier_max_fraction", repeat_frontier_max_fraction_, 0.67);\n'
        '  nh.param("planner_escape/repeat_frontier_low_gain_threshold", repeat_frontier_low_gain_threshold_, 2.0);\n'
        '  nh.param("planner_escape/repeat_frontier_cooldown_sec", repeat_frontier_cooldown_sec_, 35.0);\n',
    )

if "applyTargetRepeatCosts(mat, ftr_ids, positions.size());" not in cpp_s:
    cpp_s = cpp_s.replace(
        "  applyFailureMemoryCosts(mat, ftr_ids, positions.size());\n"
        "  const int dimension = mat.rows();\n",
        "  applyFailureMemoryCosts(mat, ftr_ids, positions.size());\n"
        "  applyTargetRepeatCosts(mat, ftr_ids, positions.size());\n"
        "  const int dimension = mat.rows();\n",
    )

method = r'''
void FastExplorationManager::applyTargetRepeatCosts(
    Eigen::MatrixXd& mat, const vector<int>& ftr_ids, int drone_num) {
  if (!repeat_frontier_soft_enforce_) return;
  if (ftr_ids.size() < 2 || mat.rows() <= drone_num) {
    ROS_INFO("LE6 repeat_frontier_summary frontiers=%zu applied=0 reason=insufficient",
        ftr_ids.size());
    return;
  }

  vector<double> base_costs(ftr_ids.size(), 0.0);
  vector<double> penalties(ftr_ids.size(), 0.0);
  vector<double> finite_costs;
  for (int i = 0; i < static_cast<int>(ftr_ids.size()); ++i) {
    const int col = 1 + drone_num + i;
    if (col >= mat.cols()) continue;
    base_costs[i] = mat(drone_num, col);
    if (std::isfinite(base_costs[i]) && base_costs[i] > 0.0 && base_costs[i] < 10000.0)
      finite_costs.push_back(base_costs[i]);
  }
  double cost_median = 0.0;
  if (!finite_costs.empty()) {
    const size_t mid = finite_costs.size() / 2;
    std::nth_element(finite_costs.begin(), finite_costs.begin() + mid, finite_costs.end());
    cost_median = finite_costs[mid];
  }

  const double now = ros::Time::now().toSec();
  int matched = 0;
  int low_gain_count = 0;
  double max_ratio = 0.0;
  int best_idx = -1;
  double best_cost = std::numeric_limits<double>::infinity();
  for (int i = 0; i < static_cast<int>(base_costs.size()); ++i) {
    if (std::isfinite(base_costs[i]) && base_costs[i] > 0.0 && base_costs[i] < best_cost) {
      best_cost = base_costs[i];
      best_idx = i;
    }
  }

  const int repeat_threshold = std::max(1, repeat_frontier_threshold_);
  const int strong_threshold = std::max(repeat_threshold, repeat_frontier_strong_threshold_);
  for (int i = 0; i < static_cast<int>(ftr_ids.size()); ++i) {
    const int id = ftr_ids[i];
    if (id < 0 || id >= static_cast<int>(ed_->points_.size())) continue;
    if (!std::isfinite(base_costs[i]) || base_costs[i] <= 0.0 || cost_median <= 0.0) continue;

    int repeat = 0;
    auto repeat_it = target_repeat_counts_.find(id);
    if (repeat_it != target_repeat_counts_.end()) repeat = repeat_it->second;

    double gain = std::numeric_limits<double>::quiet_NaN();
    if (id >= 0 && id < static_cast<int>(ed_->yaws_.size())) {
      gain = static_cast<double>(frontier_finder_->computeGainOfView(ed_->points_[id], ed_->yaws_[id]));
    }
    const bool low_gain = std::isfinite(gain) && gain <= repeat_frontier_low_gain_threshold_;
    if (low_gain) ++low_gain_count;

    double blocked_until = 0.0;
    auto block_it = repeat_frontier_blocked_until_.find(id);
    if (block_it != repeat_frontier_blocked_until_.end()) blocked_until = block_it->second;
    const bool active_cooldown = blocked_until > now;

    if ((repeat >= strong_threshold || (repeat >= repeat_threshold && low_gain)) &&
        repeat_frontier_cooldown_sec_ > 0.0) {
      repeat_frontier_blocked_until_[id] = now + repeat_frontier_cooldown_sec_;
      blocked_until = repeat_frontier_blocked_until_[id];
    }

    if (repeat < repeat_threshold && blocked_until <= now) continue;

    double severity = 1.0;
    if (strong_threshold > repeat_threshold) {
      severity += std::min(1.0,
          static_cast<double>(std::max(0, repeat - repeat_threshold)) /
          static_cast<double>(strong_threshold - repeat_threshold));
    }
    if (low_gain) severity += 0.5;
    if (active_cooldown) severity = std::max(severity, 1.25);
    penalties[i] = std::min(repeat_frontier_penalty_ratio_ * base_costs[i] * severity,
        0.60 * std::max(base_costs[i], cost_median));
    if (penalties[i] > 0.0) {
      ++matched;
      max_ratio = std::max(max_ratio, penalties[i] / std::max(base_costs[i], 1e-3));
    }
  }

  if (matched == static_cast<int>(ftr_ids.size()) && best_idx >= 0 && penalties[best_idx] > 0.0) {
    penalties[best_idx] = 0.0;
    --matched;
  }

  const double fraction = ftr_ids.empty() ? 0.0 :
      static_cast<double>(matched) / static_cast<double>(ftr_ids.size());
  const bool guarded = matched > 0 && matched < static_cast<int>(ftr_ids.size()) &&
      fraction <= repeat_frontier_max_fraction_;
  if (guarded) {
    for (int i = 0; i < static_cast<int>(ftr_ids.size()); ++i) {
      const int col = 1 + drone_num + i;
      if (penalties[i] <= 0.0 || col >= mat.cols()) continue;
      for (int row = 0; row < mat.rows(); ++row) {
        if (row == col) continue;
        mat(row, col) += penalties[i];
      }
    }
  }
  ROS_INFO(
      "LE6 repeat_frontier_summary frontiers=%zu matched=%d fraction=%.3f guarded=%d "
      "applied=%d median=%.3f max_ratio=%.3f repeat_threshold=%d strong_threshold=%d "
      "low_gain=%d max_fraction=%.3f",
      ftr_ids.size(), matched, fraction, guarded ? 1 : 0, guarded ? 1 : 0,
      cost_median, max_ratio, repeat_threshold, strong_threshold,
      low_gain_count, repeat_frontier_max_fraction_);
}

'''

if "LE6 repeat_frontier_summary" not in cpp_s:
    anchor = "\n}  // namespace fast_planner\n"
    cpp_s = cpp_s.replace(anchor, "\n" + method + anchor)

if 'planner_escape/repeat_frontier_soft_enforce' not in xml_s:
    insert = (
        '    <param name="planner_escape/repeat_frontier_soft_enforce" value="false" type="bool"/>\n'
        '    <param name="planner_escape/repeat_frontier_threshold" value="8" type="int"/>\n'
        '    <param name="planner_escape/repeat_frontier_strong_threshold" value="12" type="int"/>\n'
        '    <param name="planner_escape/repeat_frontier_penalty_ratio" value="0.15" type="double"/>\n'
        '    <param name="planner_escape/repeat_frontier_max_fraction" value="0.67" type="double"/>\n'
        '    <param name="planner_escape/repeat_frontier_low_gain_threshold" value="2.0" type="double"/>\n'
        '    <param name="planner_escape/repeat_frontier_cooldown_sec" value="35.0" type="double"/>\n'
    )
    xml_s = xml_s.replace(
        '    <param name="planner_escape/fail_window_sec" value="12.0" type="double"/>\n',
        '    <param name="planner_escape/fail_window_sec" value="12.0" type="double"/>\n' + insert,
    )

if "applyTargetRepeatCosts" not in hdr_s:
    raise SystemExit("header patch failed: applyTargetRepeatCosts missing")
if "LE6 repeat_frontier_summary" not in cpp_s:
    raise SystemExit("cpp patch failed: LE6 repeat summary missing")
if "planner_escape/repeat_frontier_soft_enforce" not in xml_s:
    raise SystemExit("xml patch failed: repeat params missing")

if dry:
    print("LE6_REPEAT_FRONTIER_PATCH_DRY_RUN_OK")
else:
    cpp.write_text(cpp_s)
    hdr.write_text(hdr_s)
    xml.write_text(xml_s)
    print("LE6_REPEAT_FRONTIER_PATCH_APPLIED")
PY

echo "backup: $BACKUP_DIR"
