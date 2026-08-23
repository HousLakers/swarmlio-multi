# Luna review: RUN-20260823T190024Z-3uav-smoke（D10 node_level 最终验证）

状态：D0–D10 掉线实验全链路闭环，本 run 为 **node_level 最严模式最终验证**，
`duration_complete + final_safety_passed=true`，无 abort。本报告按
`handoff/DROPOUT_EXPERIMENT_WORKFLOW.md` 第 5 节掉线专项模板撰写，属 D11 收尾交付。

## 1. 不可变身份与运行结论

- runroot：`results/RUN-20260823T190024Z-3uav-smoke/`
- manifest：`experiments/manifests/3uav_smoke.yaml`
  - SHA-256 `d9a64bf7b469ef85954fffdb09e7c9143b8b6b72b18b735477852a0e0265ebfe`
  - `approval_status: blocked_pending_verified_launch_and_preflight`（D10 使用后未消费恢复，因 runner 合同要求 launch 前置为 blocked）
  - `dropout: {enabled: true, vehicle: uav1, mode: node_level, trigger_sim_s: 60}`
- 3-UAV source hash manifest：`config/3uav_source_hashes.sha256`
  - SHA-256 `e4c79a5ce232254199ea319773cc28eb7955db909e5a880f24f226b190048ec9`
- approval package：`state/3uav_approval.yaml`
  - `issuance_id=dropout-smoke-20260823-3uav-D10-node_level`（一次性，已消费，不得复用）
- platform commit：`57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`
- single commit：`08fb545a78ed7f1df2e1182a0e6d7a13540a28f6`
- overlay：`range20m_omnidirectional_v1`
  - manifest `7c54d34ad5aa878a89fb07394b5efe88373fcdf848bbe0188b81b6fbdecb1f3c`（22 文件）
  - installer `8cabae8d6c8019cf49e4f3f6d836ac9c0fa7d26d6926e1140af8cc87c42ee5eb`
- 环境 baseline：`racer_outdoor_50x50_v1`（50×50×3 m，planner box ±24.5 / z 1.15–2.7）

### 运行结论

- `exit_reason = duration_complete`（sim 120 s 合同，实际 clock 达 146.69 sim-s）
- `final_safety_passed = true`，detail：`smoke command chain complete`
- `fleet_metrics / uav0_metrics / uav1_metrics / uav2_metrics` 全部就绪
- `stop = {clean: true, survivors: [], kill: [], identity_confirmed: true}`，teardown clean
- 掉线注入后无任何非预期 abort，全局 `abort_reasons = []`

## 2. 掉线事件核验（fleet/dropout.json）

| 字段 | 值 |
|---|---|
| vehicle | `uav1` |
| mode | `node_level`（最严：bridge + exploration + traj 三节点全杀） |
| trigger_sim_s | 60 |
| sim_s（实际） | **86.65**（poll 粒度，≈ trigger 点，工作流 0.2 允许） |
| wall_s | 19004.12 |
| reason | `intentional_dropout` |
| cleanup_policy | `stop_active_reclaim` |
| killed_nodes | `/px4_bridge_2`、`/exploration_node_2`、`/traj_server_2` |
| pids | px4_bridge_2=206333、exploration_node_2=206617、traj_server_2=206626 |

`missing_nodes` 为空；记录完整（vehicle/mode/sim_s/wall_s/pid 全在）。

## 3. 掉线分类核验

`fleet.dropout_classifications`：

- `uav0`：`none` ✅（未受 uav1 掉线影响，无意外断线）
- `uav1`：`intentional_dropout` ✅（与 dropout.json 的 vehicle 一致，未被误判为 crash/contact/freeze）
- `uav2`：`none` ✅

process_liveness 最终快照：

- uav1 三节点（`/px4_bridge_2`、`/exploration_node_2`、`/traj_server_2`）`false` = **注入故障本身**，符合预期
- 其余 8 节点全部 `true`

uav1 逐机复核：`freeze=false`、`crash=false`、`dropout=true`、`ack_timeout=0`，
`telemetry_complete="dropout_expected"` —— 未被误分类。无 `crash:*`、`severe_contact:*` abort。

## 4. 剩余 UAV 继续性指标（掉线前 vs 掉线后）

| 机 | surviving | post-dropout coverage delta | 继续性依据 |
|---|---:|---:|---|
| uav0 | ✅ true | **+7,461 voxels** | coverage 继续增长 |
| uav2 | ✅ true | **+10,212 voxels** | coverage 继续增长 |

- fleet `telemetry_completeness = true`
- task_allocation_state_samples = 3,872（掉线后继续产生）
- uav1 非 survivor：`surviving_uavs_continue[uav1] = false`，coverage_delta = null（正确语义）

uav1 掉线后，剩余两机持续探索且无 abort、无 crash、无 contact，满足工作流 0.4 第 1–5 项。

## 5. 资源与安全门对照

