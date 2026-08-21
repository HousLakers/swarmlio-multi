# 2-UAV preflight execution result

- Runroot: `RUN-20260820T101702Z-2uav-preflight`
- Command: `python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml`
- Exit code: `2`
- Decision: `PREFLIGHT_FAILED_INFRASTRUCTURE_BEFORE_ROS_CLOCK`
- Smoke trigger: not issued
- Active lifecycle after exit: absent

## Frozen identity

- Multi commit: `41879e8ccea783895965831f75646ac2a6a43ed7` (`main`, dirty tree bound by full hash manifest)
- Platform commit: `57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`
- Source hash manifest: `9dbc2b5ac181f86c786ff7b5d549daf101902abdf911440a400cb53092d209af`
- Experiment manifest: `e366f943180cb1471742ab2a84e685d75e64442fd00c8bf75e14a00ee618a0f2`
- Public baseline manifest: `48d00fca6032c76f59ca26134ff39dba2d555a552c2d73f81e3ca51b4583dc44`
- 50x50 world: `28a306b646297011b564c5ce94ac97634281a5e9a34e337956c5f4a9227c320e`
- One-time approval package: `57a76ff0e3d1829684cac38b8a725e0d9b36df006be2f5e37cbd58fafd65b60f` (consumed)

## Evidence

- Static preflight completed before process launch and passed all 53 checks.
- Gazebo/roslaunch then failed before `/clock` appeared.
- `logs/gazebo.log` records both an unwritable `~/.ros/log` directory and
  `PermissionError: [Errno 1] Operation not permitted` while `netifaces.interfaces()`
  enumerated local interfaces inside the execution sandbox.
- `live_preflight.json` therefore reports `/clock did not appear`, final metrics timeout,
  and `passed: false`.
- No UAV0, UAV1, or fleet telemetry/metrics files were produced because the collector and
  remaining stack never started.
- No `abort.request` was produced; failure occurred before runtime safety evidence existed.
- Runner cleaned the attempted lifecycle; no active lifecycle file or relevant ROS/Gazebo
  process remained after exit.

## Artifact hashes

- `static_preflight.json`: `5f8db7577e7350b65991835ace49da11ae134a01a2d20c90c2be82c5c6b7e205`
- `live_preflight.json`: `660bbb397c8a7361fc13ff6016f8dc81b16b0d9a576b6efa68ef66436d1b1e50`
- `logs/gazebo.log`: `1d476ac8209528283b1667075a7e2373dadd52e432fb01055f7e42978d71465e`

## Next gate

This run does not authorize smoke and cannot be retried with the consumed approval package.
A Lead/Sol review must explicitly authorize a new one-time preflight package. Any retry must
run with permissions that allow ROS network-interface discovery and ROS log creation, while
preserving the same manifest and source hashes or triggering a fresh hash audit.
