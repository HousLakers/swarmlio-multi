---
name: low-level-implementation
description: 修改 ROS/C++/Python/Bash 底层代码并留下可审计验证证据。
---

只处理任务包指定文件；先定位根因，再最小修改；运行静态检查、编译或单元 probe；输出 diff、源码 hash、验证命令和残余风险。

不得修改 `project_state.md` 或 `state/SESSION_HANDOFF.md`。实现结果只写入 `state/terra_implementation.md`，由 sol 在本轮实验结束并审查结果后统一合并。

不得在本轮中途 commit 或 push。保留工作树 diff，记录修改文件、测试命令和源码 hash；最终由 sol 在实验结果审核后决定哪些修改进入收尾 commit。

## 步骤完成后的交接协议

实现结束时必须输出：

```text
handoff_status: <READY_FOR_REVIEW|BLOCKED>
handoff_model: lead-planning
handoff_command:
请审核 state/terra_implementation.md、当前 git diff、manifest、source hash 和验证证据；
不要启动实验；若合格，再决定是否签发一次性 preflight approval package。
```

只有 `handoff_status: READY_FOR_REVIEW` 且 Sol/lead 明确批准后，才允许交接到
`experiment-execution`。编译或 probe 失败时交接模型仍为 `lead-planning`，并附最小返工事项，
不得自行重试实验。
