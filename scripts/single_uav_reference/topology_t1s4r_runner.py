#!/usr/bin/env python3
"""T1S-4R: 6-run integration smoke with strict telemetry and safety gates."""
import json
import math
import os
import signal
import subprocess
import time
from pathlib import Path

import s2_rsm_runner as s2
import s3f_ab_runner as base
import topology_t1s0_runner as t1s0
import topology_t1s0m_runner as t1s0m
import topology_t1s1d_runner as diag
import t1s4r_telemetry_validity as tv

HERE = Path(__file__).resolve().parent
STATE = HERE / 'topology_t1s4r_state.json'
MANIFEST = HERE / 'topology_t1s4r_manifest.json'
PLANNER_SAMPLER = HERE / 'planner_degradation_sampler.py'
LOW_SPEED_SAMPLER = HERE / 'low_speed_shadow_sampler.py'
LOW_SPEED_ACTION_BRIDGE = HERE / 'low_speed_action_bridge.py'
TARGET_CONTEXT_SAMPLER = HERE / 'target_context_sampler.py'
MAX_CONSEC_INFRA_FAIL = 2


def classify_invalid(row, reasons, report):
    """Return a stable failure class; only launch/infrastructure failures block a batch."""
    if not row.get('result_dir'):
        return 'infra'
    if any(str(r).startswith(('runner_error:', 'no_result_dir:', 'quality_metrics_error:')) for r in reasons):
        return 'infra'
    events = (report or {}).get('safety_events', {}) or {}
    if events.get('gazebo_contact') or events.get('crashed') or events.get('mavros_time_jump') or events.get('trajectory_collision'):
        return 'safety'
    if any(str(r).startswith('telemetry_coverage_low:') for r in reasons):
        return 'telemetry'
    return 'algorithm'

COMMON = dict(t1s0.COMMON_PARAMS)
BASE = {
    'fsm/sliding_recovery_enabled': 'false',
    'fsm/sliding_recovery_window': '15.0',
    'fsm/sliding_recovery_displacement': '1.0',
    'fsm/sliding_recovery_mean_speed': '0.20',
    'fsm/sliding_recovery_current_speed': '0.25',
    'fsm/sliding_recovery_good_evals_required': '3',
    'fsm/sliding_recovery_cooldown': '45.0',
    'fsm/sliding_recovery_max_count': '2',
    'fsm/stagnation_recovery_enabled': 'false',
    'planner_escape/shadow': 'false',
    'planner_escape/enabled': 'false',
    'planner_escape/fusion_enabled': 'false',
    'planner_escape/consecutive_fail_threshold': '5',
    'planner_escape/repeat_fraction_threshold': '0.28',
    'planner_escape/max_escape_count': '1',
    'planner_escape/cooldown_sec': '60.0',
    'planner_escape/cluster_suppress_sec': '30.0',
    'planner_escape/topology_bonus': '0.10',
    'planner_escape/cluster_radius_m': '2.5',
}

R1_R2 = dict(BASE, **{'fsm/sliding_recovery_enabled': 'true'})
R3_R4 = dict(BASE, **{
    'fsm/sliding_recovery_enabled': 'true',
    'planner_escape/shadow': 'true',
})
R5_R6 = dict(BASE, **{
    'fsm/sliding_recovery_enabled': 'true',
    'planner_escape/shadow': 'true',
    'planner_escape/enabled': 'true',
    'planner_escape/fusion_enabled': 'true',
})

FSM_PROFILES = {
    'strict': {
        'fsm/sliding_recovery_window': '15.0',
        'fsm/sliding_recovery_displacement': '1.0',
        'fsm/sliding_recovery_mean_speed': '0.20',
        'fsm/sliding_recovery_current_speed': '0.25',
        'fsm/sliding_recovery_good_evals_required': '3',
        'fsm/sliding_recovery_cooldown': '45.0',
    },
    'balanced': {
        'fsm/sliding_recovery_window': '12.0',
        'fsm/sliding_recovery_displacement': '1.2',
        'fsm/sliding_recovery_mean_speed': '0.25',
        'fsm/sliding_recovery_current_speed': '0.30',
        'fsm/sliding_recovery_good_evals_required': '2',
        'fsm/sliding_recovery_cooldown': '30.0',
    },
    'sensitive': {
        'fsm/sliding_recovery_window': '10.0',
        'fsm/sliding_recovery_displacement': '1.5',
        'fsm/sliding_recovery_mean_speed': '0.30',
        'fsm/sliding_recovery_current_speed': '0.35',
        'fsm/sliding_recovery_good_evals_required': '1',
        'fsm/sliding_recovery_cooldown': '20.0',
    },
}

SEQUENCE = (
    ('r1', 'center', 'fsm2', R1_R2),
    ('r2', 'incumbent', 'fsm2', R1_R2),
    ('r3', 'center', 'shadow', R3_R4),
    ('r4', 'incumbent', 'shadow', R3_R4),
    ('r5', 'center', 'fusion', R5_R6),
    ('r6', 'incumbent', 'fusion', R5_R6),
)


