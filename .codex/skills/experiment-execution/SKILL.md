---
name: experiment-execution
description: 执行已批准的多机 preflight 和 smoke 实验。
---

先检查 manifest、源码 hash、参数快照和 topic/namespace；只执行白名单脚本；每架 UAV 单独记录状态；原始 runroot 不覆盖；遇到硬门按 manifest 处理。

实验进行期间不得更新 `project_state.md` 或 `state/SESSION_HANDOFF.md`。实验结束后只写入本轮 runroot、`execution_result.md` 和必要的事件记录，等待 luna/sol 汇总。

实验期间不得执行 `git commit`、`git push`、分支切换或远程同步。启动前记录当前源码状态、公共环境基线版本和完整 hash manifest；结束后把这些信息写入 runroot，交给 sol 收尾。
