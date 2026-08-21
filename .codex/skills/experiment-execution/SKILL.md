---
name: experiment-execution
description: 执行已批准的多机 preflight 和 smoke 实验。
---

先检查 manifest、源码 hash、参数快照和 topic/namespace；只执行白名单脚本；每架 UAV 单独记录状态；原始 runroot 不覆盖；遇到硬门按 manifest 处理。

实验进行期间不得更新 `project_state.md` 或 `state/SESSION_HANDOFF.md`。实验结束后只写入本轮 runroot、`execution_result.md` 和必要的事件记录，等待 luna/sol 汇总。

实验期间不得执行 `git commit`、`git push`、分支切换或远程同步。启动前记录当前源码状态、公共环境基线版本和完整 hash manifest；结束后把这些信息写入 runroot，交给 sol 收尾。

## 步骤完成后的交接协议

每次命令结束都必须输出：

```text
handoff_status: <PREFLIGHT_PASS|PREFLIGHT_FAIL|SMOKE_COMPLETE|INFRASTRUCTURE_FAIL>
handoff_model: <下一阶段 skill/角色>
handoff_command:
<可直接执行或审核的下一步指令>
```

交接规则：

- preflight 通过：交给 `lead-planning`，指令为
  `审核该 RUN-* 的 live_preflight、最终 metrics、abort 和逐机证据；未审核前不得 launch。`；
- preflight 因脚本/环境失败：交给 `lead-planning`，指令为
  `读取 execution_result.md 和日志，判断是否需要新 approval package；不得复用已消费 package。`；
- smoke 完成：交给 `result-reporting`，指令为
  `只读取该 RUN-*，生成 state/luna_review.md；不改源码或正式状态。`；
- 任何 hash、namespace、参数、日志或 abort 硬门失败：`handoff_status: BLOCKED`，
  交给 `lead-planning`，不得继续 launch。
