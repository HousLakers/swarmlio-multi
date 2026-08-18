#!/usr/bin/env python3
"""Static contract checks for the LE8-H global trajectory safety patch."""

import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manager-source", required=True)
    parser.add_argument("--manager-header", required=True)
    parser.add_argument("--exploration-source", required=True)
    parser.add_argument("--exploration-header", required=True)
    parser.add_argument("--xml", required=True)
    args = parser.parse_args()

    manager = Path(args.manager_source).read_text()
    manager_header = Path(args.manager_header).read_text()
    exploration = Path(args.exploration_source).read_text()
    exploration_header = Path(args.exploration_header).read_text()
    xml = Path(args.xml).read_text()
    combined = manager + manager_header + exploration + exploration_header + xml

    markers = (
        "LE8H global_postplan_guard reject",
        "trajectory_safety_global_postplan_guard_enabled_",
        "trajectory_safety_reject_unknown_",
        "trajectory_safety_extra_clearance_m_",
        'recordViewpointFailure(pos, next_pos, failure_reason)',
        '"postplan_global_unsafe"',
        'region.reason != "postplan_global_unsafe"',
        "LE8H live_traj_guard reject",
        "traj_safety_reject_unknown_",
        "traj_safety_extra_clearance_m_",
        'trajectory_safety/global_postplan_guard_enabled',
        'trajectory_safety/reject_unknown',
        'trajectory_safety/extra_clearance_m',
    )
    missing = [marker for marker in markers if marker not in combined]
    assert not missing, f"LE8-H markers missing: {missing}"

    guard = exploration.index("LE8H global_postplan_guard reject")
    prefix = exploration[max(0, guard - 3500):guard]
    assert "trajectory_safety_global_postplan_guard_enabled_" in prefix
    assert "planner_escape_v2_goal_overridden_" not in prefix[-250:]
    assert "getInflateOccupancy(sample)" in prefix
    assert "getOccupancy(sample)" in prefix
    assert "getDistance(sample)" in prefix

    live = manager.index("LE8H live_traj_guard reject")
    live_prefix = manager[max(0, live - 1800):live]
    assert "getInflateOccupancy(fut_pt)" in live_prefix
    assert "getOccupancy(fut_pt)" in live_prefix
    assert "getDistance(fut_pt)" in live_prefix
    print("LE8H_GLOBAL_TRAJECTORY_SAFETY_PROBES_PASS")


if __name__ == "__main__":
    main()
