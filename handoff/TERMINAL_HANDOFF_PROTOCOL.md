# 三终端交接协议

本文件定义两类交接文档：

1. **终端之间的即时交接**
2. **上下文过长时的三终端刷新文档**

目标是让高/中/低三个终端在长周期实验中保持一致的语义、权限和下一步动作，避免上下文漂移。

---

## 1. 终端之间的即时交接

### 1.1 定义

即时交接是每次角色切换时，终端直接输出给下一终端的短消息，不落盘或只做最小落盘。

例如：

- 高终端 → 中终端：计划与任务包
- 中终端 → 高终端：实现证据与风险
- 高终端 → 低终端：批准包与执行指令
- 低终端 → 高终端：结果审核指令

### 1.2 必须包含的字段

即时交接必须明确：

- 当前阶段 ID
- 终端来源与目标
- 本轮目标
- 允许写入范围
- 不允许动作
- 下一步唯一动作
- 关键证据路径
- 是否允许 commit / push

### 1.3 推荐格式

```text
handoff_status: <READY|BLOCKED|REJECTED|PREFLIGHT_PASS|PREFLIGHT_FAIL|SMOKE_COMPLETE|DROPOUT_COMPLETE|READY_FOR_SOL|READY_FOR_REVIEW|INVALID_RUN>
handoff_model: <下一终端 skill>
handoff_command:
<可直接执行的完整指令>
```

### 1.4 终端输出规则

- 高终端输出的即时交接必须能直接交给中终端或低终端使用；
- 中终端输出的即时交接必须带有 diff、验证和残余风险；
- 低终端输出的即时交接必须带有 runroot、结果和下一步审查指令；
- 掉线实验即时交接必须显式标记 `dropout` 语义；
- 即时交接不替代正式状态合并。

---

## 2. 上下文过长时的三终端刷新文档

### 2.1 定义

当任一终端上下文过长、历史太多、需要刷新三终端共同认知时，写一份**刷新文档**。刷新文档不是实验交接，而是“把三终端当前状态重新压缩到一个新的起点”。

### 2.2 谁可以触发刷新

**任何终端都可以被触发刷新。** 你只需要在任意终端说“刷新”或“开始新会话前刷新”，该终端立即进入刷新流程：

- 你告诉**高终端**“刷新”：高终端直接汇总生成 `state/SESSION_HANDOFF.md`；
- 你告诉**中终端**“刷新”：中终端先把自己的当前状态（已实现任务、diff、验证证据、残余风险）写入 `state/terra_implementation.md` 或追加一段 `TERMINAL_REFRESH`，然后交接给高终端汇总；
- 你告诉**低终端**“刷新”：低终端先把自己的当前状态（runroot、结果、已消费 package、luna 结论）写入自己的产出文件，然后交接给高终端汇总；
- 最终 `state/SESSION_HANDOFF.md` 由高终端统一写出（符合「sol 是正式状态唯一维护者」规则）。

### 2.3 建议触发条件

建议在以下情况写刷新文档：

- 完成一个较长实验阶段（例如 preflight + smoke + report + 收尾）
- 掉线实验完成一个完整子阶段（例如 D0–D3，或 D5–D10）
- 代码和实验累计改动过多，任何一个终端都容易丢上下文
- 新的 workflow 语义出现，例如从 smoke 转向 dropout、从 2-UAV 转向 3-UAV

### 2.4 刷新文档应该包含什么

刷新文档建议包含：

1. 当前总体目标
2. 当前阶段
3. 已完成事项
4. 当前冻结身份 / manifest / hash
5. 已消费 approval package
6. 最新 runroot / 关键结果
7. 已知问题与风险
8. 三终端各自下一步唯一动作
9. 禁止事项
10. 新会话首读文件清单

### 2.4 刷新文档建议落点

推荐存放在：

