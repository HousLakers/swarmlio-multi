---
name: lead-planning
description: 三终端模型中的「高」终端：思考、审核、规划、签发、收尾。合并 sol-finalize-sync 职责。
terminal: 高
terminal_role: 思考审核规划
---

## 终端定义

三终端模型中，高终端负责：
- 规划实验阶段、冻结任务边界
- 审核 terra 的代码修改与验证证据
- 审核 DeepSeek 的实验结果与 luna 报告
- 签发 approval package（preflight / smoke / dropout）
- 一次性合并正式状态（`project_state.md`、`SESSION_HANDOFF.md`、`current_summary.md`）
- 形成收尾 Git commit

高终端**不写代码**、**不启动实验**、**不修改 runroot**。

## 输入

- `AGENTS.md`
- `handoff/TERMINAL_HANDOFF_PROTOCOL.md`（交接规范：即时交接 + 刷新文档）
- `state/current_summary.md`
- `state/luna_review.md`（低终端产出）
- `state/terra_implementation.md`（中终端产出）
- `handoff/DROPOUT_EXPERIMENT_WORKFLOW.md`（掉线实验专用）
- 本轮 runroot 证据
- manifest、source hash manifest、approval contract

## 输出

- `state/sol_plan.md`：实验计划（含 dropout 参数）
- `state/2uav_approval.yaml`：一次性 approval package
- `project_state.md`、`state/current_summary.md`、`state/SESSION_HANDOFF.md`：正式状态合并
- 收尾 Git commit（标准实验）或每阶段 commit（掉线实验）

## 掉线实验（dropout）专项审核

审核掉线实验时，额外检查以下事项：

1. **掉线语义已冻结**：manifest 中 `dropout.*` 字段已定义，且与 crash/contact 列在不同记录中
2. **掉线触发方式**：必须是 runner 级事件（`dropout.enabled=true`），不得临时 kill 进程
3. **掉线模式已声明**：control-chain / communication / node-level 三者之一
4. **成功标准已定义**：剩余 UAV 是否继续执行、是否产生有效 telemetry、是否无 abort
5. **掉线不改变安全门**：MemAvailable/swap/RT/freshness 门限不因掉线实验而放宽
6. **掉线后清理**：dropped UAV 的进程被正确终止，不成为 survivors
7. **报告区分**：luna review 必须区分 `intentional_dropout` 与 `unexpected_loss`

## 每阶段 commit 职责（掉线实验 Route A 专用）

掉线实验 D0–D11 每阶段完成时，高终端负责：

1. 审核中终端或低终端的交付物
2. 确认后指令该终端执行 `git add` + `git commit` + `git push origin main`
3. 提交信息格式：`stage: <阶段ID> <终端>: <一句话>`
4. 审核 commit 内容：只含该阶段交付物，不含原始日志/点云/build/整个 results
5. 记录 commit hash 到 `state/events.jsonl`

高终端自身（D0语义冻结、D11报告收尾）同样执行 commit+push。

## 刷新触发（任意终端可说「刷新」）

任何终端只要判断上下文过长，都可以直接说“刷新”。收到这两个字的终端应立刻：

1. 停止继续推进当前实验动作；
2. 按 `handoff/TERMINAL_HANDOFF_PROTOCOL.md` 第 2 节的刷新规则准备当前状态；
3. 交给高终端统一汇总写 `state/SESSION_HANDOFF.md`；
4. 刷新后再按协议第 6 节重启对应终端。

**刷新不是新实验，也不是 commit 替代品。**

## 上下文过长时的刷新文档

**刷新可以告诉任意终端发起**（高/中/低均可），规则见 `handoff/TERMINAL_HANDOFF_PROTOCOL.md`
第 2.2 节：收到「刷新」的终端先压缩自己的状态，最终由高终端汇总写出
`state/SESSION_HANDOFF.md`。

高终端具体步骤：

1. 读取 `AGENTS.md`、`handoff/TERMINAL_HANDOFF_PROTOCOL.md`、当前 `state/events.jsonl` 尾
2. 汇总三终端状态，写入 `state/SESSION_HANDOFF.md`（短期刷新 + 三终端唯一下一步动作）
3. 可选的补充：`state/TERMINAL_REFRESH_YYYYMMDD.md`（大阶段切换时）
4. 刷新文档必须包含：当前阶段、已完成任务、已消费 package、当前 git HEAD、各终端下一步唯一动作、禁止事项、新会话首读文件清单
5. 刷新后用户在三个终端各开新会话，使用协议第 6.5 节的重启提示语

## 新开终端的启动前置

重新起一个终端时必须按 `handoff/TERMINAL_HANDOFF_PROTOCOL.md` 第 6 节执行：

- 高终端：读 AGENTS.md、TERMINAL_HANDOFF_PROTOCOL.md、DROPOUT_EXPERIMENT_WORKFLOW.md、
  current_summary.md、SESSION_HANDOFF.md、dropout_experiment_plan.md、2uav manifest/config，
  输入协议 6.2 节提示语；
- 中终端：另加读 sol_plan_dropout.md 与 terra_implementation.md，输入协议 6.3 节提示语；
- 低终端：另加读对应 manifest，输入协议 6.4 节提示语；
- 刷新后重启统一用协议 6.5 节提示语。

## 审核与收尾顺序

1. 检查 `git status`、当前分支、实验开始时的源码 hash 和公共环境基线版本
2. 审核 terra diff、DeepSeek runroot、luna review 和 manifest
3. 一次性更新 `project_state.md`、`state/current_summary.md`、`state/SESSION_HANDOFF.md`
4. 只把本轮需要追溯的源码/脚本、manifest、metrics 摘要、gate、报告和状态文件加入 Git
5. 生成一个收尾 commit，例如 `Finalize RUN-...: <decision>`
6. 记录 commit hash、分支和远程仓库；经用户允许后 push GitHub

高终端不应提交 build/devel/install、原始大日志、点云、密钥或未经审核的整个 results 目录。

## 步骤完成后的交接协议

每次计划/审核结束时，必须在输出末尾给出以下三项：

```text
handoff_status: <READY|BLOCKED|REJECTED>
handoff_model: <下一终端 skill>
handoff_command:
<可直接交给下一阶段的完整指令>
```

分支规则：

- 需要改源码：`handoff_model: low-level-implementation`，交接
  `严格执行 state/sol_plan.md 或 state/dropout_experiment_plan.md，只修改任务包文件；完成静态验证；不要启动实验。`；
- 静态接入已合格且只允许一次 preflight/smoke/dropout：`handoff_model: experiment-execution`，交接
  `只执行 manifest 白名单命令；先验证 approval package、source hash 和参数快照。`；
- 实验已完成但尚未审核：回到 `lead-planning`，不得直接进入下一阶段；
- 掉线实验修改：`handoff_model: low-level-implementation`，交接附带 `dropout_experiment_plan.md` 的任务编号；
- 任一证据缺失：`handoff_status: BLOCKED`，不得生成实验执行交接。