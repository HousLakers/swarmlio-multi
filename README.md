# SwarmLIO Multi-UAV Agent Workspace

多机调试编排层：共享工作树、任务包、状态摘要、事件账本和受限监控接口。
不复制或修改 `swarmlio-single` 源码。

## 论文材料分支入口

当前分支 `paper-materials-20260909` 专门用于整理参赛论文、图表、引用、证据台账和 Word 稿。论文材料入口位于 [`docs/20260907_competition_submission/`](docs/20260907_competition_submission/)，队友接手时先阅读[团队论文交接说明](docs/20260907_competition_submission/TEAM_HANDOFF_论文进一步修改_20260909.md)，再阅读[论文材料 README](docs/20260907_competition_submission/README.md)。

论文主稿和可直接打开的 Word 文件分别是：

- [Markdown 正文 v2](docs/20260907_competition_submission/draft/paper_draft_v2.md)；
- [Word 排版稿](docs/20260907_competition_submission/draft/paper_draft_v2.docx)；
- [v2 交付索引](docs/20260907_competition_submission/draft/REWRITE_V2_INDEX.md)；
- [论断与证据台账](docs/20260907_competition_submission/draft/claim_ledger_v2.md)；
- [引用计划](docs/20260907_competition_submission/draft/citation_plan_v2.md)；
- [QA 与 Paper Health 报告](docs/20260907_competition_submission/draft/qa_report_v2.md)。

论文当前状态是 `READY_FOR_REVIEW`，正文仍为 `DRAFT_NOT_SUBMITTABLE`。三机 GT 注册仿真、报告级任务层丢包和单节点实机 baseline 已分层整理；实机 ATE、统一定位/建图频率、在线重规划上界、计算平台功耗、室内六/十机、AirSim 闭环、三机实机成功和完整国产化证明仍未补齐。论文缺失结果必须保留五字段占位符，不能用工程配置、日志片段或不同场景结果替代。

正文唯一编辑源是 Markdown。修改正文后运行 `docs/20260907_competition_submission/draft/build_paper_docx.py` 重新生成 Word；不要把 Word 作为唯一版本。图件、数据和图位说明见 [`figures/v2/README.md`](docs/20260907_competition_submission/figures/v2/README.md)。

论文材料分支不提交完整 `results/`、原始点云、大型运行日志、源码构建目录、远端部署包或密钥。论文中的 run ID 和来源路径用于追溯，不能据此推断实验成功。

## 工程主线状态

工程主线曾记录 P0 负载均衡矩阵收尾：**21/21 done（18 组矩阵 + C1 历史验证 3 runs）**。
该段是工程历史背景；论文分支已对 C1 的不同运行时长和证据完整性做了单独审查，不能直接把 C1 写成论文中的“全矩阵最优”。结果汇总与图片见
[REPORT_P0_MATRIX_CLOSEOUT.md](experiments/REPORT_P0_MATRIX_CLOSEOUT.md) 与
[P0_LOAD_BALANCING_CLOSEOUT.md](experiments/P0_LOAD_BALANCING_CLOSEOUT.md)。

## 冻结输入

- 公共环境：`racer-platform@57c1f34`（LE8E 运行时基座；当前公共环境仓库 HEAD 为 `4121e58`，在基座上仅新增 50x50 baseline/world）
- 单机 overlay：`swarmlio-single@82366bf` + `range20m_omnidirectional_load_balancing_v1`
- 公共环境 world：`2uav_outdoor_50x50_v1.world`（sha256 `28a306b6…`）
- 多机配置：`config/3uav_static.yaml`（`mtsp_objective: MINMAX`、`capacity_factor: 0.75`）

环境搭建、三仓库 commit 对应和校验见 [SETUP_FROM_BASE.md](SETUP_FROM_BASE.md)
（一步到位：clone + checkout 当前 commit + 增量构建，无需先走历史版本）。

## 进入工作区

第一步：如果处理论文，先读取
`docs/20260907_competition_submission/TEAM_HANDOFF_论文进一步修改_20260909.md`、
`docs/20260907_competition_submission/draft/REWRITE_V2_INDEX.md`、
`state/current_summary.md` 和 `state/SESSION_HANDOFF.md`。
P0 矩阵实验已结束，进入报告与收尾阶段；后续计划见
[PLAN_COMPETITION_2026.md](experiments/PLAN_COMPETITION_2026.md)。
如需复跑或继续实验，遵循 `AGENTS.md` 的 manifest、审批、执行与不可变 runroot
规则——实验记录以 `results/` 中不可覆盖的原始 runroot 为准（runroot 数据本地
保留、不入库，git 中仅保留报告引用的图）。

## 文档入口

- [SETUP_FROM_BASE.md](SETUP_FROM_BASE.md)：搭建指南（一步到位 + 演进背景）；
- [PLATFORM_ENVIRONMENT.md](PLATFORM_ENVIRONMENT.md)：公共环境同步合同；
- [handoff/SINGLE_TO_MULTI_TRANSFER_20260820.md](handoff/SINGLE_TO_MULTI_TRANSFER_20260820.md)：单机→多机转移门禁与基线（新多机会话首要入口）；
- [experiments/REPORT_P0_MATRIX_CLOSEOUT.md](experiments/REPORT_P0_MATRIX_CLOSEOUT.md)：P0 矩阵收尾总结（21/21 + C1）；
- [experiments/P0_LOAD_BALANCING_CLOSEOUT.md](experiments/P0_LOAD_BALANCING_CLOSEOUT.md)：P0 负载均衡收尾（含图）；
- [experiments/PLAN_COMPETITION_2026.md](experiments/PLAN_COMPETITION_2026.md)：后续计划；
- [RUNBOOK.md](RUNBOOK.md)：实验运行与角色流程；
- [state/current_summary.md](state/current_summary.md) / [state/SESSION_HANDOFF.md](state/SESSION_HANDOFF.md)：当前短状态与会话交接。

监控接口（不算实验批准，仅查看）：

```bash
python3 scripts/create_task.py two-uav-smoke
python3 scripts/monitor_experiment.py --once
```
