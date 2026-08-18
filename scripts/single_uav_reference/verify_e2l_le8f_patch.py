#!/usr/bin/env python3
"""Offline source and decision probes for LE8-F."""

import argparse
import pathlib

from e2l_runtime_param_gate import check_runtime_params


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=(
        "/home/houslakers/racer_ws/src/RACER/swarm_exploration/"
        "exploration_manager/src/fast_exploration_manager.cpp"
    ))
    args = parser.parse_args()
    source = pathlib.Path(args.source).read_text()
    markers = (
        "LE8F reachable_candidate",
        "Astar::REACH_END",
        "Astar::pathLength(path)",
        "const bool optimistic = ed_->plan_num_ < ep_->init_plan_num_;",
        "search(pos, cand, optimistic)",
        "for (int k = 0; k < 16; ++k)",
        "LE8F v2_escape geometric_fallback tested=",
        '<< " reachable=" << fallback_reachable',
    )
    assert all(marker in source for marker in markers), "LE8-F source markers missing"

    # The old fallback tested at most 5 heading-derived directions. The fixed
    # sweep always contains inward diagonals at all four corners.
    directions = [(k * 22.5) % 360 for k in range(16)]
    for inward in (45.0, 135.0, 225.0, 315.0):
        assert inward in directions

    bridge = pathlib.Path("low_speed_action_bridge.py").read_text()
    assert "row.get('cooldown_until_ros', '')" in bridge
    gate = pathlib.Path("run_e2l_le8c_pure_postplan_gate.sh").read_text()
    assert 'quality_errors.append("frozen")' in gate
    sample = """
 * /exploration_node_1/sdf_map/obstacles_inflation: 0.4
 * /exploration_node_1/planner_escape/v2_boundary_guard_enabled: False
"""
    actual, errors = check_runtime_params(sample, {
        "/exploration_node_1/sdf_map/obstacles_inflation": 0.40,
        "/exploration_node_1/planner_escape/v2_boundary_guard_enabled": False,
    })
    assert not errors, (actual, errors)
    _, errors = check_runtime_params(sample, {
        "/exploration_node_1/sdf_map/obstacles_inflation": 0.35,
    })
    assert errors and errors[0].startswith("param_mismatch:"), errors
    print("LE8F_OFFLINE_PROBES_PASS")


if __name__ == "__main__":
    main()
