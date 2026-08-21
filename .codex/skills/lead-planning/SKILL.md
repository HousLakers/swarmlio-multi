---
name: lead-planning
description: 为多机实验生成受边界约束的任务包和实验决策。
---

读取 `AGENTS.md`、`state/current_summary.md` 和指定证据；不得默认读取全部历史。输出目标、输入、允许写入、成功标准和禁止动作。未经批准不得启动实验。

每轮实验结束后，sol 才能执行一次正式状态合并：先审查 luna 的结果总结，再一次性更新 `project_state.md` 和 `state/SESSION_HANDOFF.md`。实验期间和 luna 阶段不得更新这两个正式文件。sol 是唯一允许维护正式项目状态的角色。

## sol 收尾与 GitHub 同步

本轮结果审核通过后，sol 按以下顺序收尾：

1. 检查 `git status`、当前分支、实验开始时的源码 hash 和公共环境基线版本；
2. 审核 terra diff、DeepSeek runroot、luna review 和 manifest；
3. 一次性更新 `project_state.md`、`state/current_summary.md`、`state/SESSION_HANDOFF.md`；
4. 只把本轮需要追溯的源码/脚本、manifest、metrics 摘要、gate、报告和状态文件加入 Git；
5. 生成一个收尾 commit，例如 `Finalize RUN-...: <decision>`；
6. 记录 commit hash、分支和远程仓库；经用户允许后 push GitHub。

sol 不应提交 build/devel/install、原始大日志、点云、密钥或未经审核的整个 results 目录。若结果必须存储在 GitHub，应只提交小型摘要和 hash manifest。

## 步骤完成后的交接协议

每次计划/审核结束时，必须在输出末尾给出以下三项：

```text
handoff_status: <READY|BLOCKED|REJECTED>
handoff_model: <下一阶段 skill/角色>
handoff_command:
<可直接交给下一阶段的完整指令>
```

分支规则：

- 需要改源码：`handoff_model: low-level-implementation`，交接
  `严格执行 state/sol_plan.md，只修改任务包文件；完成静态验证；不要启动实验。`；
- 静态接入已合格且只允许一次 preflight：`handoff_model: experiment-execution`，交接
  `只执行 manifest 白名单的 preflight；先验证 approval package、source hash 和参数快照；不得执行 smoke。`；
- preflight 已完成但尚未审核：回到 `lead-planning`，不得直接进入 smoke；
- 任一证据缺失：`handoff_status: BLOCKED`，不得生成实验执行交接。
