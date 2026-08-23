# 2-UAV diagnostic preflight execution result

- Runroot: `RUN-20260821T170558Z-2uav-preflight`
- Command: `python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml`
- Exit code: `2`
- Decision: **`PREFLIGHT_FAILED_READINESS_GATE`** —— readiness 门
  `uav1:mavros_odom: no payload` 120 s 超时。运行中机器负载飙升（启动时 load 1.77，
  运行期间冲高至 29-67），mavros-PX4 心跳丢失（`CON: Lost connection, HEARTBEAT timed
  out` ×3），uav1 odom 未及流动；uav0 链路已通过（sim 1.315 首帧同步）。
- Smoke trigger: not issued（本 package 只批准 diagnostic preflight）
- Active lifecycle after exit: absent —— 主栈（roslaunch/gazebo/sitl/mavros/bridges）
  teardown 正常无残留；另清理了 readiness payload probe 超时泄漏的 **39 个孤儿
  `rostopic echo` 进程**（见下）；无 ACTIVE 文件。
- 本 runroot 为最终 append-only 产物；一次性 approval package 已消费（receipt
  `65c50e12…json` 落盘）

## Frozen identity（全部核对通过）

- Multi repo HEAD: `694a9c30aa9ee8f8f04b4f165866ded55a82aa0c` / `main`（dirty tree 由
  source hash manifest 冻结；未 commit）
- Platform repo: `57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`（tracked-clean）
- Single repo: `c01f1f5af40ec25631aa11765a0f21e06834abc4`（tracked-clean）
- Experiment manifest: `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`
- Static contract: `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`
- Source hash manifest: `a96af28ea6d8c9b032ee5b840c48f309a592e5c85de4bc1874b9eae147c1a49b`
  （12/12 OK；与上轮相同，本轮为 load-retry 重新签发）
- Runner: `67b6a343ea841bbfa54e23d72b6643aa22dde62c8bf47a243f83617ab760d6a2`
- `two_uav_preflight.py`: `35969b9698fcd802b87c6370ebe9c8e14e50154f2439a3093916e26e67dcd345`
- `two_uav_gt_mapper.py`: `7ea6243d1518fc5e1a30f7b33c35378b645871fb201768e0a15f5c57f6d169ae`
- `two_uav_collector.py`: `2343f0b9024878ea9a5c58d6e4cb941cd99b3950fd3a4184be355361d134aeb4`
- 公共 baseline manifest: `ce595cafba088955b38c4c9bd1d08f9af254dbfa0bf013481372a75e17980944`
- PX4 iris model template: `e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225`
- One-time approval package:
  `65c50e1267b1666e444fbe8ff0fb2f1fcb9a4f9c668cadc7ca814132a0e0e6b7`
  （consumed；`stage: preflight`、`allowed_actions: [preflight]`、`max_uses: 1`、
  `issuance_id: preflight-20260822-load-retry-1`；启动前无 receipt、无 active
  lifecycle、环境探针 OK）

## 执行过程（至 readiness 门失败）

1. `static_preflight.json`: **passed: true**，53/53；`workspace_environment_probe.json`:
   3/3 通过。
2. stack 启动正常：gazebo 双 spawn、mavros 双节点 **+PUB 注册 odom**
   （master.log 01:06:01）、gt_mapper ready。
3. 门链：`/clock` 门通过 → uav0 raw_cloud payload 通过 → **uav0 mavros_odom payload
   通过**（uav0 首帧 scan+odom 在 sim 1.315 同步）→ **uav1 mavros_odom 120 s 无
   payload** → 拒绝（collector 未启动）。
4. 停栈：主栈 teardown 正常（无残留 roslaunch/gazebo/px4/mavros/bridges 进程）。

## 失败分析（证据，供 lead 归因）

- **负载飙升**：启动时 `load average: 1.77`（issuance 为 load-retry）；运行期间负载
  冲高至 29.0/67.5/49.1（1/5/15 min）。
- **mavros-PX4 心跳丢失**：gazebo.log
  `CON: Lost connection, HEARTBEAT timed out` ×3（sim 6.78 / 9.39 / 9.39）——
  mavros 虽 +PUB 注册 odom，但心跳中断后 local position 未产出 → uav1 odom 零消息。
- 结论：基础设施/负载类时序失败（load-retry 签发时机正确，但运行窗口内负载再次飙升）；
  非代码回归。

## 新增观察（供 lead 评估，非现场修复）

- **readiness payload probe 泄漏**：runner 的 `topic_payload_seen()` 用
  `subprocess.run(..., timeout=3)` 执行 `bash -lc "…; rostopic echo -n 1 …"`；超时时
  subprocess.run 杀掉 bash，但 bash 已 fork 的 `rostopic echo` 孙进程成为孤儿继续运行
  （负载下 echo 等不到消息会挂住）。本轮泄漏 **39 个**孤儿 `rostopic echo` 进程，已由
  执行器清理。建议 lead 评估是否让 probe 用进程组/超时后递归清理。
- 主栈 teardown（descendant closure）本轮继续有效：无 roslaunch/gzserver/px4/mavros
  残留。

## Artifact hashes

- `manifest.yaml`:
  `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`
- `2uav_static.yaml`:
  `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`
- `2uav_approval.yaml`:
  `65c50e1267b1666e444fbe8ff0fb2f1fcb9a4f9c668cadc7ca814132a0e0e6b7`
- `runtime_environment.json`:
  `12eaee0fa386784e41a7f28cb90a63558195340dae6bf2c96dd3a374b3fa396c`
- `workspace_environment_probe.json`:
  `0407d96611464f335ab30dc8127be7d39ea0e065ca6e55b475d3eff1e89a4577`
- `process_specs.json`:
  `9b0c48bfc5989ab4d169c5d0846ff311235644fc3ac69df979036ea388567f1a`
- `static_preflight.json`:
  `ad1e4b937e1df7d966186ccae2d262e9c04861723c339aafc0bfff319f534091`
- `live_preflight.json`:
  `ec1f8844a6c38312738808e7ef33d0a41cc64fc4ba10787292c1a40f4939898e`

## Next gate

readiness 门超时（负载/基础设施类），package 已消费，runroot 为最终产物。按交接指令
交回 lead-planning 审核；不得执行 smoke、不得复用旧 package、不得修改任何代码/参数。
