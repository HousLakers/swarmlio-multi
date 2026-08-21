# 2-UAV smoke execution result

- Runroot: `RUN-20260821T083254Z-2uav-smoke`
- Command: `python3 scripts/two_uav_runner.py launch --manifest experiments/manifests/2uav_smoke.yaml`
- Exit code: `2`
- Decision: **`SMOKE_FAIL_ABORT`** —— goal 已发布，uav0 进入执行，但运行期被 collector
  fail-closed abort（`corrupted_telemetry:uav0:freshness`，sim 32.39/120），
  `exit_reason=abort_requested`（非 `duration_complete`）。
- 目标时长：120 sim s；实际推进至 sim 32.39（约 27%）。
- Active lifecycle after exit: absent（5 进程全部 sigterm+sigkill，见
  `execution_result.json` 的 stop 字段；无 ACTIVE 文件）。
- 本 runroot 为最终 append-only 产物；smoke approval package 已消费（receipt
  `3986a46c…json` 落盘）。

## Frozen identity（全部核对通过）

- Multi repo: `41879e8ccea783895965831f75646ac2a6a43ed7`（`main`，dirty tree 由 hash
  manifest 绑定；未 commit）
- Platform repo: `57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`（tracked-clean）
- Single repo: `c01f1f5af40ec25631aa11765a0f21e06834abc4`（tracked-clean）
- Experiment manifest: `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`
- Source hash manifest: `0970f2e4b29aad999753270adb2cd8535d53826b4b0b651bced887e559657596`
  （12/12 OK）
- `two_uav_collector.py`: `efb27ff4335863f86e319a27ce8a06d8ad24ab90b3cf5eccac655d13c2540004`
- Static contract: `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`
- Runner: `60bd1a8aa9455139cc4663b53408cc07b64777319a7b4f83b74417e9ebe4bd50`
- 公共 baseline manifest: `ce595cafba088955b38c4c9bd1d08f9af254dbfa0bf013481372a75e17980944`
- PX4 iris model template: `e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225`
- `mid360.csv`: `aa1fc08b6a4400608dbd6ee832b7ea3a9c3c37197e734f60f58fe5abf762269a`
- Livox plugin binary: `ad117f9290cc1ef091842023d30af0de89bff14724fc78192250f737442b90b6`
- Smoke approval package:
  `3986a46c53dd3c7cfae9dbc03eb388fe80327fc2d2f784b8506a01a8b3988038`（consumed；
  `stage: smoke`、`allowed_actions: [launch]`、`max_uses: 1`；启动前无 receipt、无
  active lifecycle、环境探针 OK）

## 执行阶段

1. **静态/环境门**：`static_preflight.json` 53/53；workspace probe 3/3。
2. **启动前 live 门**：`live_preflight.json` **passed: true**（46/46）——readiness、
   双机 payload、唯一 TF、参数回读、logdir 隔离、**24 s no-goal soak 全部通过**。
3. **goal 发布**：runner 执行 `rostopic pub -1 /move_base_simple/goal …`
   （输出 "publishing and latching message for 3.0 seconds"），进入 120 sim s 监视。
4. **运行期**：sim 12.39 → 32.39 推进（fleet telemetry 11 行）；sim ~28.6-30.1 uav0
   的 traj_server 接受唯一 bspline（id=1）并发出首个 pos_cmd；sim 32.39 collector
   abort → 全局停栈（5 进程 sigterm+sigkill）。
5. **最终**：`execution_result.json`：
   `exit_reason=abort_requested`、`final_safety_passed=false`（"abort.request exists"）、
   uav0/uav1/fleet metrics 均存在。

## 失败链（均有日志证据）

1. **goal 触发仅 uav0 执行**：`[Traj server] accept bspline: id=1 start=28.610
   duration=4.699`、`[Traj server] first pos_cmd: id=1 …`（racer.log）；uav0 开始移动
   （freeze=false、path_length 3.38 m、终点位置 [-1.20, -0.49, 1.57]）。**uav1 未接令**：
   ack/pos_cmd/trajectory 全 0、freeze=true、悬停 ~1.49 m——其 planner 报
   `Astar vehicle start is inside inflated occupancy`（自身位置在膨胀区内）。
2. **uav0 规划随后失败**：sim 32.07-32.18 大量
   `[ERROR] Astar timed out`（iterations 最高 44579，rejects 以 outside/inflated_neighbor
   为主）、`No path to next viewpoint`、`S3F failure_memory_record type=astar_no_path
   failures=4`、`T1S4R planner_fail_window kind=astar_no_path consecutive=4`、`Plan fail`、
   `Replan: cluster covered`——首个 bspline 之后不再有新的可接受轨迹。
3. **trajectory 通道停更 → fail-closed abort**：collector 在首个 PositionCommand 后按
   第 13 节合同把 `trajectory/pos_cmd/ack` 加入连续 freshness 通道；`/planning/bspline_1`
   全 run 仅 1 条消息（trajectory=1），>5 s 无新消息 →
   `abort.request: {"reason": "corrupted_telemetry:uav0:freshness", …}`（sim 32.39）。
4. 8/8 节点存活、TF 正常、无 crash/contact/process death/cross-talk；fleet 指标完整。

