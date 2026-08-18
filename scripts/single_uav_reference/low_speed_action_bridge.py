#!/usr/bin/env python3
"""E2-L low-speed action bridge: detector v2 -> debounced event -> bounded replan.

NEW component for the E2-L action phase (plan section 2).  It reuses the exact
detection semantics of ``low_speed_shadow_sampler.LowSpeedSampler`` (imported,
never copied) so bridge triggers are identical to the released shadow detector.
The bridge adds a bounded, fully audited action on the existing FSM replan
interface:

    low_speed detector v2 (left_bracketed_window_v2)
        -> rising low-speed event (3 s real-time persistence)
        -> cooldown / max-count / recovery-window guard
        -> publish /planning/replan
           (traj_server shortens the current traj; the FSM then plans a fresh
            collision-checked b-spline from the current pose - the same path
            the FSM already takes on a normal replan trigger)
        -> post-action motion-recovery tracking
        -> telemetry + outcome audit (events.csv + audit.json)

The bridge deliberately does NOT touch the FSM or enable any legacy
recovery / planner-escape mechanism.  Action is off by default: the runner
only launches this process for action trials, and the replay topic is only
published while this process is running.
"""
import argparse
import json
import math
import signal
import time

import rospy
from std_msgs.msg import Empty, String
from nav_msgs.msg import Odometry

from low_speed_shadow_sampler import LowSpeedSampler


def _dist(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


class LowSpeedActionBridge(LowSpeedSampler):
    """LowSpeedSampler + bounded /planning/replan action + outcome audit."""

    def __init__(self, args):
        super().__init__(args)
        self.replan_pub = rospy.Publisher(args.replan_topic, Empty, queue_size=10)
        self.escape_pub = rospy.Publisher(args.escape_topic, String, queue_size=10)
        self.last_traj_ros = None
        # AnyMsg avoids depending on the (C++) bspline message python binding;
        # we only need "a new trajectory was published", not its payload.
        rospy.Subscriber(args.bspline_topic, rospy.AnyMsg, self._traj_cb, queue_size=10)
        self.args = args
        self.actions = []            # every decision (accepted or rejected)
        self.recovery = []           # accepted-action post-action outcomes
        self.action_count = 0
        self.cooldown_until_ros = None
        self.last_accept_ros = None
        self.last_stall_watchdog_ros = None
        self._pending = []
        self._cooldown_retrigger_pending = None
        self.started_wall = time.monotonic()

    # -- trajectory watch -------------------------------------------------
    def _traj_cb(self, msg):
        stamp = None
        header = getattr(msg, 'header', None)
        if header is not None and getattr(header, 'stamp', None) is not None:
            try:
                stamp = header.stamp.to_sec()
            except Exception:
                stamp = None
        if stamp is None or stamp <= 0:
            stamp = rospy.Time.now().to_sec()
        self.last_traj_ros = stamp

    # -- detection hook ---------------------------------------------------
    def step(self):
        prev_len = len(self.rows)
        prev_id = self.event_id
        super().step()
        if len(self.rows) == prev_len:
            return  # no new odom row was processed
        self._update_recovery()
        if self.event_id != prev_id:
            self._on_rising(self.rows[-1])
        self._maybe_retrigger(self.rows[-1])
        self._maybe_stall_watchdog(self.rows[-1])
        self.rows[-1]['cooldown_until_ros'] = (
            '' if self.cooldown_until_ros is None else round(self.cooldown_until_ros, 3)
        )

    # -- action decision ---------------------------------------------------
    def _on_rising(self, row):
        now = row['ros_time']
        decision = {
            'action_id': self.event_id,
            'event_ros_time': round(now, 3),
            'window_mean_speed': row.get('window_mean_speed'),
            'window_span_s': row.get('window_span_s'),
            'window_max_gap_s': row.get('window_max_gap_s'),
            'window_displacement': row.get('window_displacement'),
            'window_sample_count': row.get('window_sample_count'),
            'warmup_unready': row.get('warmup_unready'),
            'request_ros_time': round(now, 3),
            'action_count_before': self.action_count,
            'cooldown_remaining_s': None,
            'accepted': False,
            'rejection_reason': None,
        }
        reason = None
        if row.get('takeoff_landing_excluded'):
            reason = 'takeoff_landing_excluded'
        elif self.cooldown_until_ros is not None and now < self.cooldown_until_ros:
            decision['cooldown_remaining_s'] = round(self.cooldown_until_ros - now, 3)
            reason = 'in_cooldown'
        elif self.action_count >= self.args.max_actions:
            reason = 'max_actions_reached'
        elif self.args.experiment_duration is not None and \
                now - self.experiment_start_ros_time > self.args.experiment_duration - self.args.exclude_s:
            reason = 'no_recovery_window'
        elif (row.get('window_span_s') is None or row['window_span_s'] < self.args.window - 1e-6 or
              row.get('window_max_gap_s') is None or row['window_max_gap_s'] > self.args.max_gap):
            # belt-and-suspenders: never act on a detector row that fails the
            # semantic gate (should be unreachable because the sampler gates it).
            reason = 'detector_quality'
        decision['accepted'] = reason is None
        decision['rejection_reason'] = reason
        self.actions.append(decision)
        row['_bridge_decision_index'] = len(self.actions) - 1
        if reason is None:
            self._cooldown_retrigger_pending = None
            self._accept(decision, row)
        elif reason == 'in_cooldown' and self.args.pending_retrigger:
            self._cooldown_retrigger_pending = {
                'event_id': self.event_id,
                'created_ros': now,
                'cooldown_until_ros': self.cooldown_until_ros,
                'row': dict(row),
            }

    def _maybe_retrigger(self, row):
        if not self.args.pending_retrigger:
            return
        pending = self._cooldown_retrigger_pending
        if pending is None:
            return
        now = row['ros_time']
        if not row.get('low_speed_active'):
            self._cooldown_retrigger_pending = None
            return
        if self.cooldown_until_ros is not None and \
                now < self.cooldown_until_ros + self.args.retrigger_grace:
            urgent_age_ok = (
                self.args.pending_urgent_after > 0.0 and
                now - float(pending['created_ros']) >= self.args.pending_urgent_after
            )
            urgent_cooldown_ok = (
                self.last_accept_ros is None or
                now - self.last_accept_ros >= self.args.pending_min_cooldown
            )
            if not (urgent_age_ok and urgent_cooldown_ok):
                return
            trigger_kind = 'pending_urgent_retrigger'
            urgent_retrigger = 1
            cooldown_remaining = max(0.0, self.cooldown_until_ros - now)
        else:
            trigger_kind = 'pending_retrigger'
            urgent_retrigger = 0
            cooldown_remaining = 0.0
        if self.last_accept_ros is not None and \
                now - self.last_accept_ros < self.args.pending_min_cooldown:
            return
        if self.action_count >= self.args.max_actions:
            self._cooldown_retrigger_pending = None
            return
        if self.args.experiment_duration is not None and \
                now - self.experiment_start_ros_time > self.args.experiment_duration - self.args.exclude_s:
            self._cooldown_retrigger_pending = None
            return
        if row.get('window_mean_speed') is None or row['window_mean_speed'] > self.args.retrigger_mean_speed:
            return
        decision = {
            'action_id': int(pending['event_id']),
            'event_ros_time': round(float(pending['created_ros']), 3),
            'window_mean_speed': row.get('window_mean_speed'),
            'window_span_s': row.get('window_span_s'),
            'window_max_gap_s': row.get('window_max_gap_s'),
            'window_displacement': row.get('window_displacement'),
            'window_sample_count': row.get('window_sample_count'),
            'warmup_unready': row.get('warmup_unready'),
            'request_ros_time': round(now, 3),
            'action_count_before': self.action_count,
            'cooldown_remaining_s': round(cooldown_remaining, 3),
            'accepted': True,
            'rejection_reason': None,
            'trigger_kind': trigger_kind,
            'urgent_retrigger': urgent_retrigger,
            'pending_created_ros': round(float(pending['created_ros']), 3),
        }
        row['low_speed_retrigger'] = 1
        row['urgent_retrigger'] = urgent_retrigger
        self.actions.append(decision)
        row['_bridge_decision_index'] = len(self.actions) - 1
        self._cooldown_retrigger_pending = None
        self._accept(decision, row)

    def _maybe_stall_watchdog(self, row):
        if not self.args.stall_watchdog:
            return
        now = row['ros_time']
        if row.get('takeoff_landing_excluded'):
            return
        if row.get('low_speed_active') or row.get('low_speed_trigger') or \
                row.get('low_speed_retrigger') or row.get('stall_watchdog_trigger'):
            return
        if self.last_stall_watchdog_ros is not None and \
                now - self.last_stall_watchdog_ros < self.args.stall_watchdog_debounce:
            return
        if self.action_count >= self.args.max_actions:
            return
        if self.args.experiment_duration is not None and \
                now - self.experiment_start_ros_time > self.args.experiment_duration - self.args.exclude_s:
            return
        if self.last_accept_ros is not None and \
                now - self.last_accept_ros < self.args.pending_min_cooldown:
            return
        recent = [r for r in self.rows if now - r['ros_time'] <= self.args.stall_window]
        if len(recent) < 2:
            return
        span = recent[-1]['ros_time'] - recent[0]['ros_time']
        if span < self.args.stall_window - 1e-6:
            return
        max_gap = max(
            recent[i]['ros_time'] - recent[i - 1]['ros_time']
            for i in range(1, len(recent))
        )
        if max_gap > self.args.max_gap:
            return
        mean_speed = sum(float(r['speed']) for r in recent) / len(recent)
        peak_speed = max(float(r['speed']) for r in recent)
        displacement = _dist(
            (recent[0]['x'], recent[0]['y'], recent[0]['z']),
            (recent[-1]['x'], recent[-1]['y'], recent[-1]['z'])
        )
        if mean_speed > self.args.stall_mean_speed:
            return
        if peak_speed > self.args.stall_peak_speed:
            return
        if displacement > self.args.stall_displacement:
            return
        urgent_retrigger = int(
            self.cooldown_until_ros is not None and now < self.cooldown_until_ros
        )
        if urgent_retrigger and self.last_accept_ros is not None and \
                now - self.last_accept_ros < self.args.pending_min_cooldown:
            return
        decision = {
            'action_id': int(self.event_id) + 10000,
            'event_ros_time': round(now, 3),
            'window_mean_speed': row.get('window_mean_speed'),
            'window_span_s': row.get('window_span_s'),
            'window_max_gap_s': row.get('window_max_gap_s'),
            'window_displacement': row.get('window_displacement'),
            'window_sample_count': row.get('window_sample_count'),
            'warmup_unready': row.get('warmup_unready'),
            'request_ros_time': round(now, 3),
            'action_count_before': self.action_count,
            'cooldown_remaining_s': 0.0 if not urgent_retrigger or self.cooldown_until_ros is None
                                    else round(max(0.0, self.cooldown_until_ros - now), 3),
            'accepted': True,
            'rejection_reason': None,
            'trigger_kind': 'stall_watchdog',
            'urgent_retrigger': urgent_retrigger,
            'stall_window_s': round(span, 3),
            'stall_mean_speed': round(mean_speed, 3),
            'stall_peak_speed': round(peak_speed, 3),
            'stall_displacement': round(displacement, 3),
        }
        row['stall_watchdog_trigger'] = 1
        row['urgent_retrigger'] = urgent_retrigger
        self.actions.append(decision)
        row['_bridge_decision_index'] = len(self.actions) - 1
        self._cooldown_retrigger_pending = None
        self.last_stall_watchdog_ros = now
        self._accept(decision, row)

    def _accept(self, decision, row):
        # Multiple actions can be accepted inside one recovery window
        # (for example urgent retrigger after 30s while recovery_window is 45s).
        # Keep earlier records alive instead of overwriting their audit state.
        self._update_recovery()
        self.action_count += 1
        now = row['ros_time']
        if self.args.action_mechanism == 'low_speed_escape':
            msg = String()
            msg.data = json.dumps({
                'action_id': int(decision.get('action_id', self.event_id)),
                'event_ros_time': now,
                'x': row.get('x'),
                'y': row.get('y'),
                'z': row.get('z'),
                'window_mean_speed': row.get('window_mean_speed'),
                'window_displacement': row.get('window_displacement'),
                'urgent_retrigger': int(decision.get('urgent_retrigger', 0)),
            }, sort_keys=True)
            self.escape_pub.publish(msg)
        else:
            self.replan_pub.publish(Empty())
        self.cooldown_until_ros = now + self.args.cooldown
        self.last_accept_ros = now
        self._pending.append({
            'action_id': int(decision.get('action_id', self.event_id)),
            'start_ros': now,
            'deadline_ros': now + self.args.recovery_window,
            'start_pos': (row['x'], row['y'], row['z']),
            'peak_speed': 0.0,
            'max_displacement': 0.0,
            'recovered': False,
            'traj_seen': False,
            'first_fast_ros': None,
        })

    # -- post-action recovery ----------------------------------------------
    def _update_recovery(self):
        if not self._pending:
            return
        now = self.latest['ros_time'] if self.latest else None
        if now is None:
            return
        active = []
        for rec in self._pending:
            if now > rec['deadline_ros']:
                self._finalize_recovery(rec)
                continue
            sp = self.latest['speed']
            pos = (self.latest['x'], self.latest['y'], self.latest['z'])
            disp = _dist(pos, rec['start_pos'])
            if sp > rec['peak_speed']:
                rec['peak_speed'] = sp
            if disp > rec['max_displacement']:
                rec['max_displacement'] = disp
            if (sp >= self.args.recovery_speed and
                    disp >= self.args.recovery_displacement and
                    not rec['recovered']):
                rec['recovered'] = True
                rec['first_fast_ros'] = now
            active.append(rec)
        self._pending = active

    def _finalize_recovery(self, rec):
        if self.last_traj_ros is not None and self.last_traj_ros > rec['start_ros']:
            rec['traj_seen'] = True
        self.recovery.append(rec)

    def _finalize_all_recoveries(self):
        for rec in self._pending:
            self._finalize_recovery(rec)
        self._pending = []

    # -- output -------------------------------------------------------------
    def write(self):
        import csv
        fields = ['wall_elapsed', 'ros_time', 'x', 'y', 'z', 'vx', 'vy', 'vz', 'speed',
                  'window_ready', 'window_span_s', 'window_sample_count',
                  'window_max_gap_s', 'observation_started', 'window_displacement',
                  'window_mean_speed', 'observation_age_s', 'warmup_unready',
                  'low_speed_candidate', 'low_speed_candidate_duration_s',
                  'takeoff_landing_excluded', 'low_speed_time_persistence_s',
                  'speed_state', 'low_speed_trigger', 'low_speed_active', 'low_speed_retrigger',
                  'urgent_retrigger',
                  'stall_watchdog_trigger',
                  'low_speed_event_id',
                  'action_id', 'action_requested', 'action_accepted',
                  'rejection_reason', 'action_count', 'cooldown_until_ros']
        with open(self.args.out, 'w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
            writer.writeheader()
            for row in self.rows:
                out = dict(row)
                out.pop('_bridge_decision_index', None)
                act = self._decision_for_row(row)
                is_rising_row = bool(row.get('low_speed_trigger'))
                is_retrigger_row = bool(row.get('low_speed_retrigger'))
                is_stall_row = bool(row.get('stall_watchdog_trigger'))
                out['low_speed_retrigger'] = int(is_retrigger_row)
                out['urgent_retrigger'] = int(bool(row.get('urgent_retrigger')))
                out['stall_watchdog_trigger'] = int(is_stall_row)
                out['action_id'] = '' if act is None else act.get('action_id', '')
                action_row = is_rising_row or is_retrigger_row or is_stall_row
                out['action_requested'] = 0 if act is None or not action_row else 1
                out['action_accepted'] = '' if act is None or not action_row else int(act['accepted'])
                out['rejection_reason'] = '' if act is None or not action_row else (act['rejection_reason'] or '')
                out['action_count'] = '' if act is None or not action_row else act.get('action_count_before', '')
                out['cooldown_until_ros'] = row.get('cooldown_until_ros', '')
                writer.writerow(out)

        rejected = {}
        for a in self.actions:
            r = a['rejection_reason']
            if r:
                rejected[r] = rejected.get(r, 0) + 1
        recovered = sum(1 for r in self.recovery if r['recovered'])
        audit = {
            'schema_version': 1,
            'bridge': 'low_speed_action_bridge',
            'detector': {
                'id': 'lsp_w12_t3_v0.5_nogate_excl10_bracket_gap0.5_v2',
                'implementation': 'left_bracketed_window_v2',
                'window_s': self.args.window,
                'time_persistence_s': self.args.time_persistence,
                'v_max_mps': self.args.mean_speed,
                'exclude_s': self.args.exclude_s,
                'max_gap_s': self.args.max_gap,
                'experiment_duration_s': self.args.experiment_duration,
            },
            'action_policy': {
                'mechanism': self.args.action_mechanism,
                'replan_topic': self.args.replan_topic,
                'escape_topic': self.args.escape_topic,
                'bspline_topic': self.args.bspline_topic,
                'cooldown_s': self.args.cooldown,
                'pending_retrigger': self.args.pending_retrigger,
                'retrigger_grace_s': self.args.retrigger_grace,
                'retrigger_mean_speed_mps': self.args.retrigger_mean_speed,
                'pending_urgent_after_s': self.args.pending_urgent_after,
                'pending_min_cooldown_s': self.args.pending_min_cooldown,
                'stall_watchdog': self.args.stall_watchdog,
                'stall_window_s': self.args.stall_window,
                'stall_mean_speed_mps': self.args.stall_mean_speed,
                'stall_peak_speed_mps': self.args.stall_peak_speed,
                'stall_displacement_m': self.args.stall_displacement,
                'stall_watchdog_debounce_s': self.args.stall_watchdog_debounce,
                'max_actions': self.args.max_actions,
                'recovery_window_s': self.args.recovery_window,
                'recovery_speed_mps': self.args.recovery_speed,
                'recovery_displacement_m': self.args.recovery_displacement,
            },
            'summary': {
                'detector_events': len(self.actions),
                'accepted_actions': sum(1 for a in self.actions if a['accepted']),
                'accepted_pending_retriggers': sum(1 for a in self.actions
                                                   if a.get('accepted') and
                                                   a.get('trigger_kind') == 'pending_retrigger'),
                'accepted_urgent_retriggers': sum(1 for a in self.actions
                                                  if a.get('accepted') and
                                                  a.get('trigger_kind') == 'pending_urgent_retrigger'),
                'accepted_stall_watchdogs': sum(1 for a in self.actions
                                                if a.get('accepted') and
                                                a.get('trigger_kind') == 'stall_watchdog'),
                'rejected_actions': sum(1 for a in self.actions if not a['accepted']),
                'rejected_by_reason': rejected,
                'accepted_with_traj_seen': sum(1 for r in self.recovery if r['traj_seen']),
                'accepted_recovered_40s': recovered,
                'accepted_total_tracked': len(self.recovery),
            },
            'events': self.actions,
            'recovery': [{k: (round(v, 3) if isinstance(v, float) else v)
                          for k, v in r.items()} for r in self.recovery],
            'process': {
                'started_wall': round(self.started_wall, 3),
                'ended_wall': round(time.monotonic(), 3),
                'row_count': len(self.rows),
            },
        }
        with open(self.args.audit_out, 'w') as handle:
            json.dump(audit, handle, ensure_ascii=False, indent=2)

    def _decision_for_row(self, row):
        idx = row.get('_bridge_decision_index')
        if isinstance(idx, int) and 0 <= idx < len(self.actions):
            return self.actions[idx]
        return self._decision_for_event(row.get('low_speed_event_id'))

    def _decision_for_event(self, event_id):
        for a in reversed(self.actions):
            if str(a['action_id']) == str(event_id):
                return a
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, help='action_bridge_events.csv')
    parser.add_argument('--audit-out', required=True, help='action_bridge_audit.json')
    parser.add_argument('--topic', default='/lidar_slam/odom_1')
    parser.add_argument('--replan-topic', default='/planning/replan')
    parser.add_argument('--bspline-topic', default='/planning/bspline')
    parser.add_argument('--escape-topic', default='/planning/low_speed_escape')
    parser.add_argument('--duration', type=float, default=360.0)
    parser.add_argument('--rate', type=float, default=10.0)
    # detector args -- must match the released shadow sampler exactly.
    parser.add_argument('--window', type=float, default=12.0)
    parser.add_argument('--mean-speed', type=float, default=0.5)
    parser.add_argument('--time-persistence', type=float, default=3.0)
    parser.add_argument('--exclude-s', type=float, default=10.0)
    parser.add_argument('--max-gap', type=float, default=0.5)
    parser.add_argument('--experiment-duration', type=float, default=None)
    # action policy args.
    parser.add_argument('--action-mechanism', default='replan_injection',
                        choices=('replan_injection', 'low_speed_escape'))
    parser.add_argument('--cooldown', type=float, default=40.0)
    parser.add_argument('--pending-retrigger', action='store_true',
                        help='if a low-speed rising edge is rejected by cooldown, fire once when cooldown expires if low speed is still active')
    parser.add_argument('--retrigger-grace', type=float, default=0.0,
                        help='extra seconds after cooldown expiry before a pending retrigger can fire')
    parser.add_argument('--retrigger-mean-speed', type=float, default=None,
                        help='max window mean speed for pending retrigger; defaults to --mean-speed')
    parser.add_argument('--pending-urgent-after', type=float, default=0.0,
                        help='allow a pending cooldown-rejected event to retrigger before full cooldown once low speed has persisted this many seconds')
    parser.add_argument('--pending-min-cooldown', type=float, default=30.0,
                        help='minimum seconds since last accepted action before any pending urgent retrigger can fire')
    parser.add_argument('--stall-watchdog', action='store_true',
                        help='short-window near-stationary watchdog for pre-freeze low-speed events hidden by the long detector window')
    parser.add_argument('--stall-window', type=float, default=4.0,
                        help='short watchdog window in seconds')
    parser.add_argument('--stall-mean-speed', type=float, default=0.22,
                        help='max mean speed in the watchdog window')
    parser.add_argument('--stall-peak-speed', type=float, default=0.35,
                        help='max instantaneous speed in the watchdog window')
    parser.add_argument('--stall-displacement', type=float, default=0.8,
                        help='max displacement in the watchdog window')
    parser.add_argument('--stall-watchdog-debounce', type=float, default=20.0,
                        help='minimum seconds between watchdog-originated actions')
    parser.add_argument('--max-actions', type=int, default=5)
    parser.add_argument('--recovery-window', type=float, default=40.0)
    parser.add_argument('--recovery-speed', type=float, default=0.8)
    parser.add_argument('--recovery-displacement', type=float, default=1.0)
    args = parser.parse_args()
    if args.retrigger_mean_speed is None:
        args.retrigger_mean_speed = args.mean_speed

    rospy.init_node('t1s4_low_speed_action_bridge', anonymous=True)
    bridge = LowSpeedActionBridge(args)

    def stop(_signum, _frame):
        bridge.stop_requested = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    deadline = time.monotonic() + args.duration
    rate = rospy.Rate(args.rate)
    try:
        while not rospy.is_shutdown() and not bridge.stop_requested and time.monotonic() < deadline:
            bridge.step()
            rate.sleep()
    except rospy.exceptions.ROSInterruptException:
        pass
    finally:
        # flush any pending recovery records before writing.
        if bridge._pending:
            bridge._finalize_all_recoveries()
        bridge.write()
        print('action bridge wrote {} rows / {} decisions to {}'.format(
            len(bridge.rows), len(bridge.actions), args.out), flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
