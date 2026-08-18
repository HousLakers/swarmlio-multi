# SwarmLIO Multi-UAV 工作规则

- lead：制定计划、批准实验、审查结论。
- code：修改源码和脚本；必须提交 diff 和验证证据。
- experiment：只能运行 manifest 白名单命令；不得改源码或参数。
- report：只读 `results/`，不得修改原始实验数据。
- monitor：只能读取状态并返回白名单动作建议。

## 每轮实验的状态更新节奏

一轮实验期间不得更新 `project_state.md` 或 `state/SESSION_HANDOFF.md`。实验结束后，DeepSeek 只保存原始 runroot 和执行结果；luna 只生成本轮结果总结；sol 审查 luna 后，才一次性更新 `project_state.md` 和 `state/SESSION_HANDOFF.md`。sol 是正式项目状态的唯一维护者。

硬约束：单机结果只能作为节点级 baseline；2-UAV preflight 未通过不得长跑；同一时间最多一个代理写源码；每架 UAV 分别记录 completion、freeze、crash、contact、coverage、telemetry；原始 runroot 只追加；模型不得执行任意 shell 命令；未经 lead 批准不得扩大实验范围。

## Git 与环境基线规则

- 每轮实验中途禁止 `git commit`、`git push`、修改远程历史或切换分支。
- terra 只修改本地工作树并留下 diff；DeepSeek 只执行当前工作树并记录实验开始时的源码 commit/hash（若工作树无 commit，则记录完整 hash manifest）。
- 本轮实验结束后，只有 sol 在审核 luna 结果后，才能一次性将本轮需要的源码、脚本、manifest、指标摘要、报告、`project_state.md` 和 `state/SESSION_HANDOFF.md` 加入一个收尾 commit。
- 原始大日志、点云、build/devel/install 和密钥不直接提交 GitHub；只提交可追溯的摘要、manifest、hash 和外部存储引用。
- single 与 multi 必须引用同一个公共环境基线版本；任何环境升级先在公共环境清单中形成版本，再由两边分别验证。
- sol 收尾后才允许把收尾 commit 推送 GitHub；推送前必须记录 commit、分支和远程仓库。

## 用户意见优先级

用户在当前任务中明确提出的意见优先于 Skill 的默认流程和输出格式。若用户意见扩大实验范围、改变安全门、覆盖原始数据或与项目硬约束冲突，必须先由 lead 明确记录影响并请求确认；不能静默执行。
