#!/usr/bin/env bash
# Install L-E4c soft-memory patch.
# Goal: keep low-speed failure memory active, but prevent hard frontier pruning
# from emptying all candidates before v2 escape can apply.
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
BACKUP_DIR="$ROOT/POST_E1_E2L_LE4C_SOFT_MEMORY_PATCH_$STAMP"
mkdir -p "$BACKUP_DIR"
cp "$CPP" "$BACKUP_DIR/fast_exploration_manager.cpp.pre_le4c_$STAMP"
cp "$HDR" "$BACKUP_DIR/fast_exploration_manager.h.pre_le4c_$STAMP"
cp "$XML" "$BACKUP_DIR/single_drone_planner.xml.pre_le4c_$STAMP"

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

if "failure_memory_hard_prune_" not in hdr_s:
    hdr_s = hdr_s.replace(
        "  bool failure_memory_enforce_low_speed_only_;\n",
        "  bool failure_memory_enforce_low_speed_only_;\n"
        "  bool failure_memory_hard_prune_;\n",
    )

if 'nh.param("failure_memory/hard_prune"' not in cpp_s:
    cpp_s = cpp_s.replace(
        '  nh.param("failure_memory/enforce_low_speed_only", failure_memory_enforce_low_speed_only_, false);\n'
        '  nh.param("failure_memory/shadow", failure_memory_shadow_, false);\n',
        '  nh.param("failure_memory/enforce_low_speed_only", failure_memory_enforce_low_speed_only_, false);\n'
        '  nh.param("failure_memory/hard_prune", failure_memory_hard_prune_, true);\n'
        '  nh.param("failure_memory/shadow", failure_memory_shadow_, false);\n',
    )

old = '''  all_frontiers_suppressed_ = false;
  if (failure_memory_enabled_ && failure_memory_enforce_ && !ftr_ids.empty()) {
    vector<int> available_ids;
    available_ids.reserve(ftr_ids.size());
    for (const int id : ftr_ids) {
      if (id >= 0 && id < static_cast<int>(ed_->points_.size()) &&
          failureMemoryBlacklisted(ed_->points_[id])) {
        const auto& point = ed_->points_[id];
        ROS_WARN("S3F blacklist_skip frontier=%d x=%.3f y=%.3f z=%.3f", id, point.x(),
            point.y(), point.z());
        continue;
      }
      available_ids.push_back(id);
    }
    if (available_ids.empty()) {
      all_frontiers_suppressed_ = true;
      ROS_WARN("S3F memory_pruned_no_path frontiers=%zu", ftr_ids.size());
      frontier_ids.clear();
      return;
    }
    ftr_ids.swap(available_ids);
  }
'''
new = '''  all_frontiers_suppressed_ = false;
  if (failure_memory_enabled_ && failure_memory_enforce_ && failure_memory_hard_prune_ &&
      !ftr_ids.empty()) {
    vector<int> available_ids;
    available_ids.reserve(ftr_ids.size());
    for (const int id : ftr_ids) {
      if (id >= 0 && id < static_cast<int>(ed_->points_.size()) &&
          failureMemoryBlacklisted(ed_->points_[id])) {
        const auto& point = ed_->points_[id];
        ROS_WARN("S3F blacklist_skip frontier=%d x=%.3f y=%.3f z=%.3f", id, point.x(),
            point.y(), point.z());
        continue;
      }
      available_ids.push_back(id);
    }
    if (available_ids.empty()) {
      all_frontiers_suppressed_ = true;
      ROS_WARN("S3F memory_pruned_no_path frontiers=%zu", ftr_ids.size());
      frontier_ids.clear();
      return;
    }
    ftr_ids.swap(available_ids);
  } else if (failure_memory_enabled_ && failure_memory_enforce_ && !ftr_ids.empty()) {
    int soft_kept = 0;
    for (const int id : ftr_ids) {
      if (id >= 0 && id < static_cast<int>(ed_->points_.size()) &&
          failureMemoryBlacklisted(ed_->points_[id])) {
        ++soft_kept;
      }
    }
    if (soft_kept > 0) {
      ROS_WARN("S3F blacklist_soft_keep frontiers=%zu matched=%d hard_prune=false",
          ftr_ids.size(), soft_kept);
    }
  }
'''
if old in cpp_s:
    cpp_s = cpp_s.replace(old, new, 1)
elif "blacklist_soft_keep" not in cpp_s:
    raise SystemExit("could not find hard-prune frontier block")

lines = xml_s.splitlines()
out = []
inserted = False
safe_defaults = {
    "failure_memory/enabled": "false",
    "failure_memory/enforce": "false",
    "failure_memory/enforce_low_speed_only": "false",
    "failure_memory/hard_prune": "false",
    "failure_memory/shadow": "false",
    "failure_memory/local_enforce": "false",
    "failure_memory/region_size_m": "0.5",
    "failure_memory/cooldown_sec": "15.0",
    "failure_memory/blacklist_threshold": "999",
    "failure_memory/blacklist_sec": "60.0",
    "failure_memory/forget_sec": "90.0",
    "failure_memory/cost_penalty": "0.0",
    "failure_memory/kino_scale": "0.0",
}
for line in lines:
    for name, value in safe_defaults.items():
        needle = f'<param name="{name}"'
        if needle in line:
            param_type = 'bool' if value in ("true", "false") else line.split('type="', 1)[1].split('"', 1)[0]
            line = f'    <param name="{name}" value="{value}" type="{param_type}"/>'
            break
    out.append(line)
    if '<param name="failure_memory/enforce_low_speed_only"' in line:
        inserted = True
        if not any('failure_memory/hard_prune' in item for item in lines):
            out.append('    <param name="failure_memory/hard_prune" value="false" type="bool"/>')
xml_s = "\n".join(out) + "\n"

if not inserted and 'failure_memory/hard_prune' not in xml_s:
    raise SystemExit("could not place failure_memory/hard_prune XML param")

if dry:
    print("LE4C_SOFT_MEMORY_PATCH_DRY_RUN_OK")
else:
    cpp.write_text(cpp_s)
    hdr.write_text(hdr_s)
    xml.write_text(xml_s)
    print("LE4C_SOFT_MEMORY_PATCH_WRITTEN")
PY

if [[ "${1:-}" == "--dry-run" ]]; then
  echo "LE4C_SOFT_MEMORY_PATCH_DRY_RUN_PASS: $BACKUP_DIR"
else
  echo "LE4C_SOFT_MEMORY_PATCH_COMPLETE: $BACKUP_DIR"
fi
