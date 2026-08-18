#!/usr/bin/env bash
# Install L-E7 gain-aware frontier ranking patch.
#
# LE7 keeps LE6 repeat-frontier late gating as a protection layer, but adds a
# gain-aware soft cost before the TSP solve so near/low-gain frontiers no longer
# win purely because they are close.
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
BACKUP_DIR="$ROOT/POST_E1_E2L_LE7_GAIN_RANK_PATCH_$STAMP"
mkdir -p "$BACKUP_DIR"
cp "$CPP" "$BACKUP_DIR/fast_exploration_manager.cpp.pre_le7_$STAMP"
cp "$HDR" "$BACKUP_DIR/fast_exploration_manager.h.pre_le7_$STAMP"
cp "$XML" "$BACKUP_DIR/single_drone_planner.xml.pre_le7_$STAMP"

python3 - "$CPP" "$HDR" "$XML" "${1:-}" <<'PY'
from pathlib import Path
import re
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

if "applyGainRankCosts" not in hdr_s:
    hdr_s = hdr_s.replace(
        "  void applyTargetRepeatCosts(\n"
        "      Eigen::MatrixXd& mat, const vector<int>& ftr_ids, int drone_num);\n",
        "  void applyTargetRepeatCosts(\n"
        "      Eigen::MatrixXd& mat, const vector<int>& ftr_ids, int drone_num);\n"
        "  void applyGainRankCosts(\n"
        "      Eigen::MatrixXd& mat, const vector<int>& ftr_ids, int drone_num);\n",
    )

if "repeat_frontier_max_penalty_ratio_" not in hdr_s:
    hdr_s = hdr_s.replace(
        "  double repeat_frontier_low_gain_threshold_, repeat_frontier_cooldown_sec_;\n",
        "  double repeat_frontier_low_gain_threshold_, repeat_frontier_cooldown_sec_;\n"
        "  double repeat_frontier_max_penalty_ratio_;\n",
    )

if "gain_rank_enforce_" not in hdr_s:
    hdr_s = hdr_s.replace(
        "  double repeat_frontier_max_penalty_ratio_;\n",
        "  double repeat_frontier_max_penalty_ratio_;\n"
        "  bool gain_rank_enforce_;\n"
        "  double gain_rank_gain_weight_, gain_rank_gain_cap_, gain_rank_bonus_ratio_;\n"
        "  double gain_rank_low_gain_threshold_, gain_rank_low_gain_penalty_ratio_;\n"
        "  double gain_rank_max_fraction_;\n",
    )

if 'nh.param("planner_escape/repeat_frontier_max_penalty_ratio"' not in cpp_s:
    cpp_s = cpp_s.replace(
        '  nh.param("planner_escape/repeat_frontier_cooldown_sec", repeat_frontier_cooldown_sec_, 35.0);\n',
        '  nh.param("planner_escape/repeat_frontier_cooldown_sec", repeat_frontier_cooldown_sec_, 35.0);\n'
        '  nh.param("planner_escape/repeat_frontier_max_penalty_ratio", repeat_frontier_max_penalty_ratio_, 0.30);\n',
    )

if 'nh.param("planner_escape/gain_rank_enforce"' not in cpp_s:
    cpp_s = cpp_s.replace(
        '  nh.param("planner_escape/repeat_frontier_max_penalty_ratio", repeat_frontier_max_penalty_ratio_, 0.30);\n',
        '  nh.param("planner_escape/repeat_frontier_max_penalty_ratio", repeat_frontier_max_penalty_ratio_, 0.30);\n'
        '  nh.param("planner_escape/gain_rank_enforce", gain_rank_enforce_, false);\n'
        '  nh.param("planner_escape/gain_rank_gain_weight", gain_rank_gain_weight_, 0.06);\n'
        '  nh.param("planner_escape/gain_rank_gain_cap", gain_rank_gain_cap_, 20.0);\n'
        '  nh.param("planner_escape/gain_rank_bonus_ratio", gain_rank_bonus_ratio_, 0.18);\n'
        '  nh.param("planner_escape/gain_rank_low_gain_threshold", gain_rank_low_gain_threshold_, 2.0);\n'
        '  nh.param("planner_escape/gain_rank_low_gain_penalty_ratio", gain_rank_low_gain_penalty_ratio_, 0.08);\n'
        '  nh.param("planner_escape/gain_rank_max_fraction", gain_rank_max_fraction_, 0.75);\n',
    )

if "applyGainRankCosts(mat, ftr_ids, positions.size());" not in cpp_s:
    cpp_s = cpp_s.replace(
        "  applyFailureMemoryCosts(mat, ftr_ids, positions.size());\n"
        "  applyTargetRepeatCosts(mat, ftr_ids, positions.size());\n",
        "  applyFailureMemoryCosts(mat, ftr_ids, positions.size());\n"
        "  applyGainRankCosts(mat, ftr_ids, positions.size());\n"
        "  applyTargetRepeatCosts(mat, ftr_ids, positions.size());\n",
    )

if "repeat_frontier_max_penalty_ratio_" in hdr_s and "repeat_frontier_max_penalty_ratio_ * base_costs[i]" not in cpp_s:
    cpp_s = cpp_s.replace(
        "    penalties[i] = std::min(repeat_frontier_penalty_ratio_ * base_costs[i] * severity,\n"
        "        0.60 * std::max(base_costs[i], cost_median));\n",
        "    penalties[i] = std::min(repeat_frontier_penalty_ratio_ * base_costs[i] * severity,\n"
        "        repeat_frontier_max_penalty_ratio_ * base_costs[i]);\n",
    )

method = r'''
void FastExplorationManager::applyGainRankCosts(
    Eigen::MatrixXd& mat, const vector<int>& ftr_ids, int drone_num) {
  if (!gain_rank_enforce_) return;
  if (ftr_ids.empty() || mat.rows() <= drone_num) {
    ROS_INFO("LE7 gain_rank_summary frontiers=%zu applied=0 reason=insufficient",
        ftr_ids.size());
    return;
  }

  vector<double> base_costs(ftr_ids.size(), 0.0);
  vector<double> bonus_deltas(ftr_ids.size(), 0.0);
  vector<double> penalty_deltas(ftr_ids.size(), 0.0);
  vector<double> finite_gains;
  vector<double> gains(ftr_ids.size(), 0.0);
  vector<int> gain_ok(ftr_ids.size(), 0);
  for (int i = 0; i < static_cast<int>(ftr_ids.size()); ++i) {
    const int id = ftr_ids[i];
    const int col = 1 + drone_num + i;  // frontier i column (depot 0, drones 1..drone_num)
    if (col >= mat.cols() || id < 0 || id >= static_cast<int>(ed_->points_.size())) continue;
    base_costs[i] = mat(drone_num, col);  // drone-0 row (row 1 when drone_num == 1)
    if (!std::isfinite(base_costs[i]) || base_costs[i] <= 0.0) continue;
    if (id < static_cast<int>(ed_->yaws_.size())) {
      const double gain = static_cast<double>(
          frontier_finder_->computeGainOfView(ed_->points_[id], ed_->yaws_[id]));
      if (std::isfinite(gain)) {
        gains[i] = std::max(0.0, gain);
        gain_ok[i] = 1;
        finite_gains.push_back(gains[i]);
      }
    }
  }
  if (finite_gains.empty()) {
    ROS_INFO("LE7 gain_rank_summary frontiers=%zu applied=0 reason=no_gain", ftr_ids.size());
    return;
  }

  vector<double> sorted_gains = finite_gains;
  const size_t mid = sorted_gains.size() / 2;
  std::nth_element(sorted_gains.begin(), sorted_gains.begin() + mid, sorted_gains.end());
  const double median_gain = sorted_gains[mid];

  int boosted = 0;
  int penalized = 0;
  int finite = 0;
  int best_idx = -1;
  double best_gain = -1.0;
  double best_base = 0.0;
  double max_bonus_ratio = 0.0;
  double max_penalty_ratio = 0.0;
  for (int i = 0; i < static_cast<int>(ftr_ids.size()); ++i) {
    if (!gain_ok[i]) continue;
    if (!std::isfinite(base_costs[i]) || base_costs[i] <= 0.0) continue;

    const double gain = gains[i];
    ++finite;
    if (gain > best_gain || (std::fabs(gain - best_gain) <= 1e-9 &&
        (best_idx < 0 || base_costs[i] < best_base))) {
      best_idx = i;
      best_gain = gain;
      best_base = base_costs[i];
    }

    const double capped_gain = std::min(gain, std::max(0.0, gain_rank_gain_cap_));
    double bonus = std::min(gain_rank_gain_weight_ * capped_gain,
        gain_rank_bonus_ratio_ * base_costs[i]);
    if (median_gain > 0.0 && gain < median_gain * 0.75) {
      bonus *= 0.35;
    }
    if (bonus > 0.0) {
      bonus_deltas[i] -= bonus;
      ++boosted;
      max_bonus_ratio = std::max(max_bonus_ratio, bonus / std::max(base_costs[i], 1e-3));
    }

    if (gain <= gain_rank_low_gain_threshold_ && gain_rank_low_gain_penalty_ratio_ > 0.0) {
      const double penalty = gain_rank_low_gain_penalty_ratio_ * base_costs[i];
      penalty_deltas[i] += penalty;
      ++penalized;
      max_penalty_ratio = std::max(max_penalty_ratio, penalty / std::max(base_costs[i], 1e-3));
    }
  }

  const double affected_fraction = ftr_ids.empty() ? 0.0 :
      static_cast<double>(boosted + penalized) / static_cast<double>(ftr_ids.size());
  const double penalty_fraction = ftr_ids.empty() ? 0.0 :
      static_cast<double>(penalized) / static_cast<double>(ftr_ids.size());
  const bool penalty_guarded = penalty_fraction <= gain_rank_max_fraction_;
  int applied_cols = 0;
  int fallback_cols = 0;
  if (finite > 0) {
    for (int i = 0; i < static_cast<int>(ftr_ids.size()); ++i) {
      const int col = 1 + drone_num + i;
      if (col >= mat.cols()) continue;
      double delta = bonus_deltas[i];
      if (penalty_guarded) delta += penalty_deltas[i];
      if (std::fabs(delta) <= 1e-9) continue;
      ++applied_cols;
      for (int row = 0; row < mat.rows(); ++row) {
        if (row == col) continue;
        mat(row, col) = std::max(0.01, mat(row, col) + delta);
      }
    }
    if (applied_cols == 0 && best_idx >= 0) {
      const int col = 1 + drone_num + best_idx;
      if (col < mat.cols() && std::isfinite(base_costs[best_idx]) && base_costs[best_idx] > 0.0) {
        const double fallback_bonus = std::min(
            0.05 * base_costs[best_idx],
            std::max(0.05, gain_rank_bonus_ratio_ * base_costs[best_idx] * 0.25));
        for (int row = 0; row < mat.rows(); ++row) {
          if (row == col) continue;
          mat(row, col) = std::max(0.01, mat(row, col) - fallback_bonus);
        }
        applied_cols = 1;
        fallback_cols = 1;
        max_bonus_ratio = std::max(max_bonus_ratio,
            fallback_bonus / std::max(base_costs[best_idx], 1e-3));
      }
    }
  }
  ROS_INFO(
      "LE7 gain_rank_summary frontiers=%zu finite=%d boosted=%d penalized=%d "
      "fraction=%.3f penalty_fraction=%.3f penalty_guarded=%d applied=%d "
      "applied_cols=%d fallback_cols=%d median_gain=%.3f max_bonus_ratio=%.3f max_penalty_ratio=%.3f "
      "gain_weight=%.3f",
      ftr_ids.size(), finite, boosted, penalized, affected_fraction, penalty_fraction,
      penalty_guarded ? 1 : 0, applied_cols > 0 ? 1 : 0, applied_cols, fallback_cols,
      median_gain, max_bonus_ratio, max_penalty_ratio, gain_rank_gain_weight_);
}

'''

method_start = "\nvoid FastExplorationManager::applyGainRankCosts("
method_end = "\nvoid FastExplorationManager::applyTargetRepeatCosts("
start_idx = cpp_s.find(method_start)
end_idx = cpp_s.find(method_end)
if start_idx >= 0 and end_idx > start_idx:
    cpp_s = cpp_s[:start_idx] + "\n" + method + cpp_s[end_idx:]
elif "LE7 gain_rank_summary" not in cpp_s:
    cpp_s = cpp_s.replace("\nvoid FastExplorationManager::applyTargetRepeatCosts(\n",
                          "\n" + method + "\nvoid FastExplorationManager::applyTargetRepeatCosts(\n")

if 'planner_escape/repeat_frontier_max_penalty_ratio' not in xml_s:
    xml_s = xml_s.replace(
        '    <param name="planner_escape/repeat_frontier_cooldown_sec" value="35.0" type="double"/>\n',
        '    <param name="planner_escape/repeat_frontier_cooldown_sec" value="35.0" type="double"/>\n'
        '    <param name="planner_escape/repeat_frontier_max_penalty_ratio" value="0.30" type="double"/>\n',
    )

if 'planner_escape/gain_rank_enforce' not in xml_s:
    xml_s = xml_s.replace(
        '    <param name="planner_escape/repeat_frontier_max_penalty_ratio" value="0.30" type="double"/>\n',
        '    <param name="planner_escape/repeat_frontier_max_penalty_ratio" value="0.30" type="double"/>\n'
        '    <param name="planner_escape/gain_rank_enforce" value="false" type="bool"/>\n'
        '    <param name="planner_escape/gain_rank_gain_weight" value="0.06" type="double"/>\n'
        '    <param name="planner_escape/gain_rank_gain_cap" value="20.0" type="double"/>\n'
        '    <param name="planner_escape/gain_rank_bonus_ratio" value="0.18" type="double"/>\n'
        '    <param name="planner_escape/gain_rank_low_gain_threshold" value="2.0" type="double"/>\n'
        '    <param name="planner_escape/gain_rank_low_gain_penalty_ratio" value="0.08" type="double"/>\n'
        '    <param name="planner_escape/gain_rank_max_fraction" value="0.75" type="double"/>\n',
    )

required = [
    "applyGainRankCosts", "LE7 gain_rank_summary",
    "planner_escape/gain_rank_enforce", "repeat_frontier_max_penalty_ratio_",
    "mat(drone_num, col)", "penalty_fraction", "applied_cols", "fallback_cols",
]
joined = "\n".join([cpp_s, hdr_s, xml_s])
missing = [item for item in required if item not in joined]
if missing:
    raise SystemExit("LE7 patch failed, missing: " + ", ".join(missing))

if dry:
    print("LE7_GAIN_RANK_PATCH_DRY_RUN_OK")
else:
    cpp.write_text(cpp_s)
    hdr.write_text(hdr_s)
    xml.write_text(xml_s)
    print("LE7_GAIN_RANK_PATCH_APPLIED")
PY

echo "backup: $BACKUP_DIR"
