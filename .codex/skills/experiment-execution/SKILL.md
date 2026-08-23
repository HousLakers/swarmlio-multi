---
name: experiment-execution
description: 三终端模型中的「低」终端：执行已批准的 preflight / smoke / dropout 实验并保存 runroot。
terminal: 低
terminal_role: 执行
---

## 终端定义

三终端模型中，低终端负责：
- 只执行 manifest 白名单命令（preflight / launch / monitor / stop / collect / dropout）
- 先验证 approval package、源码 hash、参数快照和 topic/namespace
- 保存不可覆盖的 runroot 和 `execution_result.md`
- 掉线实验时按白名单事件触发，不临时 kill 进程
- 遇到硬门按 manifest 处理（fail-closed）

低终端**不修改源码、参数或配置**、**不更新正式状态文件**、**不执行 git commit/push**。

## 输入

- approval package（一次性）
- manifest（白名单命令）
- `handoff/DROPOUT_EXPERIMENT_WORKFLOW.md`（掉线语义）
- `handoff/TERMINAL_HANDOFF_PROTOCOL.md`（交接规范 + 启动前置 6.4 节）

## 输出

- 本轮 runroot（`results/RUN-*`）
- `execution_result.md`
- `state/events.jsonl` 追加
- 每阶段 commit + push（掉线实验 Route A，runroot 摘要）

## 每阶段 commit 职责（掉线实验 Route A 专用）

完成一个实验阶段（如 D3、D8、D9、D10）后：

1. 等待高终端审核 runroot 证据；
2. 高终端确认后，执行 commit + push：
   ```bash
   git add <本阶段交付文件，例如 runroot 的 metrics.json/execution_result.md/state/luna_review.md>
   git commit -m "stage: D3 2uav dropout rehearsal (low)"
   git push origin main
   ```
3. 提交信息格式：`stage: <阶段ID> <终端>: <一句话>`；
4. 只提交摘要/报告/state 文档；**不提交**原始大日志、点云、整个 results 目录；
5. 记录 commit hash 到 runroot 摘要或 `state/events.jsonl`；
6. 失败阶段：先 `git commit -m "stage: Dx FAIL <原因> (low)"`，再提交修复版。

标准 preflight/smoke 实验（非掉线）不执行每阶段 commit，仍由 sol 一轮一收尾。

## 掉线实验执行要求

1. 启动前确认 manifest 的 `dropout.enabled`、`dropout.vehicle`、`dropout.mode`、
   `dropout.trigger_sim_s` 已冻结且有批准 package；
2. 掉线触发是 runner 白名单事件，不是人工 kill；触发后写入 `fleet/dropout.json`；
3. 掉线后观察剩余 UAV 是否继续产生 telemetry / coverage / task allocation；
4. 若掉线触发后任何剩余 UAV crash / contact / process death，保持 abort 行为并按硬门处理；
5. runroot 必须包含 dropout 前后的 metrics 对照（如 surviving UAV coverage delta）。

## 步骤完成后的交接协议

每次命令结束都必须输出：

```text
handoff_status: <PREFLIGHT_PASS|PREFLIGHT_FAIL|SMOKE_COMPLETE|DROPOUT_COMPLETE|INFRASTRUCTURE_FAIL|BLOCKED>
handoff_model: <下一终端 skill>
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
- dropout 完成：交给 `result-reporting`，指令为
  `只读取该 RUN-*，按 DROPOUT_EXPERIMENT_WORKFLOW 生成 luna_review，区分 intentional_dropout 与 unexpected_loss。`；
- 任何 hash、namespace、参数、日志或 abort 硬门失败：`handoff_status: BLOCKED`，
  交给 `lead-planning`，不得继续 launch。

## 新开低终端的启动前置

重新起低终端会话时，输入 `handoff/TERMINAL_HANDOFF_PROTOCOL.md` 6.4 节的启动提示语，
并只读取该节列出的文件。若上下文过长，可向任意终端说「刷新」，由高终端汇总写出
`state/SESSION_HANDOFF.md` 后按 6.5 节重启。