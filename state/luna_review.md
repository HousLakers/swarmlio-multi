# Luna review: RUN-20260823T194616Z-3uav-smoke（D10 node_level 重跑最终验证）

状态：D0–D10 掉线实验全链路闭环，本 run 为 **node_level 最严模式重跑最终验证**，
`duration_complete + final_safety_passed=true`，无 abort。本报告按
`handoff/DROPOUT_EXPERIMENT_WORKFLOW.md` 第 5 节掉线专项模板撰写，属 D11 收尾交付。

## 1. 不可变身份与运行结论

- runroot：`results/RUN-20260823T194616Z-3uav-smoke/`
- manifest：`experiments/manifests/3uav_smoke.yaml`
  - SHA-256 `d9a64bf7b469ef85954fffdb09e7c9143b8b6b72b18b735477852a0e0265ebfe`
  - `approval_status: blocked_pending_verified_launch_and_preflight`
  - `dropout: {enabled: true, vehicle: uav1, mode: node_level, trigger_sim_s: 60}`
- 3-UAV source hash manifest：`config/3uav_source_hashes.sha256`
  - SHA-256 `146591227da89c43093c1d3b6783950f08b7a8bc92c735166f9c70586fbf6784`
- approval package：`state/3uav_approval.yaml`
  - `issuance_id=dropout-smoke-20260824-3uav-D10-replay`（一次性，已消费，不得复用）
- platform commit：`57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`
- single commit：`08fb545a78ed7f1df2e1182a0e6d7a13540a28f6`
- overlay：`range20m_omnidirectional_v1`
  - manifest `7c54d34ad5aa878a89fb07394b5efe88373fcdf848bbe0188b81b6fbdecb1f3c`（22 文件）
  - installer `8cabae8d6c8019cf49e4f3f6d836ac9c0fa7d26d6926e1140af8cc87c42ee5eb`
- 环境 baseline：`racer_outdoor_50x50_v1`（50×50×3 m，planner box ±24.5 / z 1.15–2.7）

### 运行结论

- `exit_reason = duration_complete`（sim 120 s 合同，实际 clock 达 147.45 sim-s）
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
| sim_s（实际） | **87.166**（poll 粒度，≈ trigger 点，工作流 0.2 允许） |
| wall_s | 21758.18 |
| reason | `intentional_dropout` |
| cleanup_policy | `stop_active_reclaim` |
| killed_nodes | `/px4_bridge_2`、`/exploration_node_2`、`/traj_server_2` |
| pids | px4_bridge_2=248003、exploration_node_2=248337、traj_server_2=248355 |

`missing_nodes` 为空；记录完整（vehicle/mode/sim_s/wall_s/pid 全在）。

## 3. 掉线分类核验

`fleet.dropout_classifications`：

- `uav0`：`none` ✅
- `uav1`：`intentional_dropout` ✅
- `uav2`：`none` ✅

process_liveness 最终快照：

- uav1 三节点（`/px4_bridge_2`、`/exploration_node_2`、`/traj_server_2`）`false` = 注入故障本身
- 其余 8 节点全部 `true`

uav1 逐机复核：`freeze=false`、`crash=false`、`dropout=true`、`ack_timeout=0`，
`telemetry_complete="dropout_expected"` —— 未被误分类。无 `crash:*`、`severe_contact:*` abort。

## 4. 剩余 UAV 继续性指标（掉线前 vs 掉线后）

| 机 | surviving | post-dropout coverage delta | 继续性依据 |
|---|---:|---:|---|
| uav0 | ✅ true | **+5,350 voxels** | coverage 继续增长 |
| uav2 | ✅ true | **+24,231 voxels** | coverage 继续增长 |

- fleet `telemetry_completeness = true`
- task_allocation_state_samples = 3,825（掉线后继续产生）
- uav1 非 survivor：`surviving_uavs_continue[uav1] = false`

uav1 掉线后，剩余两机持续探索且无 abort、无 crash、无 contact，满足工作流 0.4 第 1–5 项。

