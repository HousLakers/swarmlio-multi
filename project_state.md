# SwarmLIO Multi-UAV Project State

更新时间：2026-08-21
正式阶段：`TWO_UAV_SMOKE_FAIL_DIAGNOSIS / BLOCKED_PENDING_MINIMAL_REPAIR`

## 冻结身份

- multi 基点：`41879e8ccea783895965831f75646ac2a6a43ed7`，branch `main`，remote
  `https://github.com/HousLakers/swarmlio-multi.git`；
- platform：`57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`；
- single：`c01f1f5af40ec25631aa11765a0f21e06834abc4`；
- 节点 baseline：`range20m_omnidirectional_v1`，20 m、水平 360°；
- 公共环境：`racer_outdoor_50x50_v1`，manifest SHA-256
  `ce595cafba088955b38c4c9bd1d08f9af254dbfa0bf013481372a75e17980944`；
- 实验 manifest SHA-256：
  `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`；
- source-hash manifest SHA-256：
  `0970f2e4b29aad999753270adb2cd8535d53826b4b0b651bced887e559657596`，12/12。

单机结论保持 `FUNCTIONAL_VALIDATION_PASS / FORMAL_ENDURANCE_INCOMPLETE`，只作为节点级
baseline，不外推为 fleet 结论。

## 2-UAV 接入与实验事实

多机 runner/launch/preflight/collector、namespace、MAVLink ID/端口、日志目录、唯一 TF、
参数回读、逐机/fleet metrics 和一次性 approval/receipt 门已形成可审计实现。

`results/RUN-20260821T082048Z-2uav-preflight/`：静态 53/53、live 48/48，通过。两机
raw/registered cloud、MAVROS/registered odom、frontier、TF、owner、参数、日志、watchdog、
8/8 node liveness、final metrics 与 final safety 均通过；RT factor≈0.306。

`results/RUN-20260821T083254Z-2uav-smoke/`：有效但失败。goal 后运行至 sim 32.39/120，
`exit_reason=abort_requested`，RT factor≈0.339。uav0 trajectory/pos_cmd/ACK=1/278/278、
path=3.381 m、freeze=false；uav1=0/0/0、path=2.151 m、freeze=true；两机 completion=false、
crash/contact=0。fleet coverage=0.01658、overlap=0.89051、map consistency=0.71153、最小
机间距离=1.45659 m，abort 时 8/8 节点和唯一 TF/owner 合同仍正常。

## 审核结论

直接 abort `corrupted_telemetry:uav0:freshness` 是 collector 合同错误：事件型 trajectory
被当作 5 s wall 连续心跳。该 B-spline 计划结束约 sim 33.309，abort 在 sim 32.389，
当时 PositionCommand/ACK 仍持续。

同时存在不能掩盖的真实故障：uav0 在首条轨迹后出现 A* timeout/no path；uav1 从未进入
command 链，并反复报告当前起点位于 inflated occupancy。Gazebo Livox 的 peer-body 回波
污染共享地图是当前首要但未验证的假设，必须先用近机点计数/来源证据确认。

当前无有效 approval package。preflight package `57a21fa5…b9fa4` 与 smoke package
`3986a46c…0038` 均已消费并永久禁止复用。本轮不得写成 2-UAV/fleet PASS。

## 下一步唯一动作

Lead 按 `state/sol_plan.md` 第 19 节签发最小 Terra 任务：

1. collector 将 trajectory 改为 command 阶段 presence/event，保持连续遥测与 ACK 门；
2. GT mapper 增加基于冻结 iris 外形的 self/peer 近机点诊断，仅在证据成立时实施紧致机体
   回波剔除；
3. runner 最终有效性要求每架 UAV 都有 trajectory、PositionCommand、ACK 且无 timeout；
4. 更新对应 source hash 和 Terra 证据，只运行离线验证。

修复经 Sol 审核后必须先签发新的单次 preflight；preflight 再次通过后才可评估新 smoke。
禁止修改单机/RACER 参数、manifest/static 参数、world/spawn、freshness/ACK 阈值，禁止复用
旧 runroot/package、现场调参、直接 smoke、长跑、参数搜索或 push。Git push 仍需用户另行授权。
