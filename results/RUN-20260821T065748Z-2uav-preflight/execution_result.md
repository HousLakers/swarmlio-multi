# 2-UAV preflight execution result

- Runroot: `RUN-20260821T065748Z-2uav-preflight`
- Command: `python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml`
- Exit code: `2`
- Decision: `PREFLIGHT_FAILED_READINESS_GATE_NO_RAW_SCAN`（readiness 门
  `uav0:raw_cloud: no payload` 在 stack 启动后、collector 启动前拒绝；根因在 lidar
  仿真插件数据链路，非 runner）
- Smoke trigger: not issued（本 package 只批准 preflight）
- Active lifecycle after exit: absent（无残留 ROS/Gazebo 进程，无
  `/tmp/swarmlio_multi_2uav_active.json`）
- 本 runroot 为最终 append-only 产物；一次性 approval package 已消费（receipt
  `0944b9c0…json` 落盘）

## Frozen identity

- Multi repo: `41879e8ccea783895965831f75646ac2a6a43ed7`（`main`，dirty tree 由完整
  hash manifest 绑定；未 commit）
- Platform repo: `57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`（tracked-clean）
- Single repo: `c01f1f5af40ec25631aa11765a0f21e06834abc4`（tracked-clean）
- Source hash manifest: `f7939703b6fe232aeea7b7343e6538ae5baa2b32ad35d4bd4305fe5ce8f50c70`
  （12/12 OK）
- Experiment manifest: `e366f943180cb1471742ab2a84e685d75e64442fd00c8bf75e14a00ee618a0f2`
- Runner: `60bd1a8aa9455139cc4663b53408cc07b64777319a7b4f83b74417e9ebe4bd50`
- Public baseline manifest: `48d00fca6032c76f59ca26134ff39dba2d555a552c2d73f81e3ca51b4583dc44`
- 50x50 world: `28a306b646297011b564c5ce94ac97634281a5e9a34e337956c5f4a9227c320e`
- One-time approval package:
  `0944b9c08b0646efaaf82494cdca38c0263efa7f6dbc6f4a42ad0f05dd2ef79b`（consumed）

## Pre-execution gates（启动前核对，全部通过）

- 四项 SHA-256 与 sol_approval 第 10 节一致：manifest `e366f943…`、source hash
  manifest `f7939703…`、runner `60bd1a8a…`、approval package `0944b9c0…`。
- package 字段：`stage: preflight`、`approved: true`、`allowed_actions: [preflight]`、
  `issued_by: sol`、`max_uses: 1`；字段与实际文件匹配。
- 无 `0944b9c0…` 的消费 receipt（仅旧 `3bf111db…`、`57a76ff0…`、`8b3b7530…` 存在）；
  无 active lifecycle；冻结仓库 commit 未变。
- 环境探针：`netifaces.interfaces()` OK（5 接口）、localhost TCP OK、`/tmp` 可写。
- `static_preflight.json`: **passed: true**，53/53 项。
- `workspace_environment_probe.json`: **三项全部通过**（returncode 0）：
  swarm_lio → `/home/houslakers/swarm_ws/src/Swarm-LIO2/swarm_lio`；
  exploration_manager → racer_ws；quadrotor_msgs import OK。（runner 的 probe prefix
  修复生效，与 process_specs 共享同一 `ros_runtime_prefix`。）

## Stack 启动（全部成功，直至 raw_scan 门）

- gazebo 启动，`/clock` 门通过（单一发布者、sim 时间推进）。
- 两架 PX4 SITL 启动，mavros 连接成功：`CON: Got HEARTBEAT, connected. FCU: PX4
  Autopilot`、IMU/姿态正常、mission 在 sim 16.7 s 收到。
- 两架 vehicle_spawn 完成：`Spawn status: SpawnModel: Successfully spawned entity`。
- master.log：`+PUB [/uav0/livox/scan] /gazebo`、`+PUB [/uav1/livox/scan] /gazebo`
  —— gazebo 注册了 raw_cloud 发布者；订阅者为 `/two_uav_gt_mapper` 与 readiness
  probe（`rostopic_…`）。

## Failure（readiness 门，fail-closed 按设计）