- `state/SESSION_HANDOFF.md`：短期、面向新会话的刷新文档
- `state/current_summary.md`：更短的当前摘要
- 必要时额外生成 `state/TERMINAL_REFRESH_YYYYMMDD.md`：用于大阶段切换

### 2.5 刷新文档格式建议

```text
handoff_status: READY_FOR_REFRESH
handoff_model: <lead-planning | low-level-implementation | experiment-execution | result-reporting>
handoff_command:
<刷新后各终端的唯一下一步动作>
```

### 2.6 刷新文档与即时交接的区别

- 即时交接：一句话到一段话，直接交给下一个终端
- 刷新文档：阶段总结，给三个终端同时刷新认知

刷新文档必须包含“当前唯一下一步动作”，否则会重新引入上下文漂移。

---

## 3. 掉线实验的交接要求

掉线实验既需要即时交接，也需要阶段刷新。

### 3.1 掉线实验的即时交接

- 高 → 中：冻结 dropout 语义 / 审核 runner 与 collector 任务包
- 中 → 高：报告 dropout 字段、diff、self-test、风险
- 高 → 低：签发 dropout approval package
- 低 → 高：返回 runroot、dropout.json、luna review

### 3.2 掉线实验的刷新文档

建议在以下点刷新：

- D0 完成后刷新一次
- D3 2-UAV rehearsal 后刷新一次
- D7 3-UAV static 校验后刷新一次
- D10 3-UAV 最终 smoke 后刷新一次

### 3.3 掉线实验的刷新文档必须写明

- 掉线对象
- 掉线模式
- 掉线触发时间
- intentional_dropout 的判定方式
- 剩余 UAV 是否继续
- 是否允许下一阶段

---

## 4. 不能省略的 commit 规则

你要求每阶段提交 GitHub，这里把规则写死：

1. **每阶段都要 commit**：D0–D11 每完成一阶段至少一个 commit；
2. **每阶段都要 push**：`git push origin main`；
3. **commit 内容只含该阶段交付物**；
4. **不能跳过 commit 直接进入下一阶段**；
5. **不能把刷新文档当成 commit 替代品**；
6. **高终端审核后才允许 commit / push**；
7. **掉线实验阶段允许更频繁 commit，但每次必须对应明确 stage**。

### 推荐 commit 命名

- `stage: D0 dropout semantics frozen (high)`
- `stage: D1 runner dropout event (mid)`
- `stage: D2 collector dropout classification (mid)`
- `stage: D3 2uav dropout rehearsal (low)`
- `stage: D5 3uav parameterization (mid)`
- `stage: D9 3uav control-chain dropout smoke (low)`
- `stage: D11 dropout report and closeout (high)`

---

## 5. 与现有 workflow 的关系

本文件不替代 `AGENTS.md`，只补充两类交接：

- 即时交接：终端之间直接输出
- 刷新文档：三终端统一重置上下文

如果与现有 workflow 冲突，优先级顺序为：

1. 用户当前明确指令
2. `AGENTS.md`
3. 本协议
4. 各阶段 plan / review / report

---

## 6. 新开终端的启动前置（每次重新起终端必须按此执行）

### 6.1 公共前置（三个终端都必读）

无论开哪个终端，新会话第一条消息之前，先确保以下文件存在且已知：

- `AGENTS.md`
- `handoff/TERMINAL_HANDOFF_PROTOCOL.md`
- `state/current_summary.md`
- `state/SESSION_HANDOFF.md`
- `state/dropout_experiment_plan.md`
- `handoff/DROPOUT_EXPERIMENT_WORKFLOW.md`

然后输入对应的终端提示语（见 6.2-6.4）。提示语中必须包含「只读以下文件」清单，
不得默认读取完整历史。

### 6.2 高终端启动提示语

