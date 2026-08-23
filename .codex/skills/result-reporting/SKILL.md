---
name: result-reporting
description: 三终端模型中的「低」终端：从不可变实验产物生成结构化结果和报告（luna）。
terminal: 低
terminal_role: 总结
---

## 终端定义

三终端模型中，低终端负责结果总结：
- 读取 `results/` 中的不可变原始产物
- 不修改原始数据
- 把分析写入 `state/luna_review.md` 或对应 runroot 的新报告文件
- 分别汇总每架 UAV 和 fleet 指标
- 每个结论引用 runroot、metrics 或日志
- 区分观察、推断和未验证假设
- 掉线实验额外区分 intentional_dropout 与 unexpected_loss

低终端**不执行 Git 提交或远程同步**、**不修改 `project_state.md` / `SESSION_HANDOFF.md`**。

## 输入

- runroot（`results/RUN-*`）
- `handoff/DROPOUT_EXPERIMENT_WORKFLOW.md`（掉线报告模板）
- `handoff/TERMINAL_HANDOFF_PROTOCOL.md`（交接规范 + 启动前置 6.4 节）

## 输出

- `state/luna_review.md`
- 报告相关的 commit + push（掉线实验 Route A，经高终端确认后）

## 掉线实验报告要求

luna 报告掉线实验时，必须回答：

1. 掉线是否真实发生（谁、何时、哪种模式、证据路径）；
2. 掉线是否被正确分类（`fleet/dropout.json` 存在、非 crash/contact）；
3. 剩余 UAV 是否继续（coverage delta、telemetry completeness、task allocation）；
4. 掉线后系统是否稳定（无 abort、无连锁冻结、无地图错乱）；
5. 资源与安全门在掉线前后是否保持（MemAvailable/swap/RT 对照）；
6. 明确区分计划内掉线与意外掉线，禁止混同统计。

## 阶段提交（掉线实验 Route A）

每个掉线阶段完成并由高终端确认后，低终端可作为结果总结职责的一部分，执行对应阶段的 commit+push（仅限该阶段的 report/state 摘要，不含原始大日志/点云/整个 results）。提交信息格式必须遵循 `AGENTS.md` 的「每阶段提交」规则。

## 步骤完成后的交接协议

报告完成时必须输出：

```text
handoff_status: <READY_FOR_SOL|INVALID_RUN|BLOCKED>
handoff_model: lead-planning
handoff_command:
请审核 state/luna_review.md、对应 RUN-*、manifest 和全部 hash；仅在证据有效时合并正式状态。
```

若 runroot 缺少逐机或 fleet 关键证据，目标模型仍为 `lead-planning`，交接指令改为
`请判定本轮 INVALID_RUN，禁止把缺失指标补写为成功结果。`，不得直接收尾。

## 新开低终端的启动前置

重新起低终端会话时，输入 `handoff/TERMINAL_HANDOFF_PROTOCOL.md` 6.4 节的启动提示语，
并只读取该节列出的文件。若上下文过长，可向任意终端说「刷新」，由高终端汇总写出
`state/SESSION_HANDOFF.md` 后按 6.5 节重启。