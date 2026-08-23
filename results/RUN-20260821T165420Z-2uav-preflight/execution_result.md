# 2-UAV diagnostic preflight execution result

- Runroot: `RUN-20260821T165420Z-2uav-preflight`
- Command: `python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml`
- Exit code: `2`
- Decision: **`PREFLIGHT_FAILED_READINESS_GATE`** —— readiness 门
  `uav0:mavros_odom: no payload` 120 s 超时（mavros 已注册 odom 发布者但 0 消息；
  根因上下文为机器极端过载 load avg 66.9 → sim RT≈0.008 → PX4 心跳未及建立）。
- Smoke trigger: not issued（本 package 只批准 diagnostic preflight）
- Active lifecycle after exit: absent —— **runner 新 teardown（descendant closure）生效，
  无任何残留进程**（gazebo.log 显示 master/gazebo/sitl/mavros 完整级联清理）；
  无 ACTIVE 文件。
- 本 runroot 为最终 append-only 产物；一次性 approval package 已消费（receipt
  `93172bf0…json` 落盘）。

## Frozen identity（全部核对通过）

- Multi repo HEAD: `694a9c30aa9ee8f8f04b4f165866ded55a82aa0c` / `main`（dirty tree 由
  source hash manifest 冻结；未 commit）
- Platform repo: `57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`（tracked-clean）
- Single repo: `c01f1f5af40ec25631aa11765a0f21e06834abc4`（tracked-clean）
- Experiment manifest: `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`
- Static contract: `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`
- Source hash manifest: `a96af28ea6d8c9b032ee5b840c48f309a592e5c85de4bc1874b9eae147c1a49b`
  （12/12 OK）
- `two_uav_preflight.py`（本轮新增 `readonly_cli_retry()`）:
  `35969b9698fcd802b87c6370ebe9c8e14e50154f2439a3093916e26e67dcd345`
- Runner（本轮新增 `teardown_targets()`/`descendant_closure()` 停栈覆盖）:
  `67b6a343ea841bbfa54e23d72b6643aa22dde62c8bf47a243f83617ab760d6a2`
- `two_uav_gt_mapper.py`: `7ea6243d1518fc5e1a30f7b33c35378b645871fb201768e0a15f5c57f6d169ae`
- `two_uav_collector.py`: `2343f0b9024878ea9a5c58d6e4cb941cd99b3950fd3a4184be355361d134aeb4`
- 公共 baseline manifest: `ce595cafba088955b38c4c9bd1d08f9af254dbfa0bf013481372a75e17980944`
- PX4 iris model template: `e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225`
- One-time approval package:
  `93172bf09bc5bdbb6001e04d0cdbe3ba4fa2135e4fd88ef944053fc61ae2f94f`（consumed；
  `stage: preflight`、`allowed_actions: [preflight]`、`max_uses: 1`；启动前无 receipt、
  无 active lifecycle、环境探针 OK、runroot-local ROS identity 正常）

## 执行过程（至 readiness 门失败）

1. `static_preflight.json`: **passed: true**，53/53；`workspace_environment_probe.json`:
   3/3 通过。
2. stack 启动：gazebo（双 spawn OK）、gt_mapper（ready）、mavros 节点启动并
   **+PUB 注册 `/uav0|/uav1/mavros/local_position/odom`**（master.log 00:54:23）；
   gt_mapper 与 readiness probe 订阅 odom。
3. 门链：`/clock` 门通过 → gt_mapper 门：uav0 raw_cloud payload 出现 → **uav0
   mavros_odom 120 s 无 payload** → 拒绝（collector 未启动）。
4. 停栈：runner 新 teardown（descendant closure）清理全部进程——**无残留**（对比上两轮
   需人工清理；本轮修复生效）。

## 失败分析（证据，供 lead 归因）

- **mavros odom topic 注册但 0 消息**：master.log 有 `+PUB [/uav0/mavros/local_position/odom]
  /uav0/mavros` 与 `+SUB /two_uav_gt_mapper`；但 gazebo.log **无 "CON: Got HEARTBEAT"**
  ——mavros 未与 PX4 建立心跳，local position 未产出 → odom 零消息。
- **机器极端过载**：失败时 `load average: 66.91`；sim 推进极慢（gazebo.log 末段 sim 仅
  ~0.70，gt_mapper 首帧 scan 在 154 wall s 后于 sim 1.168 才出现 → **RT≈0.008**，
  远低于常态 0.33）。PX4 侧另有 `WARN [logger] Too many subscriptions, failed to add:
  vehicle_mocap_odometry` ×2（订阅资源压力）。
- 结论：基础设施/负载类时序失败（sim 近乎停滞使 mavros 心跳/odom 无法在 120 s 墙钟
  窗口内到达），非代码回归；同门在历史轮次（RT≈0.33）通过。

## 证据交付说明

- **CLI retry attempts**：本轮失败于 readiness 门（live_checks 之前），
  `readonly_cli_retry()` 未被执行，runroot 无 CLI retry 记录文件（预期）。
- **runner teardown 证据**：teardown 实际执行（descendant closure 生效、进程全部清理），
  但本失败路径（start_stack 异常，无 ACTIVE）未写 `stop_result.json`；以"无残留进程 +
  gazebo.log 级联清理"作为 teardown 证据。若需持久化 teardown 快照，建议 lead 评估在
  start_stack 异常路径同样落盘。

## Artifact hashes

- `manifest.yaml`:
  `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`
- `2uav_static.yaml`:
  `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`
- `2uav_approval.yaml`:
  `93172bf09bc5bdbb6001e04d0cdbe3ba4fa2135e4fd88ef944053fc61ae2f94f`
- `runtime_environment.json`:
  `9011395b7cba7dc75edb06e9d0ead0e55871e2c4288f229031c88370df787776`
- `workspace_environment_probe.json`:
  `0407d96611464f335ab30dc8127be7d39ea0e065ca6e55b475d3eff1e89a4577`
- `process_specs.json`:
  `75fbcf96910a4a9bc6c570e2ba0b09e66154912a957ca8a6ba2987350a28057f`
- `static_preflight.json`:
  `ad1e4b937e1df7d966186ccae2d262e9c04861723c339aafc0bfff319f534091`
- `live_preflight.json`:
  `6ddfd43cdec8891f4191db60ca03e762bffee1c97aef718832388b198c5e39e0`
- `logs/gazebo.log`:
  `d0fcea0b7369fb2a81138cbededcdcd77b83e0ceb84ed75aad73f9f603c8d172`
- `logs/gt_mapper.log`:
  `f4798e473b6323dabef764c889d627242230d446429450e387224e194a0a58c9`

## Next gate

readiness 门超时（负载/基础设施类），package 已消费，runroot 为最终产物。按交接指令
交回 lead-planning 审核；不得执行 smoke、不得同包重试、不得修改任何代码/参数。