def build_trials():
    profile_name = os.environ.get('T1S4R_FSM_PROFILE', 'strict')
    if profile_name not in FSM_PROFILES:
        raise ValueError(f'unknown T1S4R_FSM_PROFILE={profile_name}')
    fsm_profile = FSM_PROFILES[profile_name]
    group = os.environ.get('T1S4R_GROUP', 'native')
    lse_max_escape_count = os.environ.get('T1S4R_LSE_MAX_ESCAPE_COUNT', '2')
    lse_cooldown_sec = os.environ.get('T1S4R_LSE_COOLDOWN_SEC', '45.0')
    lse_urgent_cooldown_sec = os.environ.get('T1S4R_LSE_URGENT_COOLDOWN_SEC', lse_cooldown_sec)
    lse_cluster_suppress_sec = os.environ.get('T1S4R_LSE_CLUSTER_SUPPRESS_SEC', '60.0')
    lse_topology_bonus = os.environ.get('T1S4R_LSE_TOPOLOGY_BONUS', '0.30')
    lse_cluster_radius_m = os.environ.get('T1S4R_LSE_CLUSTER_RADIUS_M', '4.5')
    lse_v2_enabled = os.environ.get('T1S4R_LSE_V2_ENABLED', 'false')
    lse_v2_clear_radius_m = os.environ.get('T1S4R_LSE_V2_CLEAR_RADIUS_M', '6.0')
    lse_v2_min_step_m = os.environ.get('T1S4R_LSE_V2_MIN_STEP_M', '3.0')
    lse_v2_max_step_m = os.environ.get('T1S4R_LSE_V2_MAX_STEP_M', '8.0')
    lse_v2_ttl_sec = os.environ.get('T1S4R_LSE_V2_TTL_SEC', '90.0')
    lse_v2_min_clearance_m = os.environ.get('T1S4R_LSE_V2_MIN_CLEARANCE_M', '0.35')
    lse_v2_max_cost = os.environ.get('T1S4R_LSE_V2_MAX_COST', '10000.0')
    lse_v2_trigger_on_planner_fail = os.environ.get('T1S4R_LSE_V2_TRIGGER_ON_PLANNER_FAIL', 'true')
    lse_v2_target_repeat_threshold = os.environ.get('T1S4R_LSE_V2_TARGET_REPEAT_THRESHOLD', '8')
    lse_v2_sticky_center = os.environ.get('T1S4R_LSE_V2_STICKY_CENTER', 'false')
    lse_v2_failed_target_memory = os.environ.get(
        'T1S4R_LSE_V2_FAILED_TARGET_MEMORY', 'false')
    lse_v2_failed_target_radius_m = os.environ.get(
        'T1S4R_LSE_V2_FAILED_TARGET_RADIUS_M', '0.8')
    lse_v2_boundary_guard_enabled = os.environ.get(
        'T1S4R_LSE_V2_BOUNDARY_GUARD_ENABLED', 'false')
    lse_v2_boundary_margin_xy_m = os.environ.get(
        'T1S4R_LSE_V2_BOUNDARY_MARGIN_XY_M', '0.0')
    lse_v2_postplan_guard_enabled = os.environ.get(
        'T1S4R_LSE_V2_POSTPLAN_GUARD_ENABLED', 'false')
    lse_v2_postplan_dt_sec = os.environ.get(
        'T1S4R_LSE_V2_POSTPLAN_DT_SEC', '0.05')
    lse_v2_progress_guard_configured = (
        'T1S4R_LSE_V2_PROGRESS_GUARD_ENABLED' in os.environ)
    lse_v2_progress_guard_enabled = os.environ.get(
        'T1S4R_LSE_V2_PROGRESS_GUARD_ENABLED', 'false')
    lse_v2_progress_horizon_sec = os.environ.get(
        'T1S4R_LSE_V2_PROGRESS_HORIZON_SEC', '1.6')
    lse_v2_min_progress_xy_m = os.environ.get(
        'T1S4R_LSE_V2_MIN_PROGRESS_XY_M', '0.25')
    global_traj_guard_configured = (
        'T1S4R_GLOBAL_TRAJ_GUARD_ENABLED' in os.environ)
    global_traj_guard_enabled = os.environ.get(
        'T1S4R_GLOBAL_TRAJ_GUARD_ENABLED', 'false')
    global_traj_reject_unknown = os.environ.get(
        'T1S4R_GLOBAL_TRAJ_REJECT_UNKNOWN', 'false')
    global_traj_boundary_margin_xy_m = os.environ.get(
        'T1S4R_GLOBAL_TRAJ_BOUNDARY_MARGIN_XY_M', '0.50')
    global_traj_extra_clearance_m = os.environ.get(
        'T1S4R_GLOBAL_TRAJ_EXTRA_CLEARANCE_M', '0.10')
    global_traj_dt_sec = os.environ.get(
        'T1S4R_GLOBAL_TRAJ_DT_SEC', '0.05')
    obstacles_inflation = os.environ.get('T1S4R_OBSTACLES_INFLATION', '0.35')
    lse_memory_enabled = os.environ.get('T1S4R_LSE_MEMORY_ENABLED', 'false')
    lse_memory_enforce = os.environ.get('T1S4R_LSE_MEMORY_ENFORCE', 'false')
    lse_memory_enforce_low_speed_only = os.environ.get('T1S4R_LSE_MEMORY_ENFORCE_LOW_SPEED_ONLY', 'true')
    lse_memory_hard_prune = os.environ.get('T1S4R_LSE_MEMORY_HARD_PRUNE', 'false')
    lse_memory_local_enforce = os.environ.get('T1S4R_LSE_MEMORY_LOCAL_ENFORCE', 'false')
    lse_memory_frontier_soft_enforce = os.environ.get('T1S4R_LSE_MEMORY_FRONTIER_SOFT_ENFORCE', 'false')
    lse_memory_frontier_max_fraction = os.environ.get('T1S4R_LSE_MEMORY_FRONTIER_MAX_FRACTION', '0.67')
    lse_memory_frontier_penalty_ratio = os.environ.get('T1S4R_LSE_MEMORY_FRONTIER_PENALTY_RATIO', '0.25')
    lse_memory_region_size_m = os.environ.get('T1S4R_LSE_MEMORY_REGION_SIZE_M', '4.5')
    lse_memory_cooldown_sec = os.environ.get('T1S4R_LSE_MEMORY_COOLDOWN_SEC', '90.0')
    lse_memory_blacklist_threshold = os.environ.get('T1S4R_LSE_MEMORY_BLACKLIST_THRESHOLD', '1')
    lse_memory_blacklist_sec = os.environ.get('T1S4R_LSE_MEMORY_BLACKLIST_SEC', '120.0')
    lse_memory_forget_sec = os.environ.get('T1S4R_LSE_MEMORY_FORGET_SEC', '180.0')
    lse_memory_cost_penalty = os.environ.get('T1S4R_LSE_MEMORY_COST_PENALTY', '3.0')
    lse_fail_window_sec = os.environ.get('T1S4R_LSE_FAIL_WINDOW_SEC', '12.0')
    lse_repeat_frontier_soft_enforce = os.environ.get(
        'T1S4R_LSE_REPEAT_FRONTIER_SOFT_ENFORCE', 'false')
    lse_repeat_frontier_threshold = os.environ.get(
        'T1S4R_LSE_REPEAT_FRONTIER_THRESHOLD', '8')
    lse_repeat_frontier_strong_threshold = os.environ.get(
        'T1S4R_LSE_REPEAT_FRONTIER_STRONG_THRESHOLD', '12')
    lse_repeat_frontier_penalty_ratio = os.environ.get(
        'T1S4R_LSE_REPEAT_FRONTIER_PENALTY_RATIO', '0.15')
    lse_repeat_frontier_max_fraction = os.environ.get(
        'T1S4R_LSE_REPEAT_FRONTIER_MAX_FRACTION', '0.67')
    lse_repeat_frontier_low_gain_threshold = os.environ.get(
        'T1S4R_LSE_REPEAT_FRONTIER_LOW_GAIN_THRESHOLD', '2.0')
    lse_repeat_frontier_cooldown_sec = os.environ.get(
        'T1S4R_LSE_REPEAT_FRONTIER_COOLDOWN_SEC', '35.0')
    lse_repeat_frontier_max_penalty_ratio = os.environ.get(
        'T1S4R_LSE_REPEAT_FRONTIER_MAX_PENALTY_RATIO', '0.30')
    lse_gain_rank_enforce = os.environ.get('T1S4R_LSE_GAIN_RANK_ENFORCE', 'false')
    lse_gain_rank_gain_weight = os.environ.get('T1S4R_LSE_GAIN_RANK_GAIN_WEIGHT', '0.06')
    lse_gain_rank_gain_cap = os.environ.get('T1S4R_LSE_GAIN_RANK_GAIN_CAP', '20.0')
    lse_gain_rank_bonus_ratio = os.environ.get('T1S4R_LSE_GAIN_RANK_BONUS_RATIO', '0.18')
    lse_gain_rank_low_gain_threshold = os.environ.get(
        'T1S4R_LSE_GAIN_RANK_LOW_GAIN_THRESHOLD', '2.0')
    lse_gain_rank_low_gain_penalty_ratio = os.environ.get(
        'T1S4R_LSE_GAIN_RANK_LOW_GAIN_PENALTY_RATIO', '0.08')
    lse_gain_rank_max_fraction = os.environ.get('T1S4R_LSE_GAIN_RANK_MAX_FRACTION', '0.75')
    source = t1s0.sources()
    trials = []
    for index, (rep, cfg, mode, profile) in enumerate(SEQUENCE):
        snap = dict(source[cfg]['snapshot_18'])
        params = t1s0.s2.params_from_snapshot(snap)
        params.extend(('planner', name, value) for name, value in COMMON.items())
        profile = dict(profile)
        profile['fsm_profile'] = profile_name
        params.extend(('planner', name, value) for name, value in profile.items() if name != 'fsm_profile')
        # Apply the selected FSM profile last.  R1_R6 inherit BASE, so adding
        # this after profile is required; otherwise balanced/sensitive silently
        # degrade to strict values in the actual ROS parameter list.
        params.extend(('planner', name, value) for name, value in fsm_profile.items())
        # Validation/long-run groups are applied last so the final ROS
        # parameter list is exactly the requested treatment, not an inherited
        # R1/R5 profile.  ``shadow`` remains a diagnostic mode and is not a
        # long-run treatment group.
        group_overrides = {
            'baseline': {
                'fsm/sliding_recovery_enabled': 'false',
                'planner_escape/shadow': 'false',
                'planner_escape/enabled': 'false',
                'planner_escape/fusion_enabled': 'false',
            },
            'fsm_only': {
                'fsm/sliding_recovery_enabled': 'true',
                'planner_escape/shadow': 'false',
                'planner_escape/enabled': 'false',
                'planner_escape/fusion_enabled': 'false',
            },
            'fusion_legacy': {
                'fsm/sliding_recovery_enabled': 'true',
                'planner_escape/shadow': 'true',
                'planner_escape/enabled': 'true',
                'planner_escape/fusion_enabled': 'true',
                'planner_escape/max_escape_count': '2',
                'planner_escape/cooldown_sec': '45.0',
                'planner_escape/consecutive_fail_threshold': '5',
                'planner_escape/repeat_fraction_threshold': '0.28',
            },
            'fusion_fresh_overlap': {
                'fsm/sliding_recovery_enabled': 'true',
                'planner_escape/shadow': 'true',
                'planner_escape/enabled': 'true',
                'planner_escape/fusion_enabled': 'true',
                'planner_escape/max_escape_count': '2',
                'planner_escape/cooldown_sec': '45.0',
                'planner_escape/fusion_match_mode': 'fresh_overlap',
                'planner_escape/fusion_match_window_sec': '30.0',
                'planner_escape/require_low_motion': 'true',
            },
            'ctrl': {
                'fsm/sliding_recovery_enabled': 'false',
                'planner_escape/shadow': 'false',
                'planner_escape/enabled': 'false',
                'planner_escape/fusion_enabled': 'false',
                'planner_escape/idle_enabled': 'false',
            },
            'idle22': {
                'fsm/sliding_recovery_enabled': 'true',
                'planner_escape/shadow': 'true',
                'planner_escape/enabled': 'true',
                'planner_escape/fusion_enabled': 'true',
                'planner_escape/max_escape_count': '2',
                'planner_escape/cooldown_sec': '45.0',
                'planner_escape/consecutive_fail_threshold': '5',
                'planner_escape/repeat_fraction_threshold': '0.28',
                'planner_escape/idle_enabled': 'true',
                'planner_escape/idle_window_sec': '30.0',
                'planner_escape/idle_net_threshold': '22',
                'planner_escape/idle_skip_sec': '40.0',
            },
            'idle26': {
                'fsm/sliding_recovery_enabled': 'true',
                'planner_escape/shadow': 'true',
                'planner_escape/enabled': 'true',
                'planner_escape/fusion_enabled': 'true',
                'planner_escape/max_escape_count': '2',
                'planner_escape/cooldown_sec': '45.0',
                'planner_escape/consecutive_fail_threshold': '5',
                'planner_escape/repeat_fraction_threshold': '0.28',
                'planner_escape/idle_enabled': 'true',
                'planner_escape/idle_window_sec': '30.0',
                'planner_escape/idle_net_threshold': '26',
                'planner_escape/idle_skip_sec': '40.0',
            },
            'candidate_direct': {
                'fsm/sliding_recovery_enabled': 'false',
                'planner_escape/shadow': 'true',
                'planner_escape/enabled': 'true',
                'planner_escape/fusion_enabled': 'true',
                'planner_escape/trigger_mode': 'candidate_direct',
                'planner_escape/startup_guard_sec': '40.0',
                'planner_escape/max_escape_count': '2',
                'planner_escape/cooldown_sec': '45.0',
                'planner_escape/cluster_suppress_sec': '60.0',
                'planner_escape/topology_bonus': '0.30',
                'planner_escape/cluster_radius_m': '4.5',
                'planner_escape/consecutive_fail_threshold': '5',
                'planner_escape/repeat_fraction_threshold': '0.28',
            },
            'cluster_fsm': {
                'fsm/sliding_recovery_enabled': 'true',
                'planner_escape/shadow': 'true',
                'planner_escape/enabled': 'true',
                'planner_escape/fusion_enabled': 'true',
                'planner_escape/trigger_mode': 'cluster_fsm',
                'planner_escape/startup_guard_sec': '40.0',
                'planner_escape/idle_enabled': 'true',
                'planner_escape/idle_window_sec': '30.0',
                'planner_escape/idle_net_threshold': '10',
                'planner_escape/idle_skip_sec': '40.0',
                'planner_escape/max_escape_count': '2',
                'planner_escape/cooldown_sec': '45.0',
                'planner_escape/cluster_suppress_sec': '60.0',
                'planner_escape/topology_bonus': '0.30',
                'planner_escape/cluster_radius_m': '4.5',
            },
            'low_speed_escape': {
                'fsm/sliding_recovery_enabled': 'false',
                'planner_escape/shadow': 'true',
                'planner_escape/enabled': 'true',
                'planner_escape/fusion_enabled': 'true',
                'planner_escape/trigger_mode': 'low_speed_escape',
                'planner_escape/startup_guard_sec': '40.0',
                'planner_escape/max_escape_count': lse_max_escape_count,
                'planner_escape/cooldown_sec': lse_cooldown_sec,
                'planner_escape/urgent_cooldown_sec': lse_urgent_cooldown_sec,
                'planner_escape/cluster_suppress_sec': lse_cluster_suppress_sec,
                'planner_escape/topology_bonus': lse_topology_bonus,
                'planner_escape/cluster_radius_m': lse_cluster_radius_m,
                'planner_escape/v2_enabled': lse_v2_enabled,
                'planner_escape/v2_clear_radius_m': lse_v2_clear_radius_m,
                'planner_escape/v2_min_step_m': lse_v2_min_step_m,
                'planner_escape/v2_max_step_m': lse_v2_max_step_m,
                'planner_escape/v2_ttl_sec': lse_v2_ttl_sec,
                'planner_escape/v2_min_clearance_m': lse_v2_min_clearance_m,
                'planner_escape/v2_max_cost': lse_v2_max_cost,
                'planner_escape/v2_trigger_on_planner_fail': lse_v2_trigger_on_planner_fail,
                'planner_escape/v2_target_repeat_threshold': lse_v2_target_repeat_threshold,
                'planner_escape/v2_sticky_center': lse_v2_sticky_center,
                'planner_escape/v2_failed_target_memory': lse_v2_failed_target_memory,
                'planner_escape/v2_failed_target_radius_m': lse_v2_failed_target_radius_m,
                'planner_escape/v2_boundary_guard_enabled': lse_v2_boundary_guard_enabled,
                'planner_escape/v2_boundary_margin_xy_m': lse_v2_boundary_margin_xy_m,
                'planner_escape/v2_postplan_guard_enabled': lse_v2_postplan_guard_enabled,
                'planner_escape/v2_postplan_dt_sec': lse_v2_postplan_dt_sec,
                'planner_escape/v2_progress_guard_enabled': lse_v2_progress_guard_enabled,
                'planner_escape/v2_progress_horizon_sec': lse_v2_progress_horizon_sec,
                'planner_escape/v2_min_progress_xy_m': lse_v2_min_progress_xy_m,
                'trajectory_safety/global_postplan_guard_enabled': global_traj_guard_enabled,
                'trajectory_safety/reject_unknown': global_traj_reject_unknown,
                'trajectory_safety/boundary_margin_xy_m': global_traj_boundary_margin_xy_m,
                'trajectory_safety/extra_clearance_m': global_traj_extra_clearance_m,
                'trajectory_safety/dt_sec': global_traj_dt_sec,
                'sdf_map/obstacles_inflation': obstacles_inflation,
                'planner_escape/fail_window_sec': lse_fail_window_sec,
                'failure_memory/enabled': lse_memory_enabled,
                'failure_memory/enforce': lse_memory_enforce,
                'failure_memory/enforce_low_speed_only': lse_memory_enforce_low_speed_only,
                'failure_memory/hard_prune': lse_memory_hard_prune,
                'failure_memory/local_enforce': lse_memory_local_enforce,
                'failure_memory/frontier_soft_enforce': lse_memory_frontier_soft_enforce,
                'failure_memory/frontier_max_fraction': lse_memory_frontier_max_fraction,
                'failure_memory/frontier_penalty_ratio': lse_memory_frontier_penalty_ratio,
                'failure_memory/region_size_m': lse_memory_region_size_m,
                'failure_memory/cooldown_sec': lse_memory_cooldown_sec,
                'failure_memory/blacklist_threshold': lse_memory_blacklist_threshold,
                'failure_memory/blacklist_sec': lse_memory_blacklist_sec,
                'failure_memory/forget_sec': lse_memory_forget_sec,
                'failure_memory/cost_penalty': lse_memory_cost_penalty,
                'planner_escape/repeat_frontier_soft_enforce': lse_repeat_frontier_soft_enforce,
                'planner_escape/repeat_frontier_threshold': lse_repeat_frontier_threshold,
                'planner_escape/repeat_frontier_strong_threshold': lse_repeat_frontier_strong_threshold,
                'planner_escape/repeat_frontier_penalty_ratio': lse_repeat_frontier_penalty_ratio,
                'planner_escape/repeat_frontier_max_fraction': lse_repeat_frontier_max_fraction,
                'planner_escape/repeat_frontier_low_gain_threshold': lse_repeat_frontier_low_gain_threshold,
                'planner_escape/repeat_frontier_cooldown_sec': lse_repeat_frontier_cooldown_sec,
                'planner_escape/repeat_frontier_max_penalty_ratio': lse_repeat_frontier_max_penalty_ratio,
                'planner_escape/gain_rank_enforce': lse_gain_rank_enforce,
                'planner_escape/gain_rank_gain_weight': lse_gain_rank_gain_weight,
                'planner_escape/gain_rank_gain_cap': lse_gain_rank_gain_cap,
                'planner_escape/gain_rank_bonus_ratio': lse_gain_rank_bonus_ratio,
                'planner_escape/gain_rank_low_gain_threshold': lse_gain_rank_low_gain_threshold,
                'planner_escape/gain_rank_low_gain_penalty_ratio': lse_gain_rank_low_gain_penalty_ratio,
                'planner_escape/gain_rank_max_fraction': lse_gain_rank_max_fraction,
            },
        }
        if not lse_v2_progress_guard_configured:
            for name in (
                    'planner_escape/v2_progress_guard_enabled',
                    'planner_escape/v2_progress_horizon_sec',
                    'planner_escape/v2_min_progress_xy_m'):
                group_overrides['low_speed_escape'].pop(name)
        if not global_traj_guard_configured:
            for name in (
                    'trajectory_safety/global_postplan_guard_enabled',
                    'trajectory_safety/reject_unknown',
                    'trajectory_safety/boundary_margin_xy_m',
                    'trajectory_safety/extra_clearance_m',
                    'trajectory_safety/dt_sec'):
                group_overrides['low_speed_escape'].pop(name)
        if group in group_overrides:
            params.extend(('planner', name, value) for name, value in group_overrides[group].items())
        trials.append({
            'index': index,
            'tag': f't1s4r_{rep}_{cfg}_{mode}',
            'replicate': rep,
            'config_key': cfg,
            'mode': mode,
            'source_s3_tag': source[cfg]['tag'],
            'snapshot_18': snap,
            'params': params,
            'profile': profile,
            'fsm_profile': profile_name,
            'experiment_group': group,
        })
    return trials


