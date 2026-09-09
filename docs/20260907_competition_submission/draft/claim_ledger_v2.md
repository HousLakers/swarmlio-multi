# 论断与证据台账 v2

日期：2026-09-08。对应 [正文 v2](paper_draft_v2.md)、[框架 v3](../paper_writing_framework_v3.md)。状态：`READY_FOR_REVIEW`，稿件仍为 `DRAFT_NOT_SUBMITTABLE`。本台账是证据审校附件，不进入论文正文。

## 1. 证据等级

| 等级 | 含义 | 可支持范围 |
|---|---|---|
| METHOD_SOURCE | 原论文或本地实现的只读核对 | 方法说明，不代表当前实验启用或验证 |
| SIM_GT_INDEXED | 索引绑定的三机 GT 注册仿真指标 | 固定场景内的描述统计，不代表实机 LIO |
| SIM_REPORT_ONLY | 历史报告中的结果，完整记录绑定不足 | 明示来源的受限转述，不进入主统计 |
| REAL_NODE_BASELINE | 独立单节点轨迹、地图或字段记录 | 节点产物，不代表多机同步成功 |
| EVIDENCE_MISSING | 所需证据缺失 | 仅保留缺项，不能写零值或成功 |
| INVALID_RUN | 有记录但不满足有效性要求 | 不作为正面结果或成功率分母 |
| REQUIREMENT / DESIGN | 赛题阈值或系统设计 | 目标、接口，不是实测结论 |

## 2. 核心论断映射

| ID | 正文位置/图表 | 论断 | 等级与来源 | 审核结论 |
|---|---|---|---|---|
| K1 | 2.1–2.3；图1；表3–5 | 逐机感知、规划、控制与协同交换的架构 | DESIGN；旧SVG、根目录单/双机 Archify JSON；本轮图1 JSON | 可写设计，不推断三机实飞 |
| K2 | 摘要、3.2、4.2、6.2；图3、表8 | A2 的占据比例与路径均衡相对 A1 改变，同时总路径增加 | SIM_GT_INDEXED；matrix_records/statistics JSON | 数值可复算；不写显著性、完成时间收益或全面最优 |
| K3 | 3.3、4.2、6.3；图2、表14 | 失联判断后释放与接管任务 | METHOD_SOURCE + B组节点级注入 | 掉线是 intentional_dropout；不能改称碰撞/坠机容错 |
| K4 | 3.3、4.2；图2/4、表9 | 重传、重答、拒绝回滚与心跳归属协调 | 本地任务协议；第32/33轮报告 | 只注入任务层消息；等待超时不统一回滚；无时限证明 |
| K5 | 4.1、5.1–5.3、7.1；表7/10–12/15 | 按仿真、单节点实机和fleet实机分层评价 | 所给证据矩阵、实机归档与审查记录 | 不跨层借用成功结论 |
| M1 | 1.2、3.1 | LIO预测校正与协同观测原理 | METHOD_SOURCE；文献[1–3] | 方法背景；GT注册矩阵不测试LIO精度 |
| M2 | 1.2、3.2、6.2 | frontier、层次网格与去中心化分配继承关系 | 文献[4–7] | RACER已有负载考虑，不主张首次负载均衡 |
| M3 | 3.2、6.1；表13 | 进展、重复目标和轨迹安全接口 | DESIGN/METHOD_SOURCE；现有机制材料 | 主矩阵 progress_guard/globaltrajectoryguard 未启用，无消融收益 |
| R1 | 4.1–4.2；表6/8 | A/B每组n=3，C1补充n=2 | matrix_results.jsonl及精确run指标 | 共18条主结果+2条补充；C1-r2不纳入 |
| R2 | 4.1 | 0.1 m规划SDF、0.25 m统计体素、268912分母 | 各run static.yaml与fleet/metrics.json | 修正v1混写5 cm；不变更原始文件 |
| R3 | 4.1–4.2 | J和O均取所有节点对最小值 | 指标定义及two_uav_collector.py中的集合计算 | 高overlap不说明低重复探索 |
| R4 | 4.2；表9 | 0.673、0.657及其约97.6%之比 | SIM_REPORT_ONLY；第32/33轮报告 | 两条件均叠加75 s掉线，n=1/条件，无误差线 |
| R5 | 4.2；表9 | 60.20 s、72.94%、11.94 m、ATE 0.0802 m、P10 1.898 m | SIM_REPORT_ONLY；阶段报告20260825 | 完整run ID/样本合同不足，不用于实机ATE |
| R6 | 5.2；表11、图5 | R1/R2/R3轨迹数、XY路径、末次coverage | REAL_NODE_BASELINE；原CSV与地图元数据 | 不同窗口/边界，不作效率排名；R2有1条不完整轨迹行被排除 |
| R7 | 5.2；图5、表10 | R1/R3二维PGM与同记录轨迹 | REAL_NODE_BASELINE | 不猜测点云world→planner变换，不作跨机配准 |
| R8 | 4.2 | 主矩阵fleet接触计数0 | fleet/metrics.json | 检测阈值依赖；不是安全距离或全程无碰撞证明 |
| T1 | 1.3、7.1；表2/15 | ATE、10 Hz、2 s、30 W等目标 | REQUIREMENT；所给比赛方案第6页 | 测量列留空；地图验收原文语义待确认 |