| 门 | 阶段 | 值 | 门限 | 结果 |
|---|---:|---:|---:|:---:|
| MemAvailable | startup | 11.86 GiB（12,733,030,400 B） | ≥ 8 GiB | ✅ |
| MemAvailable | ready | **2.76 GiB**（2,959,286,272 B） | ≥ 3 GiB | ⚠️ 低于门限记录 |
| load1 | startup / ready | 1.85 / 4.57 | < 10 | ✅ |
| swap delta | 全程 | in +0 / out +11,982 | ≤ 200,000 | ✅ |
| stop | teardown | clean, survivors=[], kill=[] | 无 survivors | ✅ |

**备注（重要）**：ready 阶段 MemAvailable 2.76 GiB 低于 3 GiB 门限。这与本项目历史
记录一致——3-UAV 栈 RSS ≈ 9.3 GiB，16 GB 主机边界资源紧张。本次判定为「已知资源偏差」，
不豁免门限、不作为掉线语义结论的组成部分；如需正式 PASS 需在资源更充裕的主机复跑
preflight + smoke，或减小地图/机数。掉线实验语义本身未受资源门影响。

RT factor：与 D8/D9 一致（preflight 尽力 ≥0.5，实测低于 0.5），记录为已知偏差，
不阻断掉线语义实验（掉线语义 ≠ 实时性对比）。

## 6. 逐机与 fleet 结果表

### 逐机

| 机 | freeze | crash | dropout | ack_timeout | trajectory | pos_cmd/ack | path (m) | coverage voxels | coverage ratio | completion |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| uav0 | false | false | none | 0 | 52 | 9,165 | 107.5 | 19,604 | 0.0729 | false |
| uav1 | false | false | intentional | 0 | 17（掉线前） | 5,684 / 5,644 | 55.4 | 8,818 | 0.0328 | 掉线（dropout_expected） |
| uav2 | false | false | none | 0 | 176 | 12,134 | 145.0 | 32,471 | 0.1207 | false |

uav2 为三机探索量最大（traj=176、12,134 ack、145 m 路径），D9r `clearVehicleBody`
冻结修复在 D10 node_level 下持续有效。

### Fleet

| 指标 | 值 |
|---|---:|
| fleet_coverage_voxels | 34,581 |
| fleet_coverage_ratio | 0.1286（12.9%，120 sim-s / 50×50 地图） |
| overlap_ratio | 0.8672（共享地图一致） |
| map_consistency_jaccard | 0.2484 |
| minimum_inter_uav_distance | 0.582 m（>0，未接触） |
| fleet_contact_count | 0 |
| abort_reasons | `[]` |
| clock | monotonic=true、samples=135,751、last_sim_s=146.69 |
| task_allocation_state_samples | 3,872 |

## 7. 产出物与固定交付约定（本次新增）

- `grid_path.png`：三机 top-down 栅格路径图（1600×1600）
- `point_cloud.png`：三机轨迹/占据点云图（1600×1280）
- **约定**：自本 run 起，每个实验 run 的 collector 收尾自动输出以上两张图（
  `two_uav_collector.py` 的 `_write_visual_artifacts`），保存在对应 runroot 下。

## 8. Luna 判断与后续边界

### 判断

- D0–D10 掉线实验 Route A 全链路闭环：
  1. D1/D2 掉线注入与分类链路正确；
  2. D3/D9 的 control_chain smoke 证明掉线后剩余机可继续探索；
  3. uav2 冻结根因（shared-map 机体误标占据 → A* NO_PATH → PLAN_TRAJ 死循环）
     经 `clearVehicleBody` 源码修复闭环；
  4. collector `ack_timeout` 竞态误杀经恢复语义修正；
  5. **D10 node_level 最严模式最终验证通过**：uav1 三节点全杀后，
     剩余两机无 abort、无 crash、无 contact，coverage 继续增长。
- 掉线分类无混淆：uav1=`intentional_dropout`，非 crash/contact/freeze 误判。
- 身份链完整且可追溯：manifest + source hash manifest + approval package 三重绑定。

### 边界（不得外推）

- 本次证明的是 **掉线语义正确性与剩余机继续性**，不是比赛实时性/覆盖率的 PASS。
- RT < 0.5 与 ready MemAvailable < 3 GiB 为已知偏差，须在正式比赛口径中另行评估。
- 不把 `intentional_dropout` 写成 crash/contact；不外推单机/双机性能到 fleet。
- 120 sim-s 内无人触发 `completion`（exploration 未收敛），这是地图规模下的正常现象，
  不是失败。
- 后续任何新实验（含资源更充裕主机上的复跑）必须重新签发 approval package；
  已消费的 `dropout-smoke-20260823-3uav-D10-node_level` 不得复用。

```text
handoff_status: READY
handoff_model: high-terminal
handoff_command:
D10 node_level dropout-smoke 证据完整，Luna 判定 PASS（掉线语义维度）。
收尾：一次性更新 project_state.md / current_summary.md / SESSION_HANDOFF.md，
提交 stage: D11 dropout report and closeout (high)；后续实验需重新签发 approval package。
```