- `live_preflight.json`：
  - `preflight.runtime`: `readiness timeout: uav0:raw_cloud: no payload`；
  - `final.metrics` / `final.safety`: timeout（collector 未启动，无 metrics——基础设施门
    失败，预期，不补造）。
- 等待 120 s 内 `/uav0/livox/scan` 无任何消息 → gt_mapper 的 raw_cloud 门拒绝，runner
  stop 已启动进程并退出 2。无 abort.request、无 telemetry。

## Root cause（lidar 仿真插件数据链路，证据充分）

- `logs/gazebo.log` 中 **`cannot convert str:` 异常出现 2 次**（uav0 与 uav1 各一次），
  均紧跟在 `load csv file name:…/livox_laser_simulation/scan_mode/mid360.csv` 之后，
  并伴随 `data size:800000`；另见 4 次
  `ERROR [simulator_mavlink] poll timeout 0, 25`（PX4 SITL 侧）。
- 解释：spawn 的 `iris` 模型（`iris.sdf.last_generated`）含 `laser_livox` 传感器，插件
  `liblivox_laser_simulation.so` 加载成功并注册 `/uav0/livox/scan`、`/uav1/livox/scan`
  发布者，但 **mid360.csv 扫描模式解析抛出 `cannot convert str:`（boost::
  bad_lexical_cast 风格）**，扫描生成/发布链路断裂 → 0 消息。
- 传感器块无 `<always_on>true</always_on>`（仅 `update_rate=10`），但存在订阅者，
  该因素不构成主因；主因为插件 csv 解析异常。
- 归因范围（供 Sol/terra 判断）：`liblivox_laser_simulation` 插件版本与 gazebo/boost
  兼容性、mid360.csv 解析、或 iris 模型/环境 baseline 配置；不在 multi 仓库 hash 冻结
  文件内，但 `launch/2uav_px4_sitl.launch` 的 `vehicle=iris` 决定了该模型。

## Progress vs 前两轮

- 第 1 轮（RUN-…060734Z）：旧 runner 无 payload 门，失败深至 collector soak abort。
- 第 2 轮（RUN-…064604Z）：workspace probe 门因 source 顺序缺陷误报（runner bug）。
- 第 3 轮（本轮）：runner/env 门全部通过，stack 完整启动，首次在**最早期 payload 门**
  （uav0:raw_cloud）以明确证据定位到 lidar 插件数据链路缺陷。fail-closed readiness
  门按设计工作。

## Artifact hashes

- `manifest.yaml`:
  `e366f943180cb1471742ab2a84e685d75e64442fd00c8bf75e14a00ee618a0f2`
- `2uav_static.yaml`:
  `fa3be02954ea86280c19c8b41c1ca194e7d565351857051e9c0f8536e0d7e8d6`
- `2uav_approval.yaml`:
  `0944b9c08b0646efaaf82494cdca38c0263efa7f6dbc6f4a42ad0f05dd2ef79b`
- `runtime_environment.json`:
  `d6ffa0bd08720b231eb53c039b62563319280ee335789eaac683fac07f46c02f`
- `workspace_environment_probe.json`:
  `0407d96611464f335ab30dc8127be7d39ea0e065ca6e55b475d3eff1e89a4577`
- `process_specs.json`:
  `ff3b3736042f8b4667aba18514bec828d25972ab77c3a0917cc068760783fc96`
- `static_preflight.json`:
  `ae8fe807690baf470ffb677d8b77364973482415f7e8944c30736ffcfb4cbdf1`
- `live_preflight.json`:
  `c47e29c623b86a9bae0e39303cab663dedf7822f801e221099805e06421ca6cf`
- `logs/gazebo.log`:
  `315b8f1a84cc39ed3492f3ea7f7e4a41d92e551562d59fd4de103d358a7b75da`

## Next gate

package 已消费，runroot 为最终产物。按 sol_approval 第 10 节：不得复用 package、不得
launch/smoke、不得修改源码/参数/workspace/正式状态。lidar 插件数据链路缺陷已移交
Sol/terra 复审（`state/execution_issue.md`）；修复后需 Sol 重新签发一次性 preflight
package。