## 3. 索引去重、纳入与统计合同

原始索引 `experiments/matrix_results.jsonl` 有30条追加记录，对应21个逻辑槽，包含重试、失败和同run简写。不得把追加行数当重复次数。派生脚本按每个逻辑key的最终done记录定位runroot，并仅在解析到同一绝对路径时补全既有hash；同路径hash冲突立即报错。A1-r1的简写行缺hash，第一条完整行的manifest/source hash与归档approval匹配，因此保留，不能误判为hash不一致。

纳入的20条记录均有execution_result.json、duration_complete、最终安全门通过及telemetry完整标记。此处“通过”仅描述归档门值，不等于完整探索、理论安全保证或独立复现实验。C1-r2（RUN-20260824T100002Z-3uav-smoke）缺execution_result.json，末次仿真clock为608.674 s，历史记录为人工终止；与名义300 s窗口不一致，不进入同条件补充统计。

统计均值为单次指标的算术平均，标准差为样本标准差（ddof=1）。B=每次三机path最大/最小，再对B求均值；不是均值路径的比。J/O使用归档指标，不能从平均集合重新构造。主比较仅A/B；C1保留n=2并用分隔线区别。源文件hash清单见 [input_hashes.json](audit_v2/input_hashes.json)，单条指标见 [matrix_records.json](audit_v2/matrix_records.json)，汇总见 [matrix_statistics.json](audit_v2/matrix_statistics.json)。

历史C1 n=3受限汇总可追溯值：占据比例0.2258347±0.0049767，总路径819.4949907±142.6659224 m，不均衡度1.1048558±0.0245467，J=0.7611703±0.0236801，O=0.8938736±0.0126799。仅在本台账保存历史口径，不放入正文主表，也不称最优。

## 4. 精确来源

仿真主索引：`experiments/matrix_results.jsonl`；每个下列run读取 `fleet/metrics.json`、`uav0/metrics.json`、`uav1/metrics.json`、`uav2/metrics.json`、manifest、static、preflight及可用execution/approval。不扫描整个results目录。

| 逻辑槽 | run ID（均位于results/） | 角色 |
|---|---|---|
| A1-r1 | `RUN-20260823T213717Z-3uav-smoke-A1-r1` | main |
| A1-r2 | `RUN-20260823T215638Z-3uav-smoke-A1-r2` | main |
| A1-r3 | `RUN-20260823T221655Z-3uav-smoke-A1-r3` | main |
| A2-r1 | `RUN-20260824T002722Z-3uav-smoke-A2-r1` | main |
| A2-r2 | `RUN-20260823T224518Z-3uav-smoke-A2-r2` | main |
| A2-r3 | `RUN-20260824T092806Z-3uav-smoke-A2-r3` | main |
| A3-r1 | `RUN-20260823T230840Z-3uav-smoke-A3-r1` | main |
| A3-r2 | `RUN-20260823T232924Z-3uav-smoke-A3-r2` | main |
| A3-r3 | `RUN-20260823T234944Z-3uav-smoke-A3-r3` | main |
| B1-r1 | `RUN-20260824T010835Z-3uav-smoke-B1-r1` | main |
| B1-r2 | `RUN-20260824T012342Z-3uav-smoke-B1-r2` | main |
| B1-r3 | `RUN-20260824T013834Z-3uav-smoke-B1-r3` | main |
| B2-r1 | `RUN-20260824T015334Z-3uav-smoke-B2-r1` | main |
| B2-r2 | `RUN-20260824T020835Z-3uav-smoke-B2-r2` | main |
| B2-r3 | `RUN-20260824T022347Z-3uav-smoke-B2-r3` | main |
| B3-r1 | `RUN-20260824T023856Z-3uav-smoke-B3-r1` | main |
| B3-r2 | `RUN-20260824T025403Z-3uav-smoke-B3-r2` | main |
| B3-r3 | `RUN-20260824T030857Z-3uav-smoke-B3-r3` | main |
| C1-r1 | `RUN-20260824T110657Z-3uav-smoke` | supplement |
| C1-r2 | `RUN-20260824T100002Z-3uav-smoke` | excluded_duration_incomplete |
| C1-r3 | `RUN-20260824T112459Z-3uav-smoke` | supplement |


