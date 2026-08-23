# 单机掉线（Dropout）实验专用工作流

状态：`FROZEN_V1 / sol 已于 2026-08-23 冻结`
适用范围：`swarmlio_multi` 三终端模型下的最终目标实验（单机掉线 → 剩余 fleet 自适应继续）。
前置：2-UAV smoke 已通过（RUN-20260822T173640Z-2uav-smoke），三终端模型已启用。
交接与提交：所有阶段交接遵循 `handoff/TERMINAL_HANDOFF_PROTOCOL.md`；每阶段完成后
必须 commit + push origin main（格式 `stage: <阶段ID> <终端>: <一句话>`），
每阶段提交规则见 `AGENTS.md` 的「每阶段提交」节。

**冻结记录（2026-08-23, sol）**：0.1 术语隔离、0.2 掉线模式、0.3 掉线对象/时机、0.4
成功/失败标准已全部批准，无未决语义；后续任何改动须经高终端重新批准。

## 0. 掉线语义（必须最先冻结，改动需高终端批准）

掉线实验是**受控故障注入（fault injection）实验**，不是 crash、contact、或 teardown。

### 0.1 术语隔离（禁止混同）

| 术语 | 定义 | 判定证据 |
|---|---|---|
| `intentional_dropout` | 计划内掉线，runner 白名单事件触发 | `fleet/dropout.json` + manifest `dropout.*` |
| `unexpected_loss` | 无触发记录但某机 telemetry/进程消失 | telemetry 断点 + 无 dropout 记录 |
| `crash` | 某机高度 < 0.35 或 Gazebo contact 达阈值 | metrics `crash=true` |
| `contact` | 机间/障碍接触超力阈值 | metrics `contact.*` |
| `telemetry_missing` | 频道缺失但进程存活 | collector stale/missing channels |
| `teardown` | 实验正常结束后的进程清理 | `stop_result.json` clean |

### 0.2 掉线模式（按实现复杂度递增）

| 模式 | 语义 | 注入方式 | 适用阶段 |
|---|---|---|---|
| `control_chain` | 断该机控制链（exploration/traj/pos_cmd），机体仍可飞/悬停 | kill 该机 exploration_node/traj_server/px4_bridge 控制相关 | 2-UAV rehearsal、3-UAV 主实验 |
| `communication` | 断该机通信/心跳链，机体仍在 Gazebo | kill 该机 bridge/telemetry 心跳进程 | 2-UAV rehearsal（可选） |
| `node_level` | 同时 kill 该机多个关键进程，最接近真实失联 | kill 该机 exploration + bridge + traj | 3-UAV 主实验（最终验证） |

### 0.3 掉线对象与时机

- 默认掉线对象：`uav1`（保留 uav0 作为"剩余继续"的观测基准）
- 默认触发时机：`trigger_sim_s` 固定值，在起飞稳定 + 已进入 command 链之后（建议 ≥ 30 sim-s）
- 不允许在起飞瞬间掉线（无意义）；不允许随机掉线（不可复现）

### 0.4 成功/失败标准

成功（全部满足）：

1. `fleet/dropout.json` 记录完整（vehicle/mode/sim_s/wall_s/pid）；
2. 剩余 UAV（uav0）不 abort、无 crash、无 contact；
3. 剩余 UAV 继续产生 telemetry / coverage / task allocation，且 post-dropout coverage 有增量；
4. dropped UAV 被正确标记 `intentional_dropout`，未被误判为 crash/contact；
5. dropped UAV 的残余进程被 `stop_active` 回收，无 survivors；
6. 掉线前后资源门保持（MemAvailable ≥ 3 GiB、swap delta ≤ 200000、RT ≥ 0.5 尽力但不放宽门）；
7. 不掉线的那架机不因掉线而冻结（freeze 判定仍然逐机独立）。

失败（任一触发）：

1. 掉线触发后剩余 UAV abort / crash / contact / process death；
2. dropped UAV 被误判为 crash 或 contact；
3. `fleet/dropout.json` 缺失或字段不全；
4. dropped UAV 进程成为 survivors（teardown 非 clean）；
5. 掉线后全局 abort_reasons 出现非预期条目。

## 1. Route A 阶段划分（8 阶段）

### Phase 0：语义冻结（高终端）
- 输出：本文件 v1 冻结、掉线契约定稿
- 产物：`handoff/DROPOUT_EXPERIMENT_WORKFLOW.md`（本文件）、`state/dropout_experiment_plan.md`
- 成功标准：高终端批准本文件，无未决语义

### Phase 1：runner 级 fault injection 实现（中终端）
- 输出：runner 支持 `dropout.*` 事件；collector 支持 dropout 分类
- 产物：`scripts/two_uav_runner.py` / `scripts/two_uav_collector.py` diff + `state/terra_implementation.md`
- 成功标准：静态检查 + self-test + py_compile 通过；`fleet/dropout.json` 逻辑覆盖

