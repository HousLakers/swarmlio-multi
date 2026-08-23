# 2-UAV diagnostic preflight execution result

- Runroot: `RUN-20260821T162356Z-2uav-preflight`
- Command: `python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml`
- Exit code: `2`
- Decision: **`PREFLIGHT_FAILED_LIVE_CHECK_CLI_TIMEOUT`** —— readiness 门（含新
  sim-budget frontier 门）全部通过、collector 已启动，但 live 检查阶段
  `rosparam get /exploration_node_1/map_ros/depth_filter_maxdist` **15 s 超时**，
  基础设施/负载类失败。
- Smoke trigger: not issued（本 package 只批准 diagnostic preflight）
- Active lifecycle after exit: absent（已清理 runner 停栈未覆盖的 9 个深层子进程：
  rosmaster、gzserver×2、px4 sitl×2、mavros×2、px4_bridge×2；端口 11311 释放；
  无 ACTIVE 文件）
- 本 runroot 为最终 append-only 产物；一次性 approval package 已消费（receipt
  `186c9159…json` 落盘）

## Frozen identity（全部核对通过）

- Multi repo HEAD: `694a9c30aa9ee8f8f04b4f165866ded55a82aa0c` / `main`（dirty tree 由
  source hash manifest 冻结；未 commit）
- Platform repo: `57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`（tracked-clean）
- Single repo: `c01f1f5af40ec25631aa11765a0f21e06834abc4`（tracked-clean）
- Experiment manifest: `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`
- Static contract: `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`
- Source hash manifest: `48c2db6153211aec6ff85a3f83ad63229dc40b3de6ce1dc4e4ed8e89e9ec7faa`
  （12/12 OK）
- Runner（本轮更新：`node_probe_result` 带重试、`wait_frontier_readiness` sim-budget 门）:
  `67cf495c5c893039e386e746f8393b9ce6a9010bf296244381f8da08364f960e`
- `two_uav_preflight.py`: `afa8b3821b2c8f3e2dfda2f5f65e5d960145ee1bf277d10c220157bde231a567`
- `two_uav_gt_mapper.py`: `7ea6243d1518fc5e1a30f7b33c35378b645871fb201768e0a15f5c57f6d169ae`
- `two_uav_collector.py`: `2343f0b9024878ea9a5c58d6e4cb941cd99b3950fd3a4184be355361d134aeb4`
- 公共 baseline manifest: `ce595cafba088955b38c4c9bd1d08f9af254dbfa0bf013481372a75e17980944`
- PX4 iris model template: `e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225`
- One-time approval package:
  `186c9159e90bb918b674f311d5f45bd4565e7305fb164a652fcf2de41c2dda98`（consumed；
  `stage: preflight`、`allowed_actions: [preflight]`、`max_uses: 1`；启动前无 receipt、
  无 active lifecycle、环境探针 OK、runroot-local ROS 路径正常）

## 执行过程（至 live 检查失败）

1. `static_preflight.json`: **passed: true**，53/53；`workspace_environment_probe.json`:
   3/3 通过。
2. **readiness 门全部通过**（runner 更新生效）：`/clock`、双机 raw/registered
   cloud+odom、frontier（新 sim-budget 门，frontier 实际发布：uav0 400 条）、
   px4_bridge_1/2 节点（新重试探针）。collector 启动。
3. fleet/uav0/uav1 telemetry 各 2 行（sim 12.63 → 14.63），`telemetry_completeness=
   true`、无 abort、TF fresh（uav0 位置升空至 z≈1.09）。
4. **live 检查失败**：`rosparam get /exploration_node_1/map_ros/depth_filter_maxdist`
   超时 15 s（uav0 前两个参数回读 `sdf_map/obstacles_inflation`、
   `sdf_map/max_ray_length` 已通过）→ `live_checks()` 抛异常 → 停栈 → exit 2。
5. 停栈后清理：runner `stop_active` 只覆盖 5 个顶层进程；**9 个深层子进程
   （rosmaster、gzserver×2、px4 sitl×2、mavros×2、px4_bridge×2）未被 killpg 覆盖**，
   由执行器 SIGTERM/SIGKILL 清理，端口 11311 释放。

## 失败分析（证据，供 lead 归因）

- 直接原因：`two_uav_preflight.py` 的 `ros_output()`（15 s 超时、无重试）在负载下
  （RT≈0.33）对 `rosparam get /exploration_node_1/...` 超时——与上轮 `rosnode list`
  探针超时同类的基础设施 flake；runner 已对 readiness 探针加重试，但 live_checks 的
  rosparam 未覆盖。
- 系统健康度：readiness 全过、frontier 正常发布、telemetry complete、TF fresh、
  无 abort——除该 CLI 超时外无其它异常证据。
- 观察项：runner 停栈对 gazebo roslaunch 深层子进程组覆盖不足（连续两轮出现，
  本轮整棵子树存活），建议 lead 评估是否纳入 runner 停栈覆盖范围。

## Artifact hashes

- `manifest.yaml`:
  `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`
- `2uav_static.yaml`:
  `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`
- `2uav_approval.yaml`:
  `186c9159e90bb918b674f311d5f45bd4565e7305fb164a652fcf2de41c2dda98`
- `runtime_environment.json`:
  见 runroot（runroot-local ROS 路径记录）
- `workspace_environment_probe.json`:
  `0407d96611464f335ab30dc8127be7d39ea0e065ca6e55b475d3eff1e89a4577`
- `static_preflight.json`:
  53/53（hash 见 runroot）
- `live_preflight.json`:
  3 项（final.metrics/final.safety timeout、preflight.runtime rosparam 超时）
- `stop_result.json`:
  5 顶层进程 sigterm+sigkill

## Next gate

live 检查 CLI 超时（基础设施/负载类），package 已消费，runroot 为最终产物。按交接
指令交回 lead-planning 审核；不得执行 smoke、不得同包重试、不得修改任何代码/参数。