```text
这是三终端模型中的「高」终端（思考审核规划）。请先只读取以下文件：
AGENTS.md、handoff/TERMINAL_HANDOFF_PROTOCOL.md、handoff/DROPOUT_EXPERIMENT_WORKFLOW.md、
state/current_summary.md、state/SESSION_HANDOFF.md、state/dropout_experiment_plan.md、
experiments/manifests/2uav_smoke.yaml 和 config/2uav_static.yaml。
不要读取完整旧对话，不要启动实验。请确认：
1. 当前阶段是掉线实验 Route A 的哪个 Dx；
2. 当前 git HEAD 和最近一次 stage commit；
3. 已消费的 approval package；
4. 唯一下一步动作（签计划、签发 approval、审核证据或收尾）。
输出 handoff_status 和下一步指令。
```

### 6.3 中终端启动提示语

```text
这是三终端模型中的「中」终端（写代码）。请先只读取以下文件：
AGENTS.md、handoff/TERMINAL_HANDOFF_PROTOCOL.md、handoff/DROPOUT_EXPERIMENT_WORKFLOW.md、
state/current_summary.md、state/SESSION_HANDOFF.md、state/dropout_experiment_plan.md、
state/sol_plan.md 和 state/terra_implementation.md。
不要读取完整旧对话，不要启动实验。请确认：
1. 当前待实现的 Dx 任务编号和允许写入的文件清单；
2. 已完成的实现是否已提交 stage commit；
3. 当前 git diff 的未提交部分；
4. 唯一下一步动作（继续实现、补充验证证据或交回高终端审核）。
输出 handoff_status 和下一步指令。
```

### 6.4 低终端启动提示语

```text
这是三终端模型中的「低」终端（执行与总结）。请先只读取以下文件：
AGENTS.md、handoff/TERMINAL_HANDOFF_PROTOCOL.md、handoff/DROPOUT_EXPERIMENT_WORKFLOW.md、
state/current_summary.md、state/SESSION_HANDOFF.md、state/dropout_experiment_plan.md、
experiments/manifests/2uav_smoke.yaml（或 3uav_smoke.yaml）。
不要读取完整旧对话。请确认：
1. 当前是否持有一次性 approval package 及其 hash；
2. 应执行的白名单命令（preflight / launch / monitor / stop / collect）；
3. 最近一个 runroot 的位置和结论；
4. 唯一下一步动作（执行实验、写 execution_result 或写 luna_review）。
输出 handoff_status 和下一步指令。
```

### 6.5 刷新后重启的提示语

刷新文档生成后，三个终端各自新开会话，首条消息统一为：

```text
请先读取 AGENTS.md、handoff/TERMINAL_HANDOFF_PROTOCOL.md、state/current_summary.md、
state/SESSION_HANDOFF.md 和 handoff/DROPOUT_EXPERIMENT_WORKFLOW.md。
我是「高/中/低」终端。只确认当前阶段、最近 stage commit、已消费 package 和唯一下一步动作；
不要启动实验，不要重复已完成的工作。
```

---

## 7. 实操模板

### 高终端给中终端

```text
handoff_status: READY_FOR_REVIEW
handoff_model: low-level-implementation
handoff_command:
严格执行 state/dropout_experiment_plan.md 的 D1 和 D2，只修改 runner / collector；完成静态验证、self-test 和 diff 证据；不要启动实验。
```

### 高终端给低终端

```text
handoff_status: READY_FOR_EXECUTION
handoff_model: experiment-execution
handoff_command:
只执行 manifest 白名单命令；先验证 approval package、source hash 和参数快照；不得执行 smoke 以外的命令。
```

### 低终端给高终端

```text
handoff_status: READY_FOR_SOL
handoff_model: lead-planning
handoff_command:
请审核 state/luna_review.md、对应 RUN-*、manifest 和全部 hash；仅在证据有效时继续下一阶段或合并正式状态。
```

### 三终端刷新文档

```text
handoff_status: READY_FOR_REFRESH
handoff_model: lead-planning
handoff_command:
当前阶段：D3 2-UAV dropout rehearsal 已完成。请刷新三终端上下文，确认下一步唯一动作是 D4 collector 分类强化。
```