### Phase 2：2-UAV 掉线 rehearsal（高批准 → 低执行）
- 输出：2-UAV + `dropout.enabled` 的短 smoke（只验证掉线语义，不是最终 fleet 证明）
- 产物：新 runroot `RUN-*-2uav-dropout-rehearsal`
- 成功标准：0.4 中 1-7 项在 2-UAV 上全部满足
- 局限：只剩一架剩余机，不能证明"fleet 冗余"，只证明"掉线链路正确"

### Phase 3：collector/validator 掉线分类强化（中终端）
- 输出：collector 区分 intentional_dropout / unexpected_loss / crash / telemetry_missing
- 产物：`scripts/two_uav_collector.py` diff + 验证证据
- 成功标准：掉线复跑后 metrics 分类正确

### Phase 4：三机参数化扩建（中终端）
- 输出：runner/preflight/collector 由 `manifest.uav_count` 参数化
- 产物：`config/3uav_static.yaml`、`launch/3uav_*.launch`、`experiments/manifests/3uav_smoke.yaml`、脚本参数化 diff
- 成功标准：静态检查 + self-test 通过；2-UAV manifest 向后兼容

### Phase 5：3-UAV preflight（高批准 → 低执行）
- 输出：3-UAV 一次性 diagnostic preflight
- 产物：runroot `RUN-*-3uav-preflight`
- 成功标准：static + live 门通过，资源门通过（MemAvailable ≥ 3 GiB、无 swap）

### Phase 6：3-UAV 掉线 smoke（高批准 → 低执行）
- 输出：3-UAV + `dropout.enabled=true`（`node_level` 或 `control_chain`）正式掉线实验
- 产物：runroot `RUN-*-3uav-dropout-smoke`
- 成功标准：0.4 中 1-7 项在 3-UAV 上全部满足

### Phase 7：报告与收尾（低总结 → 高收尾）
- 输出：`state/luna_review.md`（掉线专项模板）+ 正式状态合并
- 产物：`project_state.md`、`SESSION_HANDOFF.md`、收尾 commit
- 成功标准：报告区分掉线类型；收尾 commit 只含可追溯摘要

## 2. 三终端分工表

| 阶段 | 高终端（lead-planning） | 中终端（low-level-implementation） | 低终端（experiment-execution / result-reporting） |
|---|---|---|---|
| P0 语义冻结 | 主编、批准 | — | — |
| P1 fault injection | 审核 diff | 实现 dropout 事件 | — |
| P2 2UAV rehearsal | 签发 approval | — | 执行 + 保存 runroot |
| P3 分类强化 | 审核 diff | 实现分类 | — |
| P4 三机参数化 | 审核 diff | 实现参数化 | — |
| P5 3UAV preflight | 签发 approval | — | 执行 + 保存 runroot |
| P6 3UAV dropout smoke | 签发 approval | — | 执行 + 保存 runroot |
| P7 报告收尾 | 审核 luna、合并状态 | — | 写 luna_review |

## 3. manifest `dropout` 段模板（待 terra 实现）

```yaml
dropout:
  enabled: true
  vehicle: uav1
  mode: node_level        # control_chain | communication | node_level
  trigger_sim_s: 60
  cleanup_policy: stop_active_reclaim   # 掉线后残余进程由 stop_active 回收
  record: fleet/dropout.json
```

## 4. 硬门（掉线实验不豁免任何现有门）

- MemAvailable：启动 ≥ 8 GiB，运行 ≥ 3 GiB；
- swap：启动/running 均零新增；
- RT：尽力 ≥ 0.5（p95），不得放宽以掩盖掉线；
- freshness / ACK timeout：不得因掉线实验放大阈值；
- abort 路径：掉线后其它机 crash/contact 仍可 abort 全局；
- 每架 UAV 的 completion/freeze/crash/contact/coverage/telemetry 仍逐机记录。

## 5. 报告模板（luna 掉线专项）

`state/luna_review.md` 掉线实验版固定章节：

1. 不可变身份与运行结论（含掉线 manifest 快照）
2. 掉线事件核验（`fleet/dropout.json`、时间、模式、pid）
3. 掉线分类核验（intentional vs unexpected vs crash/contact 混淆）
4. 剩余 UAV 继续性指标（coverage delta、telemetry completeness、task allocation）
5. 资源与安全门对照（掉线前 vs 掉线后）
6. 逐机与 fleet 结果表
7. Luna 判断与后续边界

## 6. 交接链速查

```text
高:  P0 冻结语义 → (中) P1 实现 → 高审核 → (低) P2 rehearsal
→ 低写 luna → 高审核 → (中) P3 分类 → 高审核 → (中) P4 参数化
→ 高签发 → (低) P5 3UAV preflight → 高审核 → 高签发 → (低) P6 3UAV dropout smoke
→ 低写 luna → 高收尾 P7
```

禁止：中终端在未获高终端批准前启动实验；低终端在掉线实验中使用非白名单 kill；
任何终端在掉线实验后复用已消费 approval package。
