# SwarmLIO Multi-UAV 全流程运行手册

本文件描述当前项目约定的两终端工作流：

- 终端 A：一个长期 Codex 会话，按阶段使用 luna、sol、terra；
- 终端 B：DeepSeek，负责执行已批准的实验和保存 runroot。

本目录目前是编排骨架，不是已经接好 ROS/Gazebo 的一键运行器。首次实验前必须完成“准备阶段”。

## 0. 当前文件各自的用途

| 文件/目录 | 用途 | 谁维护 |
|---|---|---|
| `AGENTS.md` | 长期规则、角色权限、状态更新节奏 | 项目负责人/主理 Codex |
| `.codex/skills/` | 四个阶段的操作流程 | 项目负责人/主理 Codex |
| `handoff/SINGLE_UAV_BASELINE.md` | 单机向多机的节点级交接边界 | 主理 Codex |
| `handoff/KNOWN_RISKS.md` | 已知风险清单 | 主理 Codex |
| `experiments/manifests/*.yaml` | 实验的唯一配置合同 | sol 审核后冻结 |
| `state/current_summary.md` | 当前短状态，供新会话快速读取 | sol |
| `state/current.json` | 机器可读的当前状态 | runner/sol |
| `state/events.jsonl` | 追加式事件账本 | runner/DeepSeek |
| `state/luna_review.md` | 本轮实验结果总结 | luna |
| `state/sol_plan.md` | 本轮诊断和修改计划 | sol |
| `state/terra_implementation.md` | 代码修改和验证记录 | terra |
| `state/SESSION_HANDOFF.md` | 新 Codex 对话的短交接 | sol |
| `project_state.md` | 正式项目历史和阶段决策 | sol，只有每轮结束时更新 |
| `results/RUN-*` | 不可覆盖的原始实验产物 | DeepSeek/runner |

## 1. 准备阶段：首次实验前只做一次

进入项目：

```bash
cd /home/houslakers/auto_tune_racer/swarmlio_multi
```

完成以下事项：

1. 填写 `handoff/SINGLE_UAV_BASELINE.md` 中的源码 commit、源码路径、地图、GT 模式和实际可复用脚本。
2. 检查 `handoff/KNOWN_RISKS.md`。
3. 将 `experiments/manifests/2uav_smoke.yaml` 的 `launch_command` 替换成已经验证的 2-UAV 启动入口。
4. 把实际的 preflight、启动、监控、停止、指标收集脚本列入白名单。
5. 确认每架 UAV 使用独立 namespace、初始位姿、日志目录和结果目录。
6. 确认 runner 能保存源码 hash、运行时参数、manifest、退出原因和每架 UAV 状态。

当前 manifest 仍含有：

```yaml
launch_command: REPLACE_WITH_APPROVED_2UAV_LAUNCH_COMMAND
```

在替换它之前，不得启动实验。

## 2. Codex 终端 A：打开一个长期会话

```bash
cd /home/houslakers/auto_tune_racer/swarmlio_multi
codex
```

新会话第一句话：

```text
这是多机项目的新工作阶段。请先读取 AGENTS.md、handoff/SINGLE_UAV_BASELINE.md、state/SESSION_HANDOFF.md 和 state/current_summary.md。不要读取完整历史，不要修改源码，不要启动实验。先用不超过20行说明当前状态和准备阶段缺口。
```

用户的本轮意见可以直接追加在 Skill 后面，例如：

```text
$lead-planning

本轮意见：只允许做 2-UAV preflight；不允许修改单机 escape 参数；如果问题只是 namespace，优先改 runner 或 launch。
```

用户本轮明确意见优先于 Skill 的默认流程，但不能静默突破安全门、实验范围或原始数据保护规则。

## 3. sol 阶段：批准一轮实验

在 Codex 中选择 sol，执行：

```text
$lead-planning

请审查当前多机准备状态，并生成本轮实验计划。
只允许使用 experiments/manifests/2uav_smoke.yaml。
如果 preflight、namespace、源码 hash、参数回读或日志隔离没有证据，请不要批准实验。
输出写入 state/sol_plan.md；不要启动实验，不要修改 project_state.md。
```

sol 必须确认：

- 实验 ID、UAV 数量、时长、seed；
- 源码和参数身份；
- preflight 内容；
- 每架 UAV 的独立指标；
- fleet-level 指标；
- abort 条件；
- 允许 DeepSeek 执行的具体命令或 manifest。

批准后由 sol 写入：

```text
state/sol_approval.md
```

没有 `sol_approval.md`，DeepSeek 不得运行。

## 4. terra 阶段：只在 sol 要求时改代码

如果 sol 判断需要修改代码，在同一个 Codex 会话中切换 terra：

```text
$low-level-implementation

严格执行 state/sol_plan.md。
只修改计划中列出的文件；不要修改实验时长、seed、安全门或 project_state.md。
完成编译、静态检查或离线 probe，并把 diff、源码 hash、验证命令和残余风险写入 state/terra_implementation.md。
不要启动 ROS/Gazebo 实验。
```

