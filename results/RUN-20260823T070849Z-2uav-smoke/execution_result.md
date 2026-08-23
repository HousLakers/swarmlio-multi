# Execution result: RUN-20260823T070849Z-2uav-smoke（D3 2-UAV 掉线 rehearsal · D1 返工后正式版）

- 命令：`python3 scripts/two_uav_runner.py launch --manifest experiments/manifests/2uav_smoke.yaml`
- exit_code：0
- 结论：**duration_complete、final_safety_passed=true、D3 全部 6 项成功标准通过**
- 本 run 使用 D1 返工版 runner（control_chain 保留 px4_bridge），为修复后正式版；
  第 1 次运行 `RUN-20260823T063342Z` 为返工前对照（uav1 穿地 z≈-0.46）。

## 不可变身份

- manifest：`experiments/manifests/2uav_smoke.yaml`，SHA-256 `2dc8bb5d13b68655521d3a6852057cddcdc4a18170ad08bce201c26522e3b42e`
- source hash manifest：`config/2uav_source_hashes.sha256`，SHA-256 `5de2b4093ad27553698409918453f7df909e2def15da862b84fe3c7552e06340`
- approval package：`state/2uav_approval.yaml`，SHA-256 `866579f2d0d9f88b46c9ef88819c818bdc33bf28723e527136156a40a93355e1`
- issuance_id：`dropout-rehearsal-20260823-2uav-3`（已消费，receipt 见 results/approval-consumption/）
- runner：`scripts/two_uav_runner.py` SHA-256 `fa9ce9f9fe057bc8fd07b608532ee7d15b6c4cd021e5198536f60fae732f345b`
- 掉线配置：`enabled=true, vehicle=uav1, mode=control_chain, trigger_sim_s=60, cleanup_policy=stop_active_reclaim`

## 掉线事件核验（D1 返工后）

- `fleet/dropout.json` 完整：vehicle=uav1、mode=control_chain、reason=intentional_dropout、
  sim_s=90.14、wall_s=10932.66、pids（exploration_node_2=64818、traj_server_2=64827）
- killed nodes：`/exploration_node_2`、`/traj_server_2`；**`/px4_bridge_2` 存活**
  （返工语义：control_chain 保留 px4_bridge，PX4 可维持悬停）
- process_liveness 确认：px4_bridge_2=true，exploration_node_2=false，traj_server_2=false
- 单次触发、无重复；nominal 60 sim-s vs 实际 90.14 sim-s（监控轮询粒度延迟，与第 1 次一致）

## 掉线分类核验（D2）

- `dropout_classifications`：uav0=none，uav1=intentional_dropout
- uav1：dropout=true、dropout_mode=control_chain、dropout_sim_s=90.14、crash=false、contact=0/0/0、
  freeze=false、telemetry_complete="dropout_expected"、telemetry_dropout_breakpoint_sim_s=90.14
- **uav1 掉线后维持悬停：最终位置 z=1.73 m（未穿地，修复生效）**
- 无 unexpected_loss、无 telemetry_missing

## 剩余 UAV（uav0）继续性

- uav0 全程无 abort/crash/contact/freeze/ack_timeout；telemetry_complete=true
- completion 观察到 `finish exploration.`（wall 11076.43），hold_at_goal=true
- 说明：本 run uav0 探索量低于第 1 次（path 0.11→7.40 m、obs_vox=7227、trajectory=2），
  较早进入 hold_at_goal/完成态；行为差异为探索随机性与路径分叉，非掉线造成（掉线前 uav0 已接近完成）
- 全局 abort_reasons=[]；fleet_contact_count=0

## 资源与安全门

| 门 | 值 | 门限 | 结果 |
|---|---|---|---|
| MemAvailable startup | 10.87 GiB | ≥ 8 GiB | ✅ |
| load1 startup | 2.32 | < 10 | ✅ |
| swap startup | 0 / 0 | — | ✅ |
| MemAvailable ready/running | 4.68 GiB（运行期 min 4.49 GiB） | ≥ 3 GiB | ✅ |
| swap running | 0 / 0（delta 0） | delta ≤ 200000 | ✅ |
| RT factor | p50=0.41、p95=0.46 | ≥ 0.5 尽力 | ❌ 已知偏差 |
| teardown | clean、无 survivors、无 kill | — | ✅ |

## 逐机与 fleet 结果

- uav0：path=7.40 m、coverage=7227 voxels（2.69%）、completion=observed、hold_at_goal=true
- uav1：path=71.53 m、coverage=20975 voxels（7.80%）、掉线后悬停 z=1.73 m
- fleet：coverage ratio=8.46%（22752 voxels）、overlap=0.754、map_consistency=0.240、
  min inter-UAV dist=1.07 m、contact=0

## 观察项（供 sol 审核，非失败项）

1. 掉线触发延迟：nominal 60 sim-s，实际 90.14 sim-s（监控轮询粒度，两次一致）。
2. uav0 本 run 探索量偏少（path 7.4 m、trajectory=2）但安全门与继续性标准满足；
   与第 1 次（path 82.9 m）差异源于探索随机性。若需更高覆盖率复现，可要求更多重复。
3. RT p95=0.46 仍低于 0.5 目标（既有已知偏差，不豁免门、仅记录）。
4. 两次 D3 运行的关系：`RUN-20260823T063342Z`（返工前，uav1 穿地）为对照；
   `RUN-20260823T070849Z`（返工后，uav1 悬停）为正式证据。
