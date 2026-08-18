#!/usr/bin/env python3
"""Static contract checks for the LE8-G v2 trajectory liveness patch."""

import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--header", required=True)
    parser.add_argument("--xml", required=True)
    args = parser.parse_args()

    source = Path(args.source).read_text()
    header = Path(args.header).read_text()
    xml = Path(args.xml).read_text()
    combined = source + header + xml
    markers = (
        "planner_escape_v2_progress_guard_enabled_",
        "const bool optimistic = ed_->plan_num_ < ep_->init_plan_num_;",
        "search(pos, cand, optimistic)",
        "LE8G LE6 true frontier column",
        "LE8G memory true frontier column",
        "base_costs[i] = mat(drone_num, col);",
        "LE8G v2_escape low_speed_episode",
        "LE8G v2 memory is independent",
        "planner_escape_v2_progress_horizon_sec_",
        "planner_escape_v2_min_progress_xy_m_",
        "LE8G v2_progress_guard reject",
        "LE8G v2_progress_guard pass",
        'recordViewpointFailure(pos, next_pos, "postplan_no_progress")',
        'notePlannerPlanFail("postplan_no_progress")',
        'planner_escape/v2_progress_guard_enabled',
    )
    missing = [marker for marker in markers if marker not in combined]
    assert not missing, f"LE8-G markers missing: {missing}"

    # Scope contract: the liveness gate is restricted to v2 overrides. Normal
    # exploration trajectories must not be rejected by this new check.
    guard = source.index("LE8G v2_progress_guard reject")
    prefix = source[max(0, guard - 1800):guard]
    assert "planner_escape_v2_goal_overridden_" in prefix
    assert "max_progress_xy" in prefix

    repeat_start = source.index("void FastExplorationManager::applyTargetRepeatCosts")
    repeat_body = source[repeat_start:source.index("}  // namespace fast_planner", repeat_start)]
    assert "const int col = drone_num + i" not in repeat_body
    assert repeat_body.count("const int col = 1 + drone_num + i") >= 2

    memory_start = source.index("void FastExplorationManager::applyFailureMemoryCosts")
    gain_start = source.index("void FastExplorationManager::applyGainRankCosts", memory_start)
    memory_body = source[memory_start:gain_start]
    assert "const int col = drone_num + i" not in memory_body
    assert memory_body.count("const int col = 1 + drone_num + i") >= 2
    assert "base_costs[i] = mat(drone_num, col)" in memory_body
    print("LE8G_OFFLINE_PROBES_PASS")


if __name__ == "__main__":
    main()
