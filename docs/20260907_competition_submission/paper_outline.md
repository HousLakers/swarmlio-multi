# 论文 / 系统报告框架

## 建议题目

**基于国产算力的多无人机具身智能实时感知、协同探索与弹性决策系统**

副标题可用：**从单机激光感知到三机仿真容错与双机实机审计**。副标题比直接写“实机
双机验证”更准确，因为 2026-09-06 18:32 的双机原始证据已经丢失。

## 一、摘要（首稿，提交前按最终指标改写）

面向 GNSS 拒止、先验地图未知和通信不稳定环境下的无人机自主作业，本文设计并实现
了一套面向国产嵌入式算力适配的多无人机具身智能感知与决策系统。系统以 Livox
MID360、IMU、动捕/外部参考和 PX4 飞控为输入，以 Swarm-LIO 完成状态估计与局部地图
构建，以 RACER 完成前沿探索、任务分配和 B-Spline 轨迹规划，并通过带版本号的协同
状态交换与心跳机制完成任务重分配和丢包自愈。针对初始分配不均和确认包丢失问题，本文
比较 MINSUM/MINMAX 目标与容量系数，提出“发送即生效、同方案幂等重答、心跳自愈和异常
回滚”的协议组合。仿真结果表明，在 18 轮矩阵和 3 轮闭环验证中，MINMAX+0.75 的平均
任务失衡比为 1.10、Jaccard 地图一致性为 0.7612；在掉线与 20% 丢包叠加场景中，覆盖率
由 0% 丢包基线的 0.673 降至 0.657，系统无崩溃且在线无人机继续执行任务。单机实机
节点级测试获得 5 cm 地图和 0.9288/0.9874 coverage，但用户确认的 18:32 双机试飞
原始证据缺失，因此本文将双机部分严格报告为证据缺失与失效模式分析，并给出下一轮可审计
preflight 和三机扩展方案。结果说明，面向国产算力适配的感知—分配—执行闭环具有可行性，
但 fleet 级实机精度、实时性、功耗和三机硬件适配仍需用统一 runroot 补齐。

**关键词**：国产算力；无人机具身智能；Swarm-LIO；协同探索；MINMAX 任务分配；
掉线重分配；20% 丢包；PX4

> 摘要中的“获得/表明”只对应 `verified` 证据；双机 18:32 不写成成功飞行。

## 二、论文主线与研究问题

### 2.1 论文要回答的三个问题

1. 在机载资源受限且无先验地图时，20 m 水平全向激光感知、LIO 和 frontier exploration
   能否形成可重复的实时感知—规划底座？
2. 在三机任务分配中，MINMAX 是否比 MINSUM 更能降低工作量失衡；容量约束如何影响
   覆盖率、总路径和地图一致性？
3. 当一架机掉线或 pair-opt 消息丢失时，版本化任务所有权和心跳自愈能否保持核心探索
   不中断，并在 20% 丢包下避免永久重复认领或任务遗漏？

### 2.2 不把实机缺证包装成贡献

实机章节回答的是第四个工程问题：**如何把上述闭环安全地迁移到双机/三机实机，并通过
可审计证据识别失败原因？** 18:32 会话归档为 `EVIDENCE_MISSING`；较早 `fea8` 只作为
`INVALID_RUN` 的诊断案例。这样既保留工程价值，也不把不可复现的现场观察当定量结果。

## 三、章节结构

### 第 1 章 引言

**目的**：把赛题四项约束转成论文问题，而不是泛泛介绍无人机。

- GNSS 拒止、陌生环境、通信断续和国产算力约束。
- 赛题目标：定位/建图精度、≥10 Hz 实时性、≤20% 丢包不中断、≤2 s 重规划、≤30 W、
  多机协同与故障自适应。
- 本文贡献（当前可 defend 的表述）：
  1. 建立一条 Livox/IMU—Swarm-LIO—RACER—PX4 的国产嵌入式闭环，并提供单机仿真与
     节点级实机 baseline。
  2. 用 21 轮三机仿真矩阵证实 MINMAX+0.75 的均衡收益，并给出 C1 重复验证。
  3. 实现掉线检测—释放—最近在线机接管—继续探索闭环，修复 int8 网格编号截断的
     段错误根因。
  4. 用发送即生效、幂等重答、心跳自愈和回滚应对 20% 丢包，并进行掉线叠加验证。
  5. 建立实机证据分级与失效诊断流程，明确双机缺证和三机待验收项。

### 第 2 章 相关工作与赛题需求映射

建议只保留与方法选择直接相关的四组文献：激光/视觉惯性 SLAM、frontier exploration、
多机器人任务分配、容错通信/分布式一致性。每组文献最后用一段指出本文缺口：资源受限
国产平台、统一地图/任务协议、掉线和丢包叠加、实机证据闭环。

表 1 用 `evidence_matrix.md` 的指标表，逐项列出赛题阈值、本文实现、证据状态，不提前
声称“满足全部指标”。

### 第 3 章 系统总体设计

#### 3.1 硬件与软件栈

- 机载：Khadas（当前已接入 UAV1/2；三机 UAV3 信息留空）、Livox MID360、IMU、PX4。
- 网络：唯一 ROS Master `192.168.100.62:11311`；现场 ROS IP 为 UAV1
  `192.168.100.62`、UAV2 `192.168.100.65`，热点管理地址 `.151/.59` 只用于 SSH。
- 软件：ROS1、Swarm-LIO、RACER exploration/solver/relay、MAVROS、PX4 bridge、
  recorder。
- 命名隔离：`/cloud_registered_N`、`/lidar_slam/odom_N`、`/lidar_slam/pose_N`、
  `/planning/pos_cmd_N`、`/keys_N`、`/uavN/mavros/...`。

#### 3.2 双机话题传递图

引用 [topic_flow_dual_real.html](../../topic_flow_dual_real.html) 和规格
`../../topic_flow_dual_real.dataflow.json`。图中分为共同输入/传感器、逐机状态估计、
协同交换、执行/记录、反馈/证据五段，并明确“共享触发 ≠ 共享控制”。

#### 3.3 三机扩展原则

- `drone_num=3`、每机独立 `drone_id`、`keys_topic`、MAVROS namespace 和 FCU system ID。
- UAV1 保留唯一 ROS Master/VRPN 启动职责；UAV2/UAV3 只加入节点和传感器链。
- 第三机未提供的 IP、雷达型号、串口和硬件确认均留空；在硬件核实前不执行。
- 具体脚本包、源 hash、manifest 和 dry-run 收据见 `deploy_triple_real/`。

### 第 4 章 感知、建图与在线探索

#### 4.1 LIO 状态估计

说明 Livox 点云、IMU、VRPN/外部参考如何经 pose→odom bridge 进入 Swarm-LIO，输出
odom/pose/registered cloud。给出时间戳、坐标系、frame_id、外部视觉 remap 契约；把
“MAVROS `/vision_pose/pose` 一对一 ingress”作为实机验收门，而不是默认成立。

#### 4.2 地图与 frontier

说明 5 cm voxel/PGM、局部 occupancy、frontier/viewpoint 生成和 A* / B-Spline。将
地图 z 下限、规划 box 和起点坐标写入实验配置表，解释 2026-09-04 曾出现“起点在规划
盒外、A* 26 个邻居全部 outside”的失败案例，证明 box 检查必须先于起飞。

#### 4.3 实时性定义

定义 LIO 频率、frontier 更新频率、规划响应时间和 command ACK 的测量窗口；不要用
“节点存在”替代频率证据。下一次 runroot 必须同时保存 `/clock`/wall time、topic hz、
planner event、bridge ACK 和 stop 时间。

### 第 5 章 多机任务分配与弹性决策

#### 5.1 任务分配目标

- MINSUM：最小总路径；MINMAX：最小最长单机路径/负载不均衡。
- 容量系数 0.75/0.50；评价 fleet ratio、路径失衡比、Jaccard、overlap、总路径。
- 解释“路径换均衡”：A2 MINMAX+0.75 失衡比 1.43±0.20，MINSUM+0.75 为 2.41±1.03，
  但 A2 总路径更长；不能只报 coverage。

#### 5.2 21 轮仿真设计

6 组（A1–A3 无掉线、B1–B3 掉线）×3 重复 + C1（MINMAX+0.75、无掉线）×3；每轮
300 s，公共 `racer_outdoor_50x50_v1`，掉线注入为 `uav1@60 s`。报告均值±标准差、
run ID 和 abort/安全门，附 `experiments/REPORT_P0_MATRIX_CLOSEOUT.md`。

#### 5.3 掉线接管闭环

用状态机图描述：心跳 watchdog → 失联确认 → 释放未探索 grid → 最近在线机唯一接管 →
重新规划 → 继续探索。解释 `int8[]→int32[]` 修复：网格 id 128–179 被截断成负数导致
越界/段错误；加入消息层和索引层守卫。

#### 5.4 20% 丢包协议

说明发送即生效、stamp 幂等重答、25 Hz 心跳、编号小者保留和异常回滚；用 0%/20% 对照
表格报告实际丢弃消息、覆盖率、冲突自愈、崩溃/负 id/回滚/超时。把 0.657/0.673 写成
仿真证据，不写成真实无线链路测量。

### 第 6 章 实验与结果

#### 6.1 仿真单机感知 baseline

表 2：60.20 s、coverage 0.7294、ATE RMSE 0.0802 m、P10 clearance 1.898 m、所有安全
事件为 0。说明 ATE 的 GT 来源和 RMS 定义；若正式提交仍只有该 run，标题写“仿真 ATE”。

#### 6.2 三机分配结果

图 4：A1/A2/A3 的失衡比—总路径 Pareto；图 5：C1 三重复的 coverage/Jaccard/overlap。
表 3：A/B/C 组均值±标准差和 run ID。结论限定为仿真。

#### 6.3 掉线 + 丢包结果

表 4：32（0%）与 33（20%）轮；图 6：coverage 曲线、任务所有权冲突自愈时间线。
重点写“任务继续增长、无崩溃”，不要把 20% 丢包写成底层网络吞吐测试。

