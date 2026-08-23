# SwarmLIO Multi-UAV 全流程运行手册

本文件描述当前项目约定的两终端工作流：

- 终端 A：一个长期 Codex 会话，按阶段使用 luna、sol、terra；
- 终端 B：DeepSeek，负责执行已批准的实验和保存 runroot。

本目录当前由 `scripts/two_uav_runner.py` 编排 ROS/Gazebo 生命周期，但仍必须先完成
静态准备和一次性 live preflight；preflight 未通过不得进入 smoke。

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

1. 读取 `handoff/SINGLE_TO_MULTI_TRANSFER_20260820.md`，核对公共平台、单机仓库和
   overlay 的冻结 commit/hash；不要重新推断或浮动到最新分支。
2. 核对 `handoff/SINGLE_UAV_BASELINE.md` 中的地图、GT 模式和节点能力边界。
3. 检查 `handoff/KNOWN_RISKS.md`。
4. 确认 `experiments/manifests/2uav_smoke.yaml` 的 `launch_command` 和命令白名单只
   指向已验证的 runner 入口；不得另写临时 launch 命令。
5. 确认 manifest 白名单包含 preflight、smoke launch、monitor、stop、collect 五个固定
   runner 命令。
6. 确认每架 UAV 使用独立 namespace、初始位姿、vehicle ID、端口、TF、日志目录和
   结果目录。
7. 确认 runner 能保存源码 hash、运行时参数、manifest、退出原因、每架 UAV 状态和
   fleet 指标。

当前唯一 manifest 已固定为：

```text
python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml
python3 scripts/two_uav_runner.py launch --manifest experiments/manifests/2uav_smoke.yaml
```

这两个命令都必须通过 runner 的 immutable approval package。不得直接执行
`roslaunch`、Gazebo 或其它未列入 manifest 的命令。

## 2. 三终端模型与启动前置（2026-08-23 起）

### 2.1 三终端模型

三个并行终端各自固定 skill：

```text
高终端（思考审核规划）:  $lead-planning   [$sol-finalize-sync 收尾职责已合并]
中终端（写代码）:        $low-level-implementation
低终端（执行与总结）:    $experiment-execution → $result-reporting
```

打开方式（各开一个会话）：

```bash
cd /home/houslakers/auto_tune_racer/swarmlio_multi
codex    # 高终端
codex    # 中终端
codex    # 低终端
```

### 2.2 高终端启动前置

先读文件（只读这些，不读完整旧对话）：

- `AGENTS.md`
- `handoff/TERMINAL_HANDOFF_PROTOCOL.md`
- `handoff/DROPOUT_EXPERIMENT_WORKFLOW.md`
- `state/current_summary.md`
- `state/SESSION_HANDOFF.md`
- `state/dropout_experiment_plan.md`
- `experiments/manifests/2uav_smoke.yaml`
- `config/2uav_static.yaml`

然后输入这段提示语：

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

### 2.3 中终端启动前置

先读文件：

- `AGENTS.md`
- `handoff/TERMINAL_HANDOFF_PROTOCOL.md`
- `handoff/DROPOUT_EXPERIMENT_WORKFLOW.md`
- `state/current_summary.md`
- `state/SESSION_HANDOFF.md`
- `state/dropout_experiment_plan.md`
- `state/sol_plan_dropout.md`
- `state/terra_implementation.md`

然后输入这段提示语：

```text
这是三终端模型中的「中」终端（写代码）。请先只读取以下文件：
AGENTS.md、handoff/TERMINAL_HANDOFF_PROTOCOL.md、handoff/DROPOUT_EXPERIMENT_WORKFLOW.md、
state/current_summary.md、state/SESSION_HANDOFF.md、state/dropout_experiment_plan.md、
state/sol_plan_dropout.md 和 state/terra_implementation.md。
不要读取完整旧对话，不要启动实验。请确认：
1. 当前待实现的 Dx 任务编号和允许写入的文件清单；
2. 已完成的实现是否已提交 stage commit；
3. 当前 git diff 的未提交部分；
4. 唯一下一步动作（继续实现、补充验证证据或交回高终端审核）。
输出 handoff_status 和下一步指令。
```

### 2.4 低终端启动前置

先读文件：