历史报告：`experiments/多机容错通信改进总结_掉线任务重分配与20%丢包_20260822.md`；`experiments/REPORT_阶段成果整合汇报_20260825.md`。第32/33轮为300 s、30×30 m报告；`RUN-20260827T040141Z-3uav-verify-droploss20-90s`属于另一次短时记录，未拿来补齐报告的run ID。

协议依据：`SKM/swarm_exploration/exploration_manager/src/fast_exploration_fsm.cpp`中droneStateCb、offlineCheck、成对优化发送/响应/超时以及simulateDrop逻辑。只读核对；现有代码状态不自动等于历史run全部源码。任务协议的0.04 s发送、5 s离线检查与Swarm-LIO2内部心跳属于不同层，未混用。

实机来源：

| 记录 | 精确run目录 | 本轮使用 |
|---|---|---|
| R1 | `state/khadas_real_runs_20260904/RUN-20260904T093149Z` | trajectory.csv、coverage.csv、metadata.json、grid_map.pgm |
| R2 | `state/real_dual_audit_20260906/single_baseline/board_192.168.43.151_id1/RUN-20260906T075343Z` | trajectory.csv、coverage.csv、metadata.json；无地图 |
| R3 | `state/real_dual_audit_20260906/single_baseline/board_192.168.43.59_id2/RUN-20260906T061914Z` | trajectory.csv、coverage.csv、metadata.json、grid_map.pgm |

既有索引：`state/real_dual_audit_20260906/single_overlays_20260907/single_overlay_metrics.json`。本轮图表不根据旧PNG反推数据。

实机时长口径修正：旧汇总为末次elapsed值126.639638、43.246419、84.271068 s；本稿表11明确使用首末有效轨迹之差126.615676、43.214285、84.207637 s。此修正发生于数字冻结及polish-prose之前。有效样本数与XY路径未变化。R3点云旧metadata记4832，既有实际点数统计4908；正文未使用该点数，以免把缓存字段与产物混为一谈。

## 5. 明确保留的否定与缺项

| 项目 | 必须保留的状态/来源 | 正文处置 |
|---|---|---|
| 2026-09-06 18:32双机 | EVIDENCE_MISSING；`state/real_dual_audit_20260906/SESSION_TIME_CORRECTION_1832.md` | 5.1明示，不纳入成功 |
| 历史fea8双机 | INVALID_RUN；同目录report.md、trigger_local_position_audit.md | 5.1明示，不纳入成功 |
| 三机实机成功 | EVIDENCE_MISSING | 图6与表12/15空位 |
| 实机ATE | EVIDENCE_MISSING | 表12/15空位；0.0802 m明确单机仿真报告 |
| 统一≥10 Hz | EVIDENCE_MISSING | 不能用25 Hz配置心跳或采样密度代替 |
| ≤2 s重规划 | EVIDENCE_MISSING | 3.3拆解计时；P95不证明最大值；离线检测间隔不能隐去 |
| ≤30 W | EVIDENCE_MISSING | 计算平台供电边界待测，不使用CPU负载换算功耗 |
| 室内六/十机与室内三机 | EVIDENCE_MISSING | 表7空位；50×50代理场景不能顶替室内 |
| AirSim闭环 | 尚无本稿可采纳的合格成功证据 | 表7/15空位；冻结输入时latest_result为AF3.1-R6失败，不追入并行后续任务 |
| 完整国产化 | EVIDENCE_MISSING | 表4/15；品牌、国产板卡与完整证明分开 |

缺项均采用五字段占位符。后续填入必须同时更新正文、数值ledger、图数据、该台账与QA，不仅删除“待填”。本轮不授权新增实验。

## 6. 结论强度与审校

没有使用“显著提升”“首次”“全面最优”“三机成功”“全部指标达标”作为无条件正面结论。系统贡献限于工程组织、目标比较与任务协议；图1/2为机制图，图3/4/5为不同层级数据图，图6为空图位。数字一致性验证只说明归档指标与正文相符，不授予复现、独立验证或安全认证。
