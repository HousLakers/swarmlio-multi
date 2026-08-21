---
name: sol-finalize-sync
description: 在单轮实验结束后审核结果，合并状态，并形成唯一 Git 收尾提交。
---

仅在 DeepSeek 完成 runroot、luna 完成 `state/luna_review.md` 后执行。

读取：`AGENTS.md`、`state/sol_plan.md`、`state/terra_implementation.md`、`state/luna_review.md`、本轮 runroot、manifest、源码/环境 hash。

执行顺序：

1. 审核实验有效性和 luna 结论；
2. 决定 terra 修改是否保留；
3. 更新 `project_state.md`、`state/current_summary.md`、`state/SESSION_HANDOFF.md`；
4. 只选择本轮需要追溯的源码、脚本、manifest、metrics 摘要、gate、报告和状态文件；
5. 创建一个收尾 commit；
6. 记录 commit hash、分支、公共环境版本和远程仓库；
7. 只有获得用户允许后才 push GitHub。

禁止：实验中途提交、覆盖历史、提交密钥和大体积原始结果、把单机结果写成 fleet-level 结论、未经审核把失败代码提交为默认版本。

建议 commit 格式：

```text
Finalize RUN-YYYYMMDD-NNN: <pass|fail|diagnosis>
```

## 步骤完成后的交接协议

收尾完成时必须输出：

```text
handoff_status: <FINALIZED|BLOCKED>
handoff_model: lead-planning
handoff_command:
下一轮从 AGENTS.md、state/current_summary.md 和最新 SESSION_HANDOFF 重新规划；不得复用本轮 approval package 或 runroot。
```

若 luna、runroot、hash 或用户 push 授权缺失，保持 `handoff_status: BLOCKED`，目标模型仍为
`lead-planning`，只交接缺口清单，不得创建或推送收尾 commit。