def write_manifest(trials, duration, path=MANIFEST):
    payload = {
        'schema_version': 1,
        'stage': 'T1S-4R',
        'purpose': 'integration smoke: telemetry + FSM-2 + shadow + fusion chain',
        'duration_sim_seconds': duration,
        'registration_source': t1s0.REGISTRATION_SOURCE,
        'trial_count': len(trials),
        'coverage_min_fraction': tv.COVERAGE_MIN,
        'stop_after_consecutive_infra_failures': MAX_CONSEC_INFRA_FAIL,
        'required_artifacts': [
            's3f_trial_config.json', 'metrics.json', 'run_validity.json',
            'odom_stagnation.csv', 'online_progress.csv', 'planner_degradation.csv',
            'low_speed_events.csv',
            'target_context.csv',
            'planner_events.json', 'telemetry_bundle_meta.json', 't1s4r_validity_report.json',
            'ros_logs/launcher_logs/racer.log',
        ],
        'fsm_profile': trials[0].get('fsm_profile', 'strict') if trials else 'strict',
        'experiment_group': trials[0].get('experiment_group', 'native') if trials else 'native',
        'trials': [{k: v for k, v in trial.items() if k not in ('params', 'profile')} for trial in trials],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')


def install_sampler_wrapper():
    original = base.master.run_scorer

    def run_scorer_with_samplers(duration, metrics_path, render_dir, extra_args=None):
        result_dir = Path(render_dir)
        progress_path = result_dir / 'online_progress.csv'
        odom_path = result_dir / 'odom_stagnation.csv'
        planner_path = result_dir / 'planner_degradation.csv'
        low_speed_path = result_dir / 'low_speed_events.csv'
        target_context_path = result_dir / 'target_context.csv'
        # Samplers and the action bridge use a wall-clock deadline while the
        # scorer duration is simulation time. Keep them alive across low RTF;
        # the finally block still terminates them as soon as scoring ends.
        sampler_wall_factor = float(os.environ.get('T1S4R_SAMPLER_WALL_FACTOR', '3.0'))
        if not math.isfinite(sampler_wall_factor) or sampler_wall_factor < 1.0:
            raise ValueError('T1S4R_SAMPLER_WALL_FACTOR must be finite and >= 1.0')
        sampler_duration = duration * sampler_wall_factor + 90
        cmds = [
            ['bash', '-lc',
             'source /opt/ros/noetic/setup.bash; '
             f'exec python3 "{t1s0m.SAMPLER}" --out "{progress_path}" --duration {sampler_duration}'],
            ['bash', '-lc',
             'source /opt/ros/noetic/setup.bash; '
             f'exec python3 "{diag.ODOM_SAMPLER}" --out "{odom_path}" --duration {sampler_duration}'],
            ['bash', '-lc',
             'source /opt/ros/noetic/setup.bash; '
             f'exec python3 "{PLANNER_SAMPLER}" --out "{planner_path}" --duration {sampler_duration} '
             f'--window 30 --fail-threshold 5 --repeat-threshold 0.28'],
            ['bash', '-lc',
             'source /opt/ros/noetic/setup.bash; '
             f'exec python3 "{LOW_SPEED_SAMPLER}" --out "{low_speed_path}" --duration {sampler_duration} '
             f'--window 12 --time-persistence 3 --mean-speed 0.5 '
             f'--exclude-s 10 --max-gap 0.5 --experiment-duration {duration}'],
            ['bash', '-lc',
             'source /opt/ros/noetic/setup.bash; '
             f'exec python3 "{TARGET_CONTEXT_SAMPLER}" --out "{target_context_path}" --duration {sampler_duration}'],
        ]
        procs = []
        sampler_names = ('online_progress', 'odom_stagnation', 'planner_degradation',
                         'low_speed_events', 'target_context')
        if os.environ.get('T1S4R_GROUP') == 'low_speed_escape':
            lse_window = os.environ.get('T1S4R_LSE_WINDOW', '12')
            lse_time_persistence = os.environ.get('T1S4R_LSE_TIME_PERSISTENCE', '3')
            lse_mean_speed = os.environ.get('T1S4R_LSE_MEAN_SPEED', '0.5')
            lse_cooldown = os.environ.get('T1S4R_LSE_BRIDGE_COOLDOWN', os.environ.get('T1S4R_LSE_COOLDOWN_SEC', '45'))
            lse_max_actions = os.environ.get('T1S4R_LSE_MAX_ACTIONS', os.environ.get('T1S4R_LSE_MAX_ESCAPE_COUNT', '2'))
            lse_recovery_window = os.environ.get('T1S4R_LSE_RECOVERY_WINDOW', '45')
            lse_recovery_speed = os.environ.get('T1S4R_LSE_RECOVERY_SPEED', '0.8')
            lse_recovery_displacement = os.environ.get('T1S4R_LSE_RECOVERY_DISPLACEMENT', '1.0')
            lse_pending_retrigger = os.environ.get('T1S4R_LSE_PENDING_RETRIGGER', 'false').lower() in ('1', 'true', 'yes')
            lse_retrigger_grace = os.environ.get('T1S4R_LSE_RETRIGGER_GRACE', '0.0')
            lse_retrigger_mean_speed = os.environ.get('T1S4R_LSE_RETRIGGER_MEAN_SPEED', lse_mean_speed)
            lse_pending_urgent_after = os.environ.get('T1S4R_LSE_PENDING_URGENT_AFTER', '0.0')
            lse_pending_min_cooldown = os.environ.get('T1S4R_LSE_PENDING_MIN_COOLDOWN', '30.0')
            lse_stall_watchdog = os.environ.get('T1S4R_LSE_STALL_WATCHDOG', 'false').lower() in ('1', 'true', 'yes')
            lse_stall_window = os.environ.get('T1S4R_LSE_STALL_WINDOW', '4.0')
            lse_stall_mean_speed = os.environ.get('T1S4R_LSE_STALL_MEAN_SPEED', '0.22')
            lse_stall_peak_speed = os.environ.get('T1S4R_LSE_STALL_PEAK_SPEED', '0.35')
            lse_stall_displacement = os.environ.get('T1S4R_LSE_STALL_DISPLACEMENT', '0.8')
            lse_stall_debounce = os.environ.get('T1S4R_LSE_STALL_DEBOUNCE', '20.0')
            action_bridge_path = result_dir / 'action_bridge_events.csv'
            action_bridge_audit = result_dir / 'action_bridge_audit.json'
            retrigger_args = (
                ' --pending-retrigger' if lse_pending_retrigger else ''
            ) + (
                f' --retrigger-grace {lse_retrigger_grace}'
                f' --retrigger-mean-speed {lse_retrigger_mean_speed}'
                f' --pending-urgent-after {lse_pending_urgent_after}'
                f' --pending-min-cooldown {lse_pending_min_cooldown}'
            )
            stall_args = (
                ' --stall-watchdog' if lse_stall_watchdog else ''
            ) + (
                f' --stall-window {lse_stall_window}'
                f' --stall-mean-speed {lse_stall_mean_speed}'
                f' --stall-peak-speed {lse_stall_peak_speed}'
                f' --stall-displacement {lse_stall_displacement}'
                f' --stall-watchdog-debounce {lse_stall_debounce}'
            )
            cmds.append(
                ['bash', '-lc',
                 'source /opt/ros/noetic/setup.bash; '
                 f'exec python3 "{LOW_SPEED_ACTION_BRIDGE}" '
                 f'--out "{action_bridge_path}" '
                 f'--audit-out "{action_bridge_audit}" '
                 f'--duration {sampler_duration} '
                 f'--window {lse_window} --time-persistence {lse_time_persistence} --mean-speed {lse_mean_speed} '
                 f'--exclude-s 10 --max-gap 0.5 --experiment-duration {duration} '
                 f'--cooldown {lse_cooldown} --max-actions {lse_max_actions} --recovery-window {lse_recovery_window} '
                 f'--recovery-speed {lse_recovery_speed} --recovery-displacement {lse_recovery_displacement} '
                 f'--action-mechanism low_speed_escape '
                 f'--escape-topic "/planning/low_speed_escape_1" '
                 f'--bspline-topic "/planning/bspline_1"{retrigger_args}{stall_args}'])
            sampler_names = sampler_names + ('action_bridge',)
        sampler_logs = []
        for name, cmd in zip(sampler_names, cmds):
            log_path = result_dir / f'{name}_sampler.log'
            handle = log_path.open('w')
            proc = subprocess.Popen(cmd, start_new_session=True, env=os.environ.copy(),
                                    stdout=handle, stderr=subprocess.STDOUT)
            proc._t1s4r_log_handle = handle
            procs.append(proc)
            sampler_logs.append((name, proc, handle))
        try:
            return original(duration, metrics_path, render_dir, extra_args)
        finally:
            # Give samplers a bounded flush window before terminating them; a
            # prior immediate SIGTERM caused missing online_progress.csv.
            deadline = time.monotonic() + 8.0
            while time.monotonic() < deadline and any(p.poll() is None for _, p, _ in sampler_logs):
                time.sleep(0.2)
            status = {}
            for proc in procs:
                if proc.poll() is None:
                    try:
                        os.killpg(proc.pid, signal.SIGTERM)
                        proc.wait(timeout=8)
                    except Exception:
                        try:
                            os.killpg(proc.pid, signal.SIGKILL)
                        except Exception:
                            pass
                status_name = next((name for name, p, _ in sampler_logs if p is proc), str(proc.pid))
                status[status_name] = {'pid': proc.pid, 'exit_code': proc.returncode}
            for _, _, handle in sampler_logs:
                handle.close()
            (result_dir / 'sampler_process_status.json').write_text(
                json.dumps({'schema_version': 1, 'samplers': status}, ensure_ascii=False, indent=2) + '\n')

    base.master.run_scorer = run_scorer_with_samplers


def save_metadata(result_dir, trial, attempt, valid, reasons, metrics, report):
    base.save_metadata(result_dir, trial, attempt, valid, reasons, metrics)
    # base.save_metadata uses the global T1S-4R profile, which previously wrote
    # fusion flags into every FSM/shadow trial.  Overwrite the metadata from the
    # actual parameter vector used for this trial.
    config_path = Path(result_dir) / 's3f_trial_config.json'
    if config_path.is_file():
        config = json.loads(config_path.read_text())
        for key in ('detector', 'fsm_profile', 'experiment_group', 'analysis_role'):
            if key in trial:
                config[key] = trial[key]
        actual = {
            name: value for group, name, value in trial.get('params', [])
            if group == 'planner' and (
                name.startswith('failure_memory/') or
                name.startswith('fsm/') or
                name.startswith('planner_escape/'))
        }
        config['failure_memory_params'] = actual
        config['failure_memory_enforce'] = actual.get('failure_memory/enforce') == 'true'
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n')
    validity = json.loads((Path(result_dir) / 'run_validity.json').read_text())
    validity.update({
        'stage': 'T1S-4R',
        'safety_events': report.get('safety_events', {}),
        'safety_hard_fail': report.get('safety_hard_fail', False),
        'telemetry_ok': report.get('telemetry_ok', False),
        'log_audit': report.get('log_audit', {}),
    })
    (Path(result_dir) / 'run_validity.json').write_text(
        json.dumps(validity, ensure_ascii=False, indent=2) + '\n')


def run_main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--duration', type=int, default=t1s0.DEFAULT_DURATION)
    parser.add_argument('--max-retries', type=int, default=base.MAX_RETRIES_DEFAULT)
    parser.add_argument('--only')
    parser.add_argument('--start-at')
    parser.add_argument('--retry-exhausted', action='store_true')
    parser.add_argument('--continue-after-exhausted', action='store_true',
                        help='记录耗尽的 trial 后继续后续 tag；不把安全/算法失败当基础设施失败')
    # Keep the configured absolute path as the default.  Previously the
    # runner reduced it to ``.name`` and silently ignored E2L_STATE_FILE /
    # E2L_MANIFEST_FILE, allowing a new batch to reuse a stale root state.
    parser.add_argument('--state-file', default=str(STATE))
    parser.add_argument('--manifest-file', default=str(MANIFEST))
    args = parser.parse_args()

    os.chdir(HERE)
    state_path = Path(args.state_file)
    manifest_path = Path(args.manifest_file)
    if not state_path.is_absolute():
        state_path = HERE / state_path
    if not manifest_path.is_absolute():
        manifest_path = HERE / manifest_path
    base.ACTIVE_STATE_PATH = state_path
    trials = build_trials()
    dry_planner_xml = os.environ.get('T1S4R_DRY_PLANNER_XML') if args.dry_run else None
    if dry_planner_xml:
        dry_planner_path = Path(dry_planner_xml)
        if not dry_planner_path.is_file():
            raise RuntimeError(f'dry planner XML missing: {dry_planner_path}')
        original_planner_xml = s2.master.PLANNER_XML
        try:
            s2.master.PLANNER_XML = str(dry_planner_path)
            s2.verify_edit_targets(trials)
        finally:
            s2.master.PLANNER_XML = original_planner_xml
    else:
        s2.verify_edit_targets(trials)
    write_manifest(trials, args.duration, manifest_path)
    print(f'T1S-4R smoke ready: {len(trials)} runs, duration={args.duration}s', flush=True)
    if args.dry_run:
        return 0

    state = base.load_state(state_path)
    if state.get('started_at') == 'pending_operator_start':
        state['started_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        base.save_state(state)
    completed = set(state.get('completed', []))
    selected = base.selected_trials(trials, args.only, args.start_at)
    if args.retry_exhausted:
        for trial in selected:
            if trial['tag'] not in completed:
                state.setdefault('attempts', {}).pop(trial['tag'], None)
        state.pop('blocked_at', None)
        state.pop('blocked_reasons', None)
        state['consecutive_infra_failures'] = 0
        base.save_state(state)

    planner_path = Path(base.master.PLANNER_XML)
    exploration_path = Path(base.master.EXPLORATION_XML)
    planner_original = planner_path.read_text()
    exploration_original = exploration_path.read_text()
    consecutive_infra = int(state.get('consecutive_infra_failures', 0))

    try:
        for trial in selected:
            tag = trial['tag']
            if tag in completed:
                print(f'SKIP completed: {tag}', flush=True)
                continue
            if consecutive_infra >= MAX_CONSEC_INFRA_FAIL:
                state['blocked_at'] = tag
                state['blocked_reasons'] = [f'consecutive_infra_failures={consecutive_infra}']
                base.save_state(state)
                print(f'STOP batch: {consecutive_infra} consecutive infrastructure failures', file=sys.stderr)
                return 2

            attempts_used = int(state.setdefault('attempts', {}).get(tag, 0))
            if attempts_used > args.max_retries:
                if tag not in state.setdefault('exhausted', []):
                    state['exhausted'].append(tag)
                base.save_state(state)
                if args.continue_after_exhausted:
                    print(f'CONTINUE: {tag} exhausted retries', file=sys.stderr)
                    continue
                print(f'STOP: {tag} exhausted retries', file=sys.stderr)
                return 2

            reasons = []
            while attempts_used <= args.max_retries:
                attempt = attempts_used + 1
                state['attempts'][tag] = attempt
                base.save_state(state)
                run_index = trial['index'] if attempt == 1 else trial['index'] + 100 * (attempt - 1)
                run_tag = tag if attempt == 1 else f'{tag}_retry{attempt - 1:02d}'
                print(f'\n=== T1S-4R {trial["index"] + 1:02d}/{len(trials)} {tag} attempt {attempt} ===', flush=True)
                try:
                    row = base.master.run_iteration(
                        run_index, trial['params'], args.duration, state['rows'], tag=run_tag, baseline_m=None)
                except Exception as exc:
                    row = {'error': f'{type(exc).__name__}: {exc}', 'result_dir': None}
                finally:
                    planner_path.write_text(planner_original)
                    exploration_path.write_text(exploration_original)

                row.update({
                    's3f_tag': tag,
                    's3f_config_key': trial['config_key'],
                    's3f_mode': trial['mode'],
                    'attempt': attempt,
                    'registration_source': t1s0.REGISTRATION_SOURCE,
                })
                valid, metrics, report = False, {}, {}
                if row.get('result_dir'):
                    s2.save_planner_events(row['result_dir'])
                    s2.archive_logs(row['result_dir'])
                    try:
                        from trajectory_quality_metrics import enrich_result_dir
                        enrich_result_dir(row['result_dir'], backup=True)
                    except Exception as exc:
                        reasons = [f'quality_metrics_error:{type(exc).__name__}:{exc}']
                    valid, reasons, metrics, report = tv.check_t1s4r_validity(row['result_dir'], args.duration)
                    if metrics.get('quality_metrics_schema_version') != 1:
                        valid = False
                        reasons.insert(0, 'quality_metrics_v1_missing')
                    if row.get('error'):
                        valid = False
                        reasons.insert(0, f'runner_error:{row["error"]}')
                    save_metadata(row['result_dir'], trial, attempt, valid, reasons, metrics, report)
                else:
                    reasons = [f'no_result_dir:{row.get("error", "unknown")}']

                row.update({
                    'valid': valid,
                    'validity_reasons': reasons,
                    'invalid_class': None if valid else classify_invalid(row, reasons, report),
                    'terminal_outcome': metrics.get('terminal_outcome'),
                    't1s4r_report': report,
                    'analysis_role': 't1s4r_integration_smoke',
                })
                state['rows'].append(row)
                base.save_state(state)

                if valid:
                    state['completed'].append(tag)
                    completed.add(tag)
                    # A tag can have a prior exhausted/invalid attempt when
                    # the operator resumes with --retry-exhausted.  Once a
                    # later attempt is valid, the state must no longer report
                    # that tag as exhausted; otherwise downstream resume and
                    # batch gates see a contradictory terminal state.
                    state['exhausted'] = [x for x in state.get('exhausted', [])
                                          if x != tag]
                    consecutive_infra = 0
                    state['consecutive_infra_failures'] = 0
                    state.pop('blocked_at', None)
                    state.pop('blocked_reasons', None)
                    base.save_state(state)
                    audit = report.get('log_audit', {})
                    print(f'VALID: {tag}; fsm_second={audit.get("fsm_second_trigger")} '
                          f'shadow={audit.get("shadow_candidates")} armed={audit.get("fusion_armed")} '
                          f'execute={audit.get("fusion_execute")}', flush=True)
                    break

                print('INVALID: ' + '; '.join(reasons), flush=True)
                invalid_class = classify_invalid(row, reasons, report)
                # safety/telemetry/algorithm invalid are valuable observations and
                # must not consume the batch-level infrastructure-failure budget.
                if invalid_class == 'infra':
                    consecutive_infra += 1
                else:
                    consecutive_infra = 0
                state['consecutive_infra_failures'] = consecutive_infra
                base.save_state(state)
                attempts_used = attempt
                if attempts_used <= args.max_retries:
                    time.sleep(2)
            if tag not in completed:
                state['blocked_at'] = tag
                state['blocked_reasons'] = reasons
                base.save_state(state)
                if args.continue_after_exhausted:
                    if tag not in state.setdefault('exhausted', []):
                        state['exhausted'].append(tag)
                    state.pop('blocked_at', None)
                    base.save_state(state)
                    continue
                return 2
    finally:
        planner_path.write_text(planner_original)
        exploration_path.write_text(exploration_original)
        base.master.stop_all()

    if not args.only and len(completed) == len(trials):
        state['finished_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        base.save_state(state)
        print(f'\nT1S-4R smoke complete: {len(trials)}/{len(trials)}', flush=True)
    return 0


def main():
    os.environ['RACER_GT_MAPPER'] = '1'
    install_sampler_wrapper()
    trials = build_trials()
    base.STATE_PATH = STATE
    base.MANIFEST_PATH = MANIFEST
    base.ACTIVE_STATE_PATH = STATE
    base.REGISTRATION_SOURCE = t1s0.REGISTRATION_SOURCE
    base.DEFAULT_DURATION = t1s0.DEFAULT_DURATION
    base.FAILURE_MEMORY_PARAMS = {**COMMON, **R5_R6}
    base.SEQUENCE = tuple((trial['config_key'], trial['mode']) for trial in trials)
    base.build_trials = build_trials
    base.write_manifest = write_manifest
    return run_main()


if __name__ == '__main__':
    raise SystemExit(main())