- `AGENTS.md`
- `handoff/TERMINAL_HANDOFF_PROTOCOL.md`
- `handoff/DROPOUT_EXPERIMENT_WORKFLOW.md`
- `state/current_summary.md`
- `state/SESSION_HANDOFF.md`
- `state/dropout_experiment_plan.md`
- `experiments/manifests/2uav_smoke.yaml`（或后续 `3uav_smoke.yaml`）
- `state/2uav_approval.yaml`（或 `state/3uav_approval.yaml`）

然后输入这段提示语：

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

### 2.5 刷新后重启的启动前置

刷新文档生成后，三个终端各自新开会话，首条消息统一为：

```text
请先只读取 AGENTS.md、handoff/TERMINAL_HANDOFF_PROTOCOL.md、state/current_summary.md、
state/SESSION_HANDOFF.md 和 handoff/DROPOUT_EXPERIMENT_WORKFLOW.md。
我是「高/中/低」终端。只确认当前阶段、最近 stage commit、已消费 package 和唯一下一步动作；
不要启动实验，不要重复已完成的工作。
```

### 2.6 用户意见优先级

用户的本轮意见可以直接追加在 Skill 后面，例如：

```text
$lead-planning

本轮意见：只允许做 2-UAV preflight；不允许修改单机 escape 参数；如果问题只是 namespace，优先改 runner 或 launch。
```

用户本轮明确意见优先于 Skill 的默认流程，但不能静默突破安全门、实验范围或原始数据保护规则。

## 3. sol 阶段：批准一轮实验

在「高」终端选择 sol，执行：

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

计划审核记录仍由 sol 写入：

```text
state/sol_approval.md
```

但 `state/sol_approval.md` 不是 runner 的执行授权。实际执行必须有独立的一次性
`state/2uav_approval.yaml`，其内容绑定当前 manifest SHA-256 和
`config/2uav_source_hashes.sha256` SHA-256：

```yaml
schema_version: 1
stage: preflight        # smoke 阶段必须另发 stage: smoke
approved: true
allowed_actions: [preflight]
manifest_sha256: <current manifest sha256>
source_hash_manifest_sha256: <current source-hash-manifest sha256>
issued_by: sol
max_uses: 1
```

每个 approval package 只能使用一次；hash、stage、action、issuer 或 receipt 不匹配时
runner fail-closed。preflight 和 smoke 必须使用两个不同的批准包。

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

## 5. DeepSeek 终端 B：执行 preflight，再执行一轮已批准实验

打开另一个终端：

```bash
cd /home/houslakers/auto_tune_racer/swarmlio_multi
deepseek
```

给 DeepSeek 的固定执行要求：

```text
你是实验执行手。

先读取 AGENTS.md、state/current_summary.md、experiments/manifests/2uav_smoke.yaml、
state/sol_approval.md 和当前 `state/2uav_approval.yaml`（若不存在则停止）。

只执行 sol 批准的 manifest 和白名单脚本。执行顺序固定为：

1. `preflight`：runner 先复核 manifest/source hash 和静态门，再启动 stack；随后做
   live topic/clock/TF/参数/日志检查、24 s watchdog soak、停栈和最终 metrics 校验。
2. 只有 preflight 的 `live_preflight.json` 为 `passed: true`，且 Sol 审核该 runroot 后，
   才能签发新的 `stage: smoke` package。
3. `launch`：runner 再次做静态/live/soak 门，通过后才发布
   `/move_base_simple/goal`，运行 manifest 指定的 120 simulated seconds。

preflight 和 smoke 各自创建不可覆盖的 `results/RUN-时间戳-2uav-*`。必须保存 manifest、
source hash、runtime 参数、每架 UAV 状态、metrics、日志摘要、abort 和退出原因。

实验期间不得修改源码、参数、project_state.md 或 state/SESSION_HANDOFF.md。不得删除或覆盖任何旧 runroot。实验结束后只写 execution_result.md 和必要事件记录；如果脚本有问题，写 state/execution_issue.md 并停止，不要自行修复代码。
```

当前目录的 `scripts/monitor_experiment.py` 只是 DeepSeek API 监控接口骨架；它不会启动
ROS/Gazebo，也不会替代实际 runner。运行中只能使用 manifest 白名单的 `monitor`、`stop`
和 `collect` 命令，不能手工补发 goal 或重启单个 UAV。

