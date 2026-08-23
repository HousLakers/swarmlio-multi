# Sol 受限计划：掉线实验 Route A 首轮（D0–D3）

- 日期：2026-08-23
- 角色：高终端（lead-planning / sol）
- 前置证据：RUN-20260822T173640Z-2uav-smoke 通过（duration_complete、final_safety_passed=true、
  RT p50=0.41 未达标记录为已知偏差；uav1 freeze=晚期规划停滞，非早期掉线）
- 适用清单：`state/dropout_experiment_plan.md`（D0–D11）
- 本草案范围：**D0 冻结语义 → D1 runner 掉线事件 → D2 collector 分类 → D3 2-UAV rehearsal**
- 当前决定：`DRAFT / 待高终端批准后签发`

## 1. 目标

在不改变冻结安全门（MemAvailable/swap/RT/freshness/abort）的前提下，把「单机掉线」实现为
runner 白名单事件，并用 2-UAV rehearsal 验证掉线链路语义正确，为 D4–D10（三机参数化与
3-UAV 正式掉线 smoke）建立可靠基础。

本阶段不证明 fleet 冗余（只剩一架剩余机），只证明：掉线注入正确、分类正确、剩余机继续、
teardown clean。

## 2. 冻结输入（本阶段不可改变）

- 公共平台 `racer-platform` commit `57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`
- 单机 `swarmlio-single-v2` commit `8c8ddf2add3f7b3ce4f9943583fd945f16b1bd91`
- overlay `range20m_omnidirectional_v1`，manifest SHA-256
  `68ceb54faa24f4cc97396634bfc3d611f8e40a6db89999d3cbabc112092ccf62`，installer
  `7e2280d5d0ba88ee501764ab5b5ccc3f3724d5b6abf39704badc7a8976349151`
- manifest：`experiments/manifests/2uav_smoke.yaml`（本轮在 D3 增加 `dropout:` 段）
- 掉线语义：`handoff/DROPOUT_EXPERIMENT_WORKFLOW.md` 第 0 节（必须冻结）
- 安全门：MemAvailable 启动 ≥ 8 GiB、运行 ≥ 3 GiB；swap delta ≤ 200000；RT ≥ 0.5 尽力不豁免

## 3. D1 任务包：runner 掉线事件（中终端）

### 允许写入

- `scripts/two_uav_runner.py`
- `experiments/manifests/2uav_smoke.yaml`（仅增加 `dropout:` 段，供 D3 使用；D1 只解析不触发）
- `state/terra_implementation.md`
- `state/events.jsonl`（追加）

### 实现要求

1. `two_uav_runner.py` 解析 manifest 的 `dropout` 配置：
   `enabled/vehicle/mode/trigger_sim_s/cleanup_policy/record`
2. `action_launch` 的 `monitor_until` 循环中，sim 到达 `trigger_sim_s` 且未触发过时，
   执行白名单 fault injection：
   - `control_chain`：kill 该机 exploration_node / traj_server / px4_bridge 控制链
   - `communication`：kill 该机 bridge/telemetry 心跳进程
   - `node_level`：kill 该机 exploration + bridge + traj
3. 触发时写 `fleet/dropout.json`：`vehicle/mode/sim_s/wall_s/pid/reason`
4. dropped UAV 的残余进程必须进入 `stop_active` 回收名单（不得成为 survivors）
5. self-test 覆盖：触发时机、mode 进程集合、重复触发禁止、dropout 后 abort 路径保留
6. **不得**：放宽安全门；临时 kill；改变 2-UAV 其它参数

### 成功标准

- py_compile / self-test / `git diff --check` 通过
- `dropout` 配置解析缺字段时 fail-fast
- 不触发 dropout 时行为与 RUN-20260822T173640Z 一致（向后兼容）

## 4. D2 任务包：collector 掉线分类（中终端）

### 允许写入

- `scripts/two_uav_collector.py`
- `state/terra_implementation.md`
- `state/events.jsonl`（追加）

### 实现要求

1. 读取同 runroot 的 `fleet/dropout.json`
2. 被 drop 的 UAV：metrics 标 `dropout=true`、`dropout_mode`、`dropout_sim_s`
3. 掉线后该机跳过 `crash/freeze/contact` 判定（避免误判 dropped 为 crash/freeze）
4. telemetry 中标注 dropout 断点；`telemetry_complete` 语义对 dropped UAV 变为
   `dropout_expected`
5. 分类强化：`intentional_dropout`（有 dropout.json）vs `unexpected_loss`（无记录但断线）
   vs `telemetry_missing`（进程存活但频道缺失）
6. freeze 判定联合 pos_cmd 活跃：若最新 pos_cmd 距今 < 15 s 且 vehicle 已就位目标点，
   不标 freeze（修复 RUN-20260822T173640Z uav1 晚期悬停误标）
7. self-test 覆盖四种分类 + freeze 联合判定

### 成功标准

- py_compile / self-test / `git diff --check` 通过
- 现有 2-UAV 无 dropout 场景 metrics 字段兼容

## 5. D3 任务包：2-UAV 掉线 rehearsal（低终端）

### 前置

- 高终端审核 D1/D2 并签发一次性 `dropout-rehearsal` approval package
- manifest `2uav_smoke.yaml` 增加：

```yaml
dropout:
  enabled: true
  vehicle: uav1
  mode: control_chain
  trigger_sim_s: 60
  cleanup_policy: stop_active_reclaim
  record: fleet/dropout.json
```

### 执行

- 只执行白名单 `launch`，等待 duration 结束，保存 runroot
- 不动其它 manifest 参数；不掉线实验不豁免任何门

### 成功标准（对应工作流 0.4）

1. `fleet/dropout.json` 完整
2. uav0 掉线后不 abort、无 crash/contact，coverage 继续增长
3. uav1 标 `intentional_dropout`，非 crash/contact/freeze 误判
4. teardown clean，无 survivors
5. 掉线前后 MemAvailable/swap/RT 保持
6. 全局 abort_reasons 无非预期条目

### 失败处理

- 分类 bug → 回 D2 返工；注入 bug → 回 D1；语义问题 → 回 D0 由高终端重新冻结

## 6. 每阶段提交计划（Route A）

| 阶段 | commit 示例 | 提交者 |
|---|---|---|
| D0 | `stage: D0 dropout semantics frozen (high)` | 高 |
| D1 | `stage: D1 runner dropout event (mid)` | 中（高审核后） |
| D2 | `stage: D2 collector dropout classification (mid)` | 中（高审核后） |
| D3 | `stage: D3 2uav dropout rehearsal (low)` | 低（高审核后） |

规则：**每阶段提交**，只提交该阶段交付物；不提交原始日志/点云/build/整个 results；commit 后 push origin main。

## 7. 禁止动作

- 修改冻结安全门阈值；修改单机 escape 参数；修改 overlay 身份
- 低终端在 rehearsal 中使用非白名单 kill
- 复用已消费 approval package
- 在 D3 通过前启动任何 3-UAV 相关实验
- 把 intentional_dropout 写成 crash / contact / freeze

## 8. 交接指令（本草案签发后）

```text
handoff_status: READY
handoff_model: low-level-implementation
handoff_command:
严格执行 state/sol_plan_dropout.md 第 3、4 节（D1、D2），只修改
scripts/two_uav_runner.py 与 scripts/two_uav_collector.py 并完成静态验证、self-test 和 diff 证据；
不得启动实验、不得 commit/push（等待高终端审核后执行 stage commit）。完成后交回高终端。
```
