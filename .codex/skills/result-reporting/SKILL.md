---
name: result-reporting
description: 从不可变实验产物生成结构化结果和报告。
---

读取 `results/` 中的不可变原始产物；不修改原始数据。允许把本轮分析写入 `state/luna_review.md` 或对应 runroot 的新报告文件。分别汇总每架 UAV 和 fleet 指标；每个结论引用 runroot、metrics 或日志；区分观察、推断和未验证假设。

luna 只写本轮的 `state/luna_review.md` 或对应 runroot 的报告，不得修改 `project_state.md` 或 `state/SESSION_HANDOFF.md`。luna 完成后交给 sol 审核，由 sol 在本轮结束时一次性维护正式状态。

luna 不执行 Git 提交或远程同步；报告必须引用本轮 runroot、源码 hash、公共环境基线版本和 manifest，供 sol 形成最终收尾提交。

## 步骤完成后的交接协议

报告完成时必须输出：

```text
handoff_status: <READY_FOR_SOL|INVALID_RUN|BLOCKED>
handoff_model: sol-finalize-sync
handoff_command:
请审核 state/luna_review.md、对应 RUN-*、manifest 和全部 hash；仅在证据有效时合并正式状态并创建唯一收尾 commit。
```

若 runroot 缺少逐机或 fleet 关键证据，目标模型仍为 `lead-planning`，交接指令改为
`请判定本轮 INVALID_RUN，禁止把缺失指标补写为成功结果。`，不得直接收尾。
