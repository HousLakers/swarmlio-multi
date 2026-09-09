# 赛题指标—证据矩阵（2026-09-07）

状态定义：

- `verified-sim`：仿真 runroot 中有完整指标，可写为仿真验证。
- `report-level-sim`：项目报告给出了结果，但当前工作区尚未把对应完整 runroot 与 manifest 一一定位；可作为阶段性结果，不能冒充完整可复现实验。
- `verified-node-real`：单机实机节点级证据，可写为节点 baseline，不能外推 fleet。
- `partial`：有配置/局部观测/单机证据，但缺少赛题要求的完整闭环。
- `missing`：本轮没有合格证据，不能用主观观察补齐。
- `invalid`：找到记录但未通过安全门或结果不可比，不得作为成绩。

| 赛题要求 | 当前状态 | 已有证据 | 论文/PPT 写法 | 下一次合格证据 |
|---|---|---|---|---|
| 室内 ATE RMS ≤0.3 m | `report-level-sim`（不是实机，场景口径待核） | 单机仿真 ATE RMSE 0.0802 m；来源 `experiments/REPORT_阶段成果整合汇报_20260825.md`；当前未定位对应完整正式 runroot | “阶段报告中的单机仿真 ATE 为 0.0802 m”；不要写成室内指标或双机实机 ATE 已达标 | 找回单机 runroot，确认室内场景口径，并保存每架 real run 的 VRPN/GT、LIO odom、时间对齐脚本和 RMS 统计 |
| 室外 ATE RMS ≤0.5 m | `missing` | 尚无合格室外 real/sim ATE 表 | 明确“待测” | 50×50 m/实机场地统一 box，输出 APE/ATE、样本数、时间窗和坐标变换 |
| 三维地图分辨率 ≥5 cm | `partial` | 规划配置 `map/grid_resolution=0.05`；UAV2 单机保存 5 cm PGM | “配置为 5 cm，UAV2 节点 baseline 形成 5 cm PGM”；不宣称双机 merged map | 双机/三机保存全局 merged map、分辨率元数据、点云/栅格一致性 |
| 单机定位建图 ≥10 Hz | `partial` | 历史 handoff 报告有约 10 Hz odom 观察，但本目标双机没有统一频率 runroot | 写“待用 topic-hz 复核” | 每架连续记录 `/lidar_slam/odom_N`、cloud、pose 的频率分布（mean/p50/p95/min） |
| 丢包率 ≤20% 核心任务不中断 | `report-level-sim` | 报告记录 300 s 第 33 轮，20% 丢包；coverage 0.657 vs 0% 0.673（97.6%），无崩溃；当前可定位的 `RUN-20260827T040141Z-3uav-verify-droploss20-90s` 是不同的短时检查 | 可写“阶段报告中的任务层丢包仿真保持 97.6% coverage”；不能写成底层无线吞吐实测，也不能把短时检查当 run33 | 找回 run32/run33 原始 runroot，补 manifest、底层链路/任务层丢包标记、消息计数、延迟和连续任务状态 |
| 多机协同定位/建图 | `verified-sim`；`missing` real fleet | 21 轮三机仿真；双机 18:32 runroot 丢失，历史 fea8 `INVALID_RUN` | 仿真结果单独成节；实机写证据缺失 | 双机先过 preflight，再采集 merged map、双方 pose、ACK、最小间距和 fleet runroot |
| 在线重规划响应 ≤2 s | `missing` | 现有资料有规划事件/超时，但无统一 p95/p99 响应指标 | 不写“满足” | 记录 obstacle/failure event→new B-Spline/pos_cmd 的时间差，报告 n、p50/p95/max |
| 突发障碍/子系统失效弹性决策 | `verified-sim`（掉线）；`partial`（更广失效） | 掉线检测—释放—接管连续 3 轮；20% 丢包叠加轮无崩溃；五维 health 仍是后续方向 | 写“通信掉线/丢包场景验证”；定位/建图/执行失效暂列 future work | 统一 `HEALTH_HOLD`、定位/建图/规划/执行失效注入和恢复证据 |
| 单机总功耗 ≤30 W | `missing` | 未有板级电压/电流/功率时间序列 | 明确“待测” | 机载电源端采样，记录 idle/LIO/planner/peak、采样率、传感器和板卡清单 |
| 国产算力/系统/组件 | `partial` | 已使用 Khadas + ROS/Swarm-LIO/Livox/PX4；具体 SoC、OS、供应链证明未归档 | “国产算力适配进行中”；不要声称全国产化 | 记录板卡 SoC、OS 版本、驱动来源、BOM、功耗与可替代性；按赛题加分项逐项核验 |
| 可运行原型与演示视频 | `partial` | UAV1/UAV2 已连接并有单机节点 baseline；三机 UAV3 硬件未填；双机目标数据丢失 | “原型链路已搭建，双机证据需重采集” | 固定相机视角视频 + run ID/时间牌 + 机载 ULog/rosout/recorder 归档 |
| 实验可审计性 | `partial` | 单机/历史双机审计、manifest、hash 和 Archify receipt 已有 | 将证据分级与 fail-closed 作为工程贡献 | 新 run 必须包含 manifest/approval/source hash、每机 runroot、metrics、failure classification |

## 证据优先级与写作禁用词

### 最高优先级（下一轮 preflight 必须补）

1. 两机每架 `/cloud_registered_N`、`odom_N`、`pose_N` 连续性和 timestamp 对齐。
2. `/uavN/mavros/local_position/pose` payload、频率、external-vision 一对一 remap。
3. grid ownership 非空、pair-opt proposal/response/ACK、trajectory/command ACK。
4. 每架 armed/OFFBOARD/hover gate、规划开始时 z、最终 ULog/bag/rosout。

### 禁用或必须加限定的表述

- 不写“18:32 双机成功”“双机 ATE 达标”“无碰撞已证明”：该时段是 `EVIDENCE_MISSING`。
- 不写“RACER 只运行在 UAV1”：源码显示两端都有 planner；只能写 ID1 初始 grid ownership
  和 ID2 `Empty dominance/No grid`。
- 不写“EKF Tracker reset 就是本机 LIO EKF reset”：当前日志来源是队友/临时目标 tracker。
- 不写“全国产化”“≤30 W”“实时重规划 ≤2 s”，除非新增带原始采样的证据。

## 推荐主结果表（论文与 PPT 共用）

| 层级 | 主指标 | 当前可展示数字 | 图注限定 |
|---|---|---:|---|
| 仿真单机 | ATE RMS | 0.0802 m | 阶段报告；60.20 simulated s，单机，原始 runroot 待补 |
| 仿真三机 C1 | fleet ratio | 0.2258 ± 0.0050 | MINMAX+0.75，无掉线，n=3 |
| 仿真三机 C1 | imbalance | 1.10 ± 0.02 | 同上 |
| 仿真三机 C1 | Jaccard | 0.7612 ± 0.0237 | 同上 |
| 仿真容错 | coverage | 0.657 vs 0.673 | 阶段报告级结果；20% vs 0% 任务层丢包，第 33/32 轮，原始 runroot 待补 |
| 单机实机 UAV1 | XY path / coverage | 34.64 m / 0.9288 | 节点级 baseline，云/占用保存竞态 |
| 单机实机 UAV2 | XY path / coverage | 55.34 m / 0.9874 | 节点级 baseline，5 cm PGM 已保存 |
| 双机目标 18:32 | status | `EVIDENCE_MISSING` | 不放入成绩柱状图 |
| 双机历史 fea8 | status | `INVALID_RUN` | 诊断/失败复盘，不放入成功率 |
