# Claim ledger v1（内部审计，不进入论文正文）

状态定义：`verified-sim`、`report-level-sim`、`verified-node-real`、`partial`、`missing`、`invalid`。本表保留证据边界，正文只引用经过筛选的论文级表述。

| ID | 论文候选论断 | 层级 | 状态 | 证据/来源 | 正文处理 |
|---|---|---|---|---|---|
| C01 | 系统由激光/IMU、Swarm-LIO、RACER、MAVROS/PX4 和记录器组成闭环 | system | partial | `topic_flow_dual_real.dataflow.json`；部署/启动路径 | 可写系统架构，不写全部指标达成 |
| C02 | 三机矩阵包含 A1–A3、B1–B3、C1 共 21 次运行 | sim | verified-sim | `experiments/REPORT_P0_MATRIX_CLOSEOUT.md`；`experiments/matrix_results.jsonl` | 可写，保留场景和 registration 来源 |
| C03 | C1 fleet coverage ratio 为 0.2258±0.0050 | sim | verified-sim | `experiments/REPORT_P0_MATRIX_CLOSEOUT.md` | 可写，标 50×50 m/三机/GT registration |
| C04 | C1 load imbalance 为 1.10±0.02 | sim | verified-sim | 同上 | 可写，限定为代理场景 |
| C05 | C1 Jaccard 为 0.7612±0.0237 | sim | verified-sim | 同上 | 可写，限定为代理场景 |
| C06 | 20% 任务层丢包 coverage 为 0.657，0% 为 0.673 | sim | report-level-sim | `experiments/多机容错通信改进总结_掉线任务重分配与20%丢包_20260822.md` | 可写但必须注明报告级、任务层注入 |
| C07 | 20% 丢包保持约 97.6% 基线 coverage | sim | report-level-sim | 同上 | 可写但不得称真实无线测量 |
| C08 | 单机仿真 ATE RMSE 为 0.0802 m | sim | report-level-sim | `experiments/REPORT_阶段成果整合汇报_20260825.md` | 可写但注明正式 runroot 待绑定 |
| C09 | UAV1 单机 path/coverage 为 34.64 m/0.9288 | real node | verified-node-real | `state/real_dual_audit_20260906/single_overlays_20260907/single_overlay_metrics.json` | 可写为节点 baseline |
| C10 | UAV2 单机 path/coverage 为 55.34 m/0.9874 | real node | verified-node-real | 同上 | 可写为节点 baseline |
| C11 | UAV2 保存 5 cm PGM、4908 cloud、5800 occupancy | real node | verified-node-real | 同上 | 可写为节点 baseline |
| C12 | 18:32 双机目标结果为成功 | real fleet | missing | `state/real_dual_audit_20260906/SESSION_TIME_CORRECTION_1832.md` | 不得写；正文只保留结果待补接口 |
| C13 | 历史 fea8 可作为双机成功结果 | real fleet | invalid | `state/real_dual_audit_20260906/report.md` | 不得写；内部仅作失效分类 |
| C14 | 真实双机 ATE/融合地图/统一频率已达标 | real fleet | missing | `evidence_matrix.md` | 留空 |
| C15 | 在线重规划 ≤2 s | real/sim | missing | 无统一事件—轨迹时间戳 | 留空并给测量定义 |
| C16 | 总功耗 ≤30 W | real | missing | 无板级采样 | 留空 |
| C17 | 全栈国产化已证明 | system | partial | Khadas/ROS/传感器材料 | 改写为“国产算力适配方向” |
| C18 | Swarm-LIO2 论文提供分布式 LIO 背景 | literature | partial | `state/khadas_cleanup_20260904/evidence/archives/swarm_lio2.tar` | 待 `verify-citations` |
| C19 | frontier/分配/容错文献综述已完整 | literature | missing | 无本地 BibTeX/检索记录 | 保留 `[CITATION_TODO]` |
| C20 | 图表可由真实矩阵和节点 baseline 生成 | artifact | partial | `figures/*.svg`；结果路径 | 图注绑定数据源后使用 |

## 审计规则

1. `missing` 和 `invalid` 不得通过润色变为成功结论。
2. 任何数字进入正文前，必须附场景、层级、n、来源和统计定义。
3. “创新”“首次”“最优”“显著”需要独立文献或对照证据；否则缩小为系统实现/阶段性观察。
4. 本表可以保留工程排障证据，但正文不复制日常调试细节。