当前最新有效 preflight 是
`results/RUN-20260821T082048Z-2uav-preflight/`，静态 53/53、live 48/48 全部通过。
其后首次 smoke `results/RUN-20260821T083254Z-2uav-smoke/` 在 sim 32.39/120
fail-closed 中止：uav0 trajectory 被错误按 5 s 连续 freshness 监管，同时存在真实的
uav0 A* no-path 和 uav1 start-inside-inflated-occupancy 问题。两个 package 均已消费，
当前没有有效执行授权；不得直接重试。

对接时按以下产物判断，不要只看终端退出码：

- runner 自动写入 `static_preflight.json`、`live_preflight.json`、`stop_result.json`，以及
  成功进入 collector 后的 `uav0/`、`uav1/`、`fleet/` telemetry/metrics；
- DeepSeek 在同一 runroot 追加 `execution_result.md`，记录命令、退出原因、源码 hash、
  运行时参数和证据路径；
- preflight 若在 `/clock`、topic 或参数门之前失败，没有逐机 metrics 是预期的基础设施
  失败，不得补造 metrics，也不得据此启动 smoke。

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

## 9. 长对话压缩、刷新和新会话

三终端模型下，任意终端都可以说「刷新」触发刷新流程（规则见
`handoff/TERMINAL_HANDOFF_PROTOCOL.md` 第 2 节）：

- 收到「刷新」的终端先暂停当前动作、整理自己的状态；
- 最后由高终端汇总写入 `state/SESSION_HANDOFF.md`；
- 刷新不是新实验，也不是 commit 替代品；
- 刷新后三终端按第 2.5 节「刷新后重启的启动前置」重新开会话。

三终端均可执行：

```text
请生成 state/SESSION_HANDOFF.md。
只记录当前目标、已完成事项、源码 hash、最新实验、已确认事实、未解决问题、下一步唯一动作和禁止重复的工作。
不要修改源码，不要启动实验。
```

新开对话后，按第 2.2/2.3/2.4 节对应终端的启动前置执行（只读对应文件 + 输入对应提示语）。

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

## 11. 每阶段提交规则（掉线实验 Route A 专用，2026-08-23 起）

掉线实验 D0–D11 每完成一阶段，必须 commit + push，规则写死在 `AGENTS.md`
「每阶段提交」节和 `handoff/TERMINAL_HANDOFF_PROTOCOL.md` 第 4 节：

1. 每阶段至少一个 commit；commit 信息格式固定为
   `stage: <阶段ID> <终端>: <一句话>`；
2. 只提交该阶段交付物（源码/脚本/config/manifest/state 文档/runroot 摘要）；
   不提交原始日志、点云、build/devel/install、密钥、整个 results 目录；
3. 每次 commit 后 push origin main；
4. 不 rewrite history、不 force push、不 amend 已推送 commit；
5. 失败阶段先提交 `stage: Dx FAIL <原因>`，再提交修复版；
6. 高终端审核交付物后，才由对应终端执行 commit + push；
7. 标准 preflight/smoke（非掉线）仍按一轮一收尾 commit。

commit 命名参考：

```text
stage: D0 dropout semantics frozen (high)
stage: D1 runner dropout event (mid)
stage: D2 collector dropout classification (mid)
stage: D3 2uav dropout rehearsal (low)
stage: D5 3uav parameterization (mid)
stage: D9 3uav control-chain dropout smoke (low)
stage: D11 dropout report and closeout (high)
```

## 12. 掉线实验（Route A）阶段速查

详细清单见 `state/dropout_experiment_plan.md`；语义见 `handoff/DROPOUT_EXPERIMENT_WORKFLOW.md`。

| 阶段 | 内容 | 终端 |
|---|---|---|
| D0 | 冻结掉线语义 | 高 |
| D1 | runner 掉线事件（fault injection） | 中 |
| D2 | collector 掉线分类 | 中 |
| D3 | 2-UAV 掉线 rehearsal | 低 |
| D4 | 分类强化 + 报告字段 | 中 |
| D5 | 三机参数化 | 中 |
| D6 | 3-UAV config/launch/manifest | 中 |
| D7 | 3-UAV static 校验 | 中 |
| D8 | 3-UAV diagnostic preflight | 低 |
| D9 | 3-UAV 掉线 smoke（control_chain） | 低 |
| D10 | 3-UAV 掉线 smoke（node_level 最终） | 低 |
| D11 | 报告与收尾 | 低→高 |

当前 git 身份：`HousLakers <HousLakers@users.noreply.github.com>`，远程 `origin` =
`https://github.com/HousLakers/swarmlio-multi.git`。
