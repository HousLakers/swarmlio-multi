# SwarmLIO Multi-UAV Agent Workspace

多机调试编排层：共享工作树、任务包、状态摘要、事件账本和受限监控接口。
不复制或修改 `swarmlio-single` 源码。

## 当前状态

P0 阶段已完成：**负载均衡矩阵 21/21 done（18 组矩阵 + C1 最终验证 3 runs）**，
选定 C1 最佳配置 **`MINMAX + capacity 0.75`**。结果汇总与图片见
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

第一步：读取 `state/current_summary.md` 和 `state/SESSION_HANDOFF.md`。
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