## 5. 资源与安全门对照

| 门 | 阶段 | 值 | 门限 | 结果 |
|---|---:|---:|---:|:---:|
| MemAvailable | startup | 11.74 GiB（12,655,820,800 B） | ≥ 8 GiB | ✅ |
| MemAvailable | ready | **3.45 GiB**（3,450,011,648 B） | ≥ 3 GiB | ✅ |
| load1 | startup / ready | 0.50 / 2.02 | < 10 | ✅ |
| swap delta | 全程 | in +76 / out +147,536（启动→ready） | ≤ 200,000 | ✅ |
| stop | teardown | clean, survivors=[], kill=[] | 无 survivors | ✅ |

RT factor：`p50=0.278`、`p95=0.305`，与历史一致，记录为已知偏差，不阻断掉线语义结论。

## 6. 逐机与 fleet 结果表

### 逐机

| 机 | freeze | crash | dropout | ack_timeout | trajectory | pos_cmd/ack | path (m) | coverage voxels | coverage ratio | completion |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| uav0 | false | false | none | 0 | 52 | 11,649 | 93.4 | 20,980 | 0.0780 | false |
| uav1 | false | false | intentional | 0 | 17（掉线前） | 5,890 / 5,890 | 26.1 | 4,065 | 0.0151 | 掉线（dropout_expected） |
| uav2 | false | false | none | 0 | 176 | 12,152 | 67.0 | 28,296 | 0.1052 | false |

uav2 仍为三机探索量最大；D9r `clearVehicleBody` 冻结修复在 D10 重跑下持续有效。

### Fleet

| 指标 | 值 |
|---|---:|
| fleet_coverage_voxels | 30,955 |
| fleet_coverage_ratio | 0.1151（11.5%，120 sim-s / 50×50 地图） |
| overlap_ratio | 0.8733 |
| map_consistency_jaccard | 0.1232 |
| minimum_inter_uav_distance | 0.53–0.58 m（无 contact） |
| fleet_contact_count | 0 |
| abort_reasons | `[]` |
| clock | monotonic=true、samples=135,363、last_sim_s=147.45 |
| task_allocation_state_samples | 3,825 |

## 7. 产出物与固定交付约定

- `grid_path.png`：三机 top-down 栅格路径图，底图为 **无人机实际建出的占据栅格**，叠加轨迹。
- `point_cloud.png`：三机 **无人机实际建出的点云/体素**，叠加轨迹。
- `coverage_voxels.json`：每机落盘的建图 voxel，用于可追溯复图。
- 约定：自本 run 起，每个实验 run 的 collector 收尾自动输出以上产物。

## 8. Luna 判断与后续边界

### 判断

- D0–D10 掉线实验 Route A 全链路闭环。
- uav1=`intentional_dropout`，未被误判为 crash/contact/freeze。
- uav0 / uav2 在 node_level 掉线后持续探索，无 abort、无 crash、无 contact。
- `grid_path.png` / `point_cloud.png` 已按“真实建图数据”标准重做：
  - `grid_path.png` = UAV-built occupancy grid + trajectories
  - `point_cloud.png` = UAV-built point cloud/voxels + trajectories

### 边界

- 本次证明的是掉线语义正确性与剩余机继续性，不是比赛实时性/覆盖率 PASS。
- 不把 `intentional_dropout` 写成 crash/contact；不外推单机/双机性能到 fleet。
- 120 sim-s 内无人触发 `completion` 是地图规模下的正常现象。
- 后续任何新实验必须重新签发 approval package；已消费的 `dropout-smoke-20260824-3uav-D10-replay` 不得复用。

```text
handoff_status: READY
handoff_model: high-terminal
handoff_command:
D10 node_level dropout-smoke 重跑证据完整，Luna 判定 PASS（掉线语义维度）。
收尾：更新 current_summary.md / SESSION_HANDOFF.md，并替换报告中的图为本次真实建图图；
按阶段规则提交并推送 D11 closeout。
```
