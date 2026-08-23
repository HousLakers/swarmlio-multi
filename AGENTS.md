# SwarmLIO Multi-UAV 工作规则

- lead：制定计划、批准实验、审查结论。
- code：修改源码和脚本；必须提交 diff 和验证证据。
- experiment：只能运行 manifest 白名单命令；不得改源码或参数。
- report：只读 `results/`，不得修改原始实验数据。
- monitor：只能读取状态并返回白名单动作建议。

## 三终端模型（2026-08-23 起）

本项目按三个并行终端运行，每个终端对应固定 skills 集合：

| 终端 | 职责 | skills | 唯一写入 |
|---|---|---|---|
| 高 | 思考、审核、规划、批准、收尾 | `lead-planning`、`sol-finalize-sync` | `project_state.md`、`SESSION_HANDOFF.md`、approval package、收尾 commit |
| 中 | 写代码、留验证证据 | `low-level-implementation` | `state/terra_implementation.md`、工作树 diff |
| 低 | 执行白名单命令、保存 runroot、总结结果 | `experiment-execution`、`result-reporting` | runroot、`execution_result.md`、`state/luna_review.md` |

交接链：高 →（计划）→ 中 →（证据）→ 高 →（批准）→ 低 →（runroot）→ 高 →（审核）→ 收尾。
实验中途高终端不得写代码，中终端不得启动实验，低终端不得改源码。

## 每轮实验的状态更新节奏

一轮实验期间不得更新 `project_state.md` 或 `state/SESSION_HANDOFF.md`。实验结束后，DeepSeek 只保存原始 runroot 和执行结果；luna 只生成本轮结果总结；sol 审查 luna 后，才一次性更新 `project_state.md` 和 `state/SESSION_HANDOFF.md`。sol 是正式项目状态的唯一维护者。

硬约束：单机结果只能作为节点级 baseline；2-UAV preflight 未通过不得长跑；同一时间最多一个代理写源码；每架 UAV 分别记录 completion、freeze、crash、contact、coverage、telemetry；原始 runroot 只追加；模型不得执行任意 shell 命令；未经 lead 批准不得扩大实验范围。

## 掉线（dropout）实验专项约束

掉线实验是故障注入实验，不是 crash 或 contact 测试。必须先冻结掉线语义（参考
`handoff/DROPOUT_EXPERIMENT_WORKFLOW.md`），任何计划内掉线都必须：

- 由 runner 白名单事件触发（不得临时 kill）；
- 在 manifest 中显式声明 `dropout.*` 字段；
- 与 crash/contact/telemetry_missing/teardown 分开记录；
- 在报告里区分 intentional dropout 与 unexpected loss；
- 不改变冻结的安全门（MemAvailable/swap/RT/freshness 不因掉线实验放宽）。

## Git 与环境基线规则

- 标准 preflight/smoke 实验：一轮实验期间禁止 commit/push/改历史/切分支；sol 审核 luna 后一次性收尾 commit。
- 掉线实验（Route A）：采用**每阶段提交**规则（见下节）。
- terra 只修改本地工作树并留下 diff；DeepSeek 只执行当前工作树并记录实验开始时的源码 commit/hash（若工作树无 commit，则记录完整 hash manifest）。
- 原始大日志、点云、build/devel/install 和密钥不直接提交 GitHub；只提交可追溯的摘要、manifest、hash 和外部存储引用。
- single 与 multi 必须引用同一个公共环境基线版本；任何环境升级先在公共环境清单中形成版本，再由两边分别验证。
- 推送前必须记录 commit、分支和远程仓库。

## 每阶段提交（2026-08-23 起，掉线实验专用）

掉线实验（Route A，D0–D11）按阶段提交 commit，不是一轮一个收尾 commit。规则：

1. 每个阶段完成后，负责的终端**提交一次 commit** 记录该阶段交付物；
2. 提交信息格式：`stage: <阶段ID> <终端>: <一句话>`，例如
   `stage: D1 dropout event in runner (mid)`、`stage: D3 2uav dropout rehearsal (low)`、
   `stage: D0 dropout semantics frozen (high)`；
3. 每次提交后**必须 push 到 origin main**（`git push origin main`）；
4. 只提交该阶段产生的文件（源码/脚本/config/manifest/state 文档/runroot 摘要）；
   **不提交**原始日志、点云、build/devel/install、密钥、整个 results 目录；
5. 不 rewrite history、不 force push、不 amend 已推送的 commit；
6. 失败或需要重做的阶段，先提交 `stage: Dx FAIL ...` 记录失败原因，再提交修复版；
7. 高终端在 stage commit 前审核交付物，确认后由该终端执行 commit+push；
8. 本规则仅适用掉线实验阶段；标准 preflight/smoke 仍按一轮一收尾。

## 用户意见优先级

用户在当前任务中明确提出的意见优先于 Skill 的默认流程和输出格式。若用户意见扩大实验范围、改变安全门、覆盖原始数据或与项目硬约束冲突，必须先由 lead 明确记录影响并请求确认；不能静默执行。