## wall/sim 推进量与 RT factor（第 14 节要求）

- fleet telemetry 窗口：sim `12.39 → 32.39`（20.00 sim s），wall `15008.1 → 15067.2`
  （59.0 s），**RT factor ≈ 0.339**；
- 按此 RT，120 sim s 约需 ~354 wall s；runner 1200 s wall watchdog 未触发（abort 先到）；
- `clock.monotonic=true` 全程。

## fleet / 逐机指标

**fleet**：`abort_reasons=[corrupted_telemetry:uav0:freshness]`、
`telemetry_completeness=false`、`tf_parents` 唯一父 `world`×2、8/8 进程存活、
`lost_after_seen=[]`、`fleet_coverage_ratio=0.0166`、
`minimum_inter_uav_distance_m=1.4566`、`map_consistency_jaccard=0.7115`、
`overlap_ratio=0.8905`、`fleet_contact_count=0`、`clock.last_sim_s=32.871`。

| 指标 | uav0 | uav1 |
|---|---|---|
| cloud / odometry | 225 / 225 | 223 / 223 |
| frontier | 1005 | 1014 |
| health / occupancy | 23 / 34 | 23 / 37 |
| pos_cmd / ack | 278 / 278 | 0 / 0 |
| trajectory | **1** | 0 |
| telemetry_complete | false（stale: [trajectory]） | true |
| crash / freeze | false / **false（已移动）** | false / true（未接令） |
| path_length_m | 3.38 | 2.15 |
| coverage voxels / ratio | 4068 / 0.0151 | 3562 / 0.0132 |
| completion | false（未到 120 s） | false |
| contact ground/inter_uav/obstacle | 0/0/0 | 0/0/0 |
| ack_timeout count | 0 | 0 |

## 说明（供 lead/luna 审核）

- 按 sol_approval 第 14 节：低 RT 导致的规划/回调超时按**真实 smoke 失败保留**，不得
  现场调参重试。本轮确属真实失败：uav0 仅执行首个轨迹后规划失败
  （A* timeout / no path），uav1 全程未接令（自身起点在膨胀区内）。
- trajectory 通道与 run 5 frontier 同属"事件驱动发布者 vs 连续 freshness 合同"类别：
  traj_server 只在接受新 bspline 时发布，规划失败后不再发布 → 5 s 门触发。是否调整
  合同或发布行为由 Sol/lead 判定（见 `state/execution_issue.md`）。

## Artifact hashes

- `manifest.yaml`:
  `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`
- `2uav_static.yaml`:
  `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`
- `2uav_approval.yaml`:
  `3986a46c53dd3c7cfae9dbc03eb388fe80327fc2d2f784b8506a01a8b3988038`
- `runtime_environment.json`:
  `1ca164c21ea549bc15d8410605a909f99e0dae745636f83bb7a34ec0cb959fe6`
- `workspace_environment_probe.json`:
  `0407d96611464f335ab30dc8127be7d39ea0e065ca6e55b475d3eff1e89a4577`
- `process_specs.json`:
  `dc38ad100a95e6f95e912ffe69b51d37233d238aab7fdb72309e33571ba1dfab`
- `static_preflight.json`:
  `ea29114e9e4cfd19cf82a42faa561fb47a91efa03fda1479b0af37475443b0a6`
- `live_preflight.json`:
  `52619e3797d88ed339ca1e1ee46e996e536a49136a285a7363a3494f7068813b`
- `execution_result.json`:
  `df00504828b2f9a357768d34972c78897d50e0bc19db09f7d4b43533aa2d8ed7`
- `fleet/abort.request`:
  `e1e6c174f3e1a03b089bec9bd28b244fc5f39c78e32c53028c2a8f0e95ae7c9f`
- `uav0/metrics.json`:
  `65f44a48511091f1cef1a56b8f14671c790c0a8bbbae4376482c4a0b60596669`
- `uav1/metrics.json`:
  `a264eb861e0622712d98f5aa5c73919494c2f52b96d7bf2ac2600d2a80ff8737`
- `fleet/metrics.json`:
  `cd89e9cce7c6c8be5451094e1bb6cb6e490546451773c8eee269a6b7d29925e4`
- `uav0/telemetry.jsonl`:
  `9bebba22b60c024b7657e12ae6f3b126de7218f1d7c6031add77200185212a95`
- `uav1/telemetry.jsonl`:
  `b2f42c8b8abf66ca22f0abb6637d8ba9f05478dbd98c7fb7e9b1e20c68a0779e`
- `fleet/telemetry.jsonl`:
  `65cb325191e4a9698d873646401ec48cf132152e54d73d5292a5cdfc2ef5a6f5`
- `logs/racer.log`:
  `9c6741522523aafa72582c744f007e8c7abdfcb0008c1058a7bf6b796ceba99e`
- `logs/gazebo.log`:
  `4f7abba282b3c7b75fa7e0cb02feee1d80f13cf61e27bdc37e70f2088da38f68`

## Next gate

smoke 失败（abort），package 已消费，runroot 为最终产物。按第 14 节：不得重试/复用
package、不得现场调参、不得修改源码/参数/正式状态。已交回 lead-planning 审核；后续
分析（luna）与是否再次签发 smoke 由 lead/sol 决定。
