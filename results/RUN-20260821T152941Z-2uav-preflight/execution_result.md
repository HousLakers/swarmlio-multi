# 2-UAV diagnostic preflight execution result

- Runroot: `RUN-20260821T152941Z-2uav-preflight`
- Command: `python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml`
- Exit code: `2`
- Decision: **`PREFLIGHT_FAILED_READINESS_GATE`** —— readiness 门
  `uav0:frontier: missing nodes: /px4_bridge_1, /px4_bridge_2` 在 180 s 超时后拒绝，
  collector 未启动；无 abort.request、无 metrics（基础设施门失败，预期）。
- Smoke trigger: not issued（本 package 只批准 diagnostic preflight）
- Active lifecycle after exit: absent（5 顶层进程 sigterm+sigkill；另清理了残留的
  rosmaster pid 72634，端口 11311 已释放；无 ACTIVE 文件）
- 本 runroot 为最终 append-only 产物；一次性 approval package 已消费（receipt
  `6280f483…json` 落盘）

## Frozen identity（全部核对通过）

- Multi repo HEAD: `694a9c30aa9ee8f8f04b4f165866ded55a82aa0c` / `main`（dirty tree 由
  source hash manifest 冻结；未 commit）
- Platform repo: `57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`（tracked-clean）
- Single repo: `c01f1f5af40ec25631aa11765a0f21e06834abc4`（tracked-clean）
- Experiment manifest: `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`
- Static contract: `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`
- Source hash manifest: `cb03164c3a3f1f44ad33c62790f7eb1b57dfc7bc5d997b1f9aafca228e00cfc5`
  （12/12 OK）
- `two_uav_gt_mapper.py`（本轮新增 inflation-neighborhood/hover 诊断）:
  `7ea6243d1518fc5e1a30f7b33c35378b645871fb201768e0a15f5c57f6d169ae`
- `two_uav_preflight.py`: `afa8b3821b2c8f3e2dfda2f5f65e5d960145ee1bf277d10c220157bde231a567`
- `two_uav_collector.py`: `2343f0b9024878ea9a5c58d6e4cb941cd99b3950fd3a4184be355361d134aeb4`
- Runner: `9e3141efafe8a6f618075d8fe6281b9a41e12f5542cad6d7def25fc377150621`
- 公共 baseline manifest: `ce595cafba088955b38c4c9bd1d08f9af254dbfa0bf013481372a75e17980944`
- PX4 iris model template: `e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225`
- One-time approval package:
  `6280f48317acda77b6c2659b12b397b186f85a8fd6ed23be93dab61c7e7ac5c1`（consumed；
  `stage: preflight`、`allowed_actions: [preflight]`、`max_uses: 1`；启动前无 receipt、
  无 active lifecycle、环境探针 OK、runroot-local ROS 路径经 runtime_environment.json
  记录）

## 执行过程（至 readiness 门失败）

1. `static_preflight.json`: **passed: true**，53/53；`workspace_environment_probe.json`:
   3/3 通过。
2. stack 启动成功：gazebo（`Spawn status: Successfully spawned entity` ×2）、gt_mapper
   （ready）、bridges（px4_bridge_1/2 启动、`[Bridge 1/2] 心跳已接通`、预热悬停设定点；
   roslaunch 无 "process has died"）、racer（exploration/traj servers 启动）。
3. 门链：gazebo `/clock` 门通过 → gt_mapper payload 门通过 → **bridges 节点门通过**
   （60 s 内检测到 /px4_bridge_1、/px4_bridge_2）→ **racer frontier 门 180 s 超时失败**：
   `readiness timeout: uav0:frontier: missing nodes: /px4_bridge_1, /px4_bridge_2`。
4. 失败后 runner 停栈；退出码 2。残留 rosmaster（pid 72634，gazebo roslaunch auto-start
   子进程，未被 killpg 覆盖）已由执行器清理。

## 失败分析（证据，供 lead 归因）

1. **探索 FSM 未越过 INIT**：`logs/ros/…/exploration_node_1-1-stdout.log` 仅 18 行，
   末行 `[FSM]: Drone 1 state: INIT`（sim 6.707）；rosout 持续
   `[FSM]: … wait for init`、初始 `no odom`（sim 6.7 后 odom 到达，T1S2C eval
   mean_speed>0）。`/planning_vis/frontier_1` 有 `+PUB /exploration_node_1` 注册
   （master.log 23:30:14）但 **0 条 frontier 消息发布** → frontier payload 门不可能
   满足。同二进制在 RUN-…082048Z / 091542Z / 095346Z 均通过该门——本轮为
   RACER init 时序/负载相关的轮次波动。
2. **bridges 节点"缺失"报告**：bridges 进程全程存活（自身日志心跳正常、roslaunch 无
   child died），且 bridges 节点门（同一 `rosnode list` 探针、60 s）先通过；racer 门
   最终采样 `rosnode list`（3 s 超时，超时返回空集）报两节点缺失——疑似负载
   （RT≈0.33）下探针超时的基础设施 flake，或与 FSM 未推进的复合阻塞。判定归 lead。
3. 无 collector/无 metrics/无 abort 属预期（gate 在 collector 启动前失败）。

## Artifact hashes

- `manifest.yaml`:
  `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`
- `2uav_static.yaml`:
  `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`
- `2uav_approval.yaml`:
  `6280f48317acda77b6c2659b12b397b186f85a8fd6ed23be93dab61c7e7ac5c1`
- `runtime_environment.json`:
  `4352406ec6b6165f13feefd45a0c3f4f0b86e8bce144a15633d79a7d27491087`
- `workspace_environment_probe.json`:
  `0407d96611464f335ab30dc8127be7d39ea0e065ca6e55b475d3eff1e89a4577`
- `process_specs.json`:
  `aaaf9da8c95c12984ee0a0b7f470ee253c608b81d0e3c931ebaecb9ebb721836`
- `static_preflight.json`:
  `162e5f328a61332ccadbac4c6b8e84cefa8dada0f1931fd48746318f89933137`
- `live_preflight.json`:
  `b7f07b708a6b0bffb260b3e5c1484dd233e89d0e65cf0b2ced9a83064b63c9ea`
- `logs/racer.log`:
  `ff0db57cbd6427112ec4d8d46a8773c961757b946752a312e61a1dbff1e955ff`
- `logs/bridges.log`:
  `698bf15ec92bf3a1df392020b4be16fbeb4f93328464abd5f94338e27cc01fb7`
- `logs/gt_mapper.log`:
  `4badf6d744c7a03fdf32eb62bb31925c0c8bd5d835e0b2426ed5ea137f6bdd06`
- `logs/gazebo.log`:
  `3cd3d75585d69050b4552930d5bd0f194cdc4197e7b9c24d36502adf919af53f`

## Next gate

readiness 门失败（基础设施/时序类），package 已消费，runroot 为最终产物。按交接指令
交回 lead-planning 审核；不得执行 smoke、不得同包重试、不得修改任何代码/参数。
