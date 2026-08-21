# Luna review: RUN-20260821T083254Z-2uav-smoke

状态：本轮 runroot 证据完整，但实验失败；不得把本报告解释为通过或批准重试。

## 1. 不可变身份与运行结论

- runroot：`results/RUN-20260821T083254Z-2uav-smoke/`
- manifest：`experiments/manifests/2uav_smoke.yaml`，runroot manifest SHA-256
  `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`。
- multi source hash manifest：`0970f2e4b29aad999753270adb2cd8535d53826b4b0b651bced887e559657596`，执行记录为
  12/12 OK。
- 公共环境 baseline：`racer_outdoor_50x50_v1`，manifest SHA-256
  `ce595cafba088955b38c4c9bd1d08f9af254dbfa0bf013481372a75e17980944`。
- platform commit：`57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`；single commit：
  `c01f1f5af40ec25631aa11765a0f21e06834abc4`。
- smoke package `3986a46c53dd3c7cfae9dbc03eb388fe80327fc2d2f784b8506a01a8b3988038` 已消费，
  不得复用。
- `execution_result.json`：`exit_reason=abort_requested`、exit code 2、
  `final_safety_passed=false`；五组进程均执行 `sigterm+sigkill`，无 ACTIVE 生命周期。

证据：`execution_result.json`、`execution_result.md`、`manifest.yaml`、`runtime_environment.json`、
`workspace_environment_probe.json`。

## 2. 时间线（观察）

| 事件 | sim 时间 | wall 时间/证据 |
|---|---:|---|
| 启动前静态/环境门 | — | `static_preflight.json` 53/53，workspace 3/3 |
| live preflight 与 no-goal soak | — | `live_preflight.json` passed=true，46/46 |
| goal 发布 | — | `execution_result.md` 执行 `rostopic pub -1 /move_base_simple/goal` |
| uav1 首次明确的起点占据错误 | 23.694 | `logs/racer.log`：start≈(1.565,-0.057,1.462)，`start inside inflated occupancy` |
| uav1 重复规划失败 | 28.072、29.572、30.893、32.178 | `logs/racer.log`：`No path to next viewpoint`/`Plan fail` |
| uav0 接受唯一轨迹 | 30.092 | `logs/racer.log`：`id=1 start=28.610 duration=4.699` |
| uav0 首个 PositionCommand | 30.101 | `logs/racer.log`：`first pos_cmd`，随后 ACK/pos_cmd 持续 |
| uav0 A* 高负载/超时 | 约 30.77–32.12 | `logs/racer.log`：最高 44579 iterations，outside/inflated_neighbor rejects |
| abort.request | 32.389（metrics clock 32.871 最后采样） | `fleet/abort.request` wall `1787301281.7907858` |

fleet telemetry 窗口为 sim 12.39→32.39、wall 15008.1→15067.2，共 59.0 wall s，
因此 RT factor≈20/59=0.339。证据：`execution_result.md`、`fleet/telemetry.jsonl`、
`fleet/metrics.json`。

## 3. 失败归因

### 3.1 trajectory freshness：误中止（观察 + 时间推论）

abort 唯一原因是 `corrupted_telemetry:uav0:freshness`。uav0 的
`/planning/bspline_1` 全程只有 1 条消息，但 `pos_cmd=278`、`ack=278`、ACK timeout=0。
该 B-spline 的计划区间是 `start=28.610`、`duration=4.699`，计划结束约 sim 33.309；
abort 在 sim 32.389，早于计划结束，且 PositionCommand/ACK 在 abort 前持续出现。

因此可确定：`trajectory` 被当作 5 s wall 连续心跳是合同分类错误，RT≈0.339 将 5 s wall
换算成约 1.7 sim s，放大了误中止。不能据此放宽 odometry/cloud/health/occupancy、
PositionCommand、ACK 或 ACK 1 s 合同；应将 trajectory 保留为 command 阶段的事件/presence
证据，并继续要求至少出现一次。

### 3.2 uav0 A*：真实规划失败（观察）

`logs/racer.log` 在首条轨迹后仍记录大量 A* timeout、`No path to next viewpoint`、
failure memory、planner fail；这与 trajectory freshness 误中止并存，不能把它归入单纯
collector 假阳性，也不能用全局 freshness 调大掩盖。

### 3.3 uav1：真实未接令；peer-body 污染仍是未验证假设

uav1 最终 metrics：`trajectory=0`、`pos_cmd=0`、`ack=0`、`freeze=true`，但 odometry/cloud/
frontier/health/occupancy 均有 payload；日志反复给出自身当前点约
`(1.48–1.56, -0.10–0.06, 1.49–1.51)` 的 `Astar vehicle start is inside inflated occupancy`。
这证明规划器看到的起点被膨胀地图占据，并非 namespace 或消息缺失。

“Gazebo Livox 将另一架 iris 的回波写入共享地图，导致 peer-body occupancy 覆盖 uav1 起点”
与坐标和共享 registered-cloud 链路相符，但本 runroot 没有近机点云/占据来源分类，故只能标为
**待诊断假设**，不能写成已证实根因。不得直接扩大出生间距、降低 inflation、清空起点地图或
删除静态障碍来规避。

## 4. 逐机与 fleet 结果

| 指标 | uav0 | uav1 |
|---|---:|---:|
| trajectory / pos_cmd / ACK | 1 / 278 / 278 | 0 / 0 / 0 |
| ACK timeout | 0 | 0 |
| completion | false | false |
| freeze | false | true |
| crash | false | false |
| path length (m) | 3.3813 | 2.1515 |
| coverage voxels / ratio | 4068 / 0.01513 | 3562 / 0.01325 |
| contact ground/inter-UAV/obstacle | 0/0/0 | 0/0/0 |
| telemetry complete | false，stale trajectory | true（不能代表进入 command） |

fleet：coverage `4458/268912=0.01658`，overlap `0.89051`，map consistency Jaccard
`0.71153`，minimum inter-UAV distance `1.45659 m`，fleet contact `0`，lost-after-seen
为空。abort 时 8/8 进程仍存活；TF 为唯一 `world→uav0/base_link` 与
`world→uav1/base_link`，topic owners 均为单一预期 owner，无 cross-talk。

证据：`uav0/metrics.json`、`uav1/metrics.json`、`fleet/metrics.json`、各自
`telemetry.jsonl`、`fleet/telemetry.jsonl`、`fleet/abort.request`、`live_preflight.json`。

## 5. Luna 判断与后续边界

本轮是**有效但失败的 smoke**，不是 INVALID_RUN：逐机 metrics、fleet metrics、abort、
telemetry、execution result、live/static preflight 和关键日志均存在且相互一致。

建议 Sol/lead 后续仅考虑以下最小修复：

1. collector 将 trajectory 从连续 freshness 改为 command 阶段 presence/event；连续遥测和
   ACK 合同不变。
2. GT mapper 先提供基于冻结 iris 碰撞外形的 self/peer 近机点计数，再决定是否实施紧致、
   可审计的动态机体回波剔除；若证据不足，停止在诊断，不猜测性改地图。
3. runner 最终有效性要求每架 UAV 都实际出现 trajectory、PositionCommand、ACK 且无 ACK
   timeout，避免 uav1 的 `telemetry_complete=true` 被误当作双机功能成功。
4. 修复后必须重新 preflight；当前不签发新 package，不得启动或重试 smoke。

handoff_status: READY_FOR_SOL
handoff_model: sol-finalize-sync
handoff_command:
请审核 state/luna_review.md、对应 RUN-*、manifest 和全部 hash；仅在证据有效时合并正式状态并创建唯一收尾 commit。