#### 6.4 单机实机节点级 baseline

表 5：UAV1 `RUN-20260906T075343Z`（34.64 m、0.9288）和 UAV2
`RUN-20260906T061914Z`（55.34 m、0.9874、4,908 cloud points、5,800 occupancy
points、5 cm PGM）。指出时长/停止时刻不同，不能横向比较速度，也不能当双机结果。

#### 6.5 双机实机：证据缺失与失效诊断

单独设为“工程审计”小节：

- 18:32 目标：`EVIDENCE_MISSING`，没有对应 runroot/rosout/bridge/bag/ULog。
- 18:30 c89：`WAIT_TRIGGER=180`、trigger=0、`Empty dominance=42`、A* 26 neighbors
  outside；只支持触发前故障诊断。
- 较早 fea8：planner trigger 相差 0.554 s，但 ID2 `Empty dominance/No grid`，ID1
  反复 `No path`，bridge 均未通过 armed/hover gate，`INVALID_RUN`。
- 根因层级：ID1 初始 grid ownership + ID2 未完成重分配；ID1 LIO z≈0.025 与 box
  `z_min=0.5` 不一致；双机 external-vision remap/keys_topic 流程缺陷；ID2 还需
  查本机 cloud/odom/pose 连续性。`EKF Tracker reset!` 仅能说明队友/临时目标 tracker，
  不能直接等同主 LIO EKF reset。

证据索引：`state/dual_diagnosis_20260907/report.md`、
`state/real_dual_audit_20260906/report.md`、`state/dual_diagnosis_20260907/c89_1828_1835_excerpt.txt`。

### 第 7 章 讨论、局限与下一步

#### 7.1 当前能支持的结论

- 仿真层：任务均衡、掉线接管、20% 丢包自愈可复现。
- 节点实机层：单机 LIO/规划/记录链有可用 baseline，但每架保存完整性不同。
- 工程层：缺证分类和 preflight 门能阻止把近地面/空 grid/未 armed 误报为飞行成功。

#### 7.2 当前不能支持的结论

- 不能声称 18:32 双机已满足 ATE、≥10 Hz、≤2 s、5 cm fleet map、最小间距或零碰撞。
- 不能声称目前达到 ≤30 W 或“全国产化”；需补 SoC/OS/功耗与供应链证据。
- 不能把 UAV2 路径更长归因于 leader 单点规划；现有代码两端均有 planner，历史记录只
 证明 ID1 初始 ownership 和 ID2 空 grid。

#### 7.3 下一轮验收顺序

1. 不解锁双机 preflight：`/keys_1/2`、namespace、cloud/odom/pose 连续性、vision remap、
   FCU local_position payload/frequency、grid ownership、pair-opt ACK。
2. 每机独立 hover gate 后再触发；一架机失败时保存完整 evidence 并 fail-closed。
3. 成功双机后复用 manifest 结构扩展三机；先补 UAV3 硬件/IP/几何，再做 3-UAV preflight。
4. 采集 ATE（VRPN/GT 对齐）、地图分辨率、规划响应 p95、LIO Hz、功耗、最小机间距、
   packet-loss/dropout fault labels 和完整 ULog。

## 四、论文图表清单

| 编号 | 图/表 | 当前来源 | 状态 |
|---|---|---|---|
| 图 1 | 总体系统架构 | `topic_flow_dual_real.html` + 三机启动路径 | 可用，视觉审阅待 Chrome |
| 图 2 | 双机话题传递图 | 同上 | Archify showcase 9/9；浏览器检查 skipped |
| 图 3 | 弹性决策状态机 | `experiments/子系统失效改动.md` | 待用 Archify 重绘 |
| 图 4 | A/B/C 分配矩阵对比 | `REPORT_P0_MATRIX_CLOSEOUT.md` | 已有数据，需统一配色 |
| 图 5 | 20% 丢包覆盖率/自愈时间线 | `多机容错通信改进总结_掉线任务重分配与20%丢包_20260822.md` | 已有数据，需绘图 |
| 图 6 | 单机实机轨迹与 5 cm PGM | `state/real_dual_audit_20260906/figures/` | 可引用，标节点级 |
| 图 7 | 双机失效诊断时间线 | `state/dual_diagnosis_20260907/` | 待整理，明确 EVIDENCE_MISSING |
| 表 1 | 赛题指标证据矩阵 | `evidence_matrix.md` | 本目录新建 |
| 表 2 | 运行/版本/hash 台账 | `BUILD_RECEIPT.json`、runroot index | 待正式汇总 |

## 五、投稿前数字审计清单

- 每个 coverage、ATE、path、Jaccard、失衡比都有 run ID/脚本/源文件。
- 0%/20% 丢包、仿真/实机、单机/双机/三机不混用单位和图例。
- 双机目标时间写 `EVIDENCE_MISSING`；历史 fea8 写 `INVALID_RUN`。
- 所有“满足指标”改为“在何种实验条件下满足”；缺失项写下一次验收方法。
- 表格、正文、PPT 共用 `evidence_matrix.md`；修改数字先改矩阵再改其它文件。