terra 完成后切回 sol：

```text
请审核 state/terra_implementation.md 和当前 git diff。
如果修改范围、验证和安全语义都合格，写入 state/sol_approval.md；否则写出拒绝原因和需要返工的最小事项。不要启动实验。
```

terra 不得维护正式 `project_state.md`。

## 5. DeepSeek 终端 B：执行一轮已批准实验

打开另一个终端：

```bash
cd /home/houslakers/auto_tune_racer/swarmlio_multi
deepseek
```

给 DeepSeek 的固定执行要求：

```text
你是实验执行手。

先读取 AGENTS.md、state/current_summary.md、experiments/manifests/2uav_smoke.yaml、state/sol_approval.md。

只执行 sol 批准的 manifest 和白名单脚本。先做 preflight，再启动 2-UAV smoke。必须保存新的 results/RUN-时间戳/，包括 manifest、源码 hash、runtime 参数、每架 UAV 状态、metrics、日志摘要和退出原因。

实验期间不得修改源码、参数、project_state.md 或 state/SESSION_HANDOFF.md。不得删除或覆盖任何旧 runroot。实验结束后只写 execution_result.md 和必要事件记录；如果脚本有问题，写 state/execution_issue.md 并停止，不要自行修复代码。
```

当前目录的 `scripts/monitor_experiment.py` 只是 DeepSeek API 监控接口骨架；它不会启动 ROS/Gazebo，也不会替代实际 runner。必须先接入真实 preflight、启动、监控和收集脚本。

## 6. luna 阶段：实验结束后读结果

DeepSeek 完成后，在 Codex 终端切换 luna：

```text
$result-reporting

请只分析最新完成的 RUN-*。
读取该 runroot 的 manifest、metrics、runtime 参数、每架 UAV 状态和日志摘要。
不要修改源码、project_state.md 或 state/SESSION_HANDOFF.md。
把本轮结果、证据路径、异常分类、观察与推断的区别写入 state/luna_review.md。
```

luna 应回答：

- 本轮是否有效；
- UAV0/UAV1 是否分别完成；
- 是否有 freeze、crash、contact；
- fleet coverage、overlap、最小机间距离；
- telemetry 是否完整；
- 问题属于单机节点还是多机协调；
- 是否建议修改代码。

## 7. sol 阶段：每轮只合并一次正式状态

luna 完成后切换 sol：

```text
$lead-planning

请审核 state/luna_review.md 和本轮 RUN-* 的证据。
如果证据足够，请在本轮实验结束阶段一次性更新：
1. project_state.md；
2. state/SESSION_HANDOFF.md；
3. state/current_summary.md；
4. state/current.json。

记录本轮事实、证据路径、结论、未解决风险和下一步唯一推荐动作。
不要重写或删除历史记录，不要把单机指标外推为 fleet-level 结论。
```

这一动作是每轮唯一一次正式状态合并。实验运行中、DeepSeek 执行中和 luna 总结时都不得更新这几个正式状态文件。

## 8. 如果 DeepSeek 报告脚本问题

DeepSeek 只写：

```text
state/execution_issue.md
```

回到 Codex，切换 sol：

```text
$lead-planning

请读取 state/execution_issue.md、最新 RUN-*、manifest、runtime 参数和日志摘要。
判断问题属于 runner、launch、namespace、参数回读、telemetry、底层算法还是 DeepSeek 执行错误。
如果需要改代码，只生成最小修复计划到 state/sol_plan.md；不要直接改代码，不要更新正式 project_state。
```

若需要改代码，按以下循环：

```text
sol 生成计划 → terra 修改 → sol 审核 → DeepSeek 重试
```

只有完成一次新的实验并经过 luna 审核后，sol 才更新正式状态。

## 9. 长对话压缩和新会话

当 Codex 对话过长，在旧对话中执行：

```text
请生成 state/SESSION_HANDOFF.md。
只记录当前目标、已完成事项、源码 hash、最新实验、已确认事实、未解决问题、下一步唯一动作和禁止重复的工作。
不要修改源码，不要启动实验。
```

新开对话后只输入：

```text
请先读取 AGENTS.md、handoff/SINGLE_UAV_BASELINE.md、state/SESSION_HANDOFF.md 和 state/current_summary.md。
不要读取完整旧对话。先确认当前阶段、最近一次实验和下一步唯一动作。
```

## 10. 一轮实验的完成定义

一轮实验只有同时满足以下条件才算完成：

- runroot 完整且不可覆盖；
- manifest、源码 hash、runtime 参数已保存；
- 每架 UAV 和 fleet 指标齐全；
- 接触、crash、freeze、telemetry 状态已分开记录；
- DeepSeek 已写 execution result；
- luna 已写 `state/luna_review.md`；
- sol 已审核并只更新一次正式状态；
- `project_state.md` 和 `state/SESSION_HANDOFF.md` 已包含证据路径和下一步动作。
