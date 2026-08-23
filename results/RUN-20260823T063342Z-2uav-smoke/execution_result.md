# Execution result: RUN-20260823T063342Z-2uav-smoke（D3 2-UAV 掉线 rehearsal）

- 命令：`python3 scripts/two_uav_runner.py launch --manifest experiments/manifests/2uav_smoke.yaml`
- exit_code：0；wall 耗时约 370 s
- 结论：**duration_complete、final_safety_passed=true、D3 掉线 rehearsal 通过全部 6 项成功标准**

## 不可变身份

- manifest：`experiments/manifests/2uav_smoke.yaml`，SHA-256 `2dc8bb5d13b68655521d3a6852057cddcdc4a18170ad08bce201c26522e3b42e`
- source hash manifest：`config/2uav_source_hashes.sha256`，SHA-256 `2ff0512d643a69ab7fab834c69982baee2339e6fd4ed82ba3afe9697c71747b8`（逐文件校验全通过）
- approval package：`state/2uav_approval.yaml`，SHA-256 `1f6354fd0d316587dfd702f180c690a5bf354641bcd18191cea4199634d61660`
- issuance_id：`dropout-rehearsal-20260823-2uav-2`（已消费，receipt 见 results/approval-consumption/）
- 掉线配置：`enabled=true, vehicle=uav1, mode=control_chain, trigger_sim_s=60, cleanup_policy=stop_active_reclaim`

## 掉线事件核验

- `fleet/dropout.json` 完整：vehicle=uav1、mode=control_chain、reason=intentional_dropout、
  sim_s=90.344、wall_s=8825.05、pids（px4_bridge_2=38185、exploration_node_2=38430、traj_server_2=38439）
- killed nodes：`/px4_bridge_2`、`/exploration_node_2`、`/traj_server_2`（3 节点全灭，missing=[]）
- 注意：nominal trigger=60 sim-s，实际触发记录 sim_s=90.344（监控轮询粒度导致 ~30 sim-s 延迟），
  单次触发、无重复。已在 `state/events.jsonl` 与本文档记录，供 sol 审核。

## 掉线分类核验（D2）

- `dropout_classifications`：uav0=none，uav1=intentional_dropout
- uav1：dropout=true、dropout_mode=control_chain、dropout_sim_s=90.344、crash=false、contact=0/0/0、
  freeze=false、telemetry_complete="dropout_expected"、telemetry_dropout_breakpoint_sim_s=90.344
- 未被误判为 crash/contact/freeze；无 unexpected_loss、无 telemetry_missing

## 剩余 UAV（uav0）继续性

- 掉线前（sim≈90）：path≈28.8 m、trajectory≈20、ack≈5812、obs_vox≈10369
- 掉线后至结束（sim 90.3→150.6）：path→82.9 m（+54 m）、trajectory→77、ack→9867、
  obs_vox→19309（+8940 体素），pos_cmd/ack 连续
- uav0：crash=false、contact=0、freeze=false、ack_timeout=0、telemetry_complete=true
- 全局 abort_reasons=[]；无 crash/contact/process death

## 资源与安全门

| 门 | 值 | 门限 | 结果 |
|---|---|---|---|
| MemAvailable startup | 11.09 GiB | ≥ 8 GiB | ✅ |
| load1 startup | 2.01 | < 10 | ✅ |
| swap startup | 0 / 0 | — | ✅ |
| MemAvailable ready/running | 4.80 GiB（运行期 min pre 4.62 / post 4.63 GiB） | ≥ 3 GiB | ✅ |
| swap running | 0 / 0（delta 0） | delta ≤ 200000 | ✅ |
| RT factor | p50=0.42、p95=0.49 | ≥ 0.5 尽力 | ❌ 已知偏差 |
| teardown | clean、无 survivors、无 kill、master_port_released | — | ✅ |

## 逐机与 fleet 结果

- uav0：path=82.91 m、coverage=19309 voxels（7.18%）、completion 未到（120 s 内未 finish）
- uav1：path=119.96 m、coverage=24751 voxels（9.20%）、掉线后物理下沉至 z≈-0.46（PX4 失链后行为，见下方观察项）
- fleet：coverage ratio=13.16%（35396 voxels）、overlap=0.449、map_consistency=0.245、
  min inter-UAV dist=1.357 m、contact=0

## 观察项（供 sol 审核，非失败项）

1. 掉线触发延迟：nominal 60 sim-s，实际 90.344 sim-s（监控轮询粒度）。语义仍为 intentional、单次触发。
2. uav1 掉线后物理行为：z 先升至 7.17 m 后下沉穿地（z≈-1.10）并稳定在 -0.46 m。
   control_chain 模式 kill 了 px4_bridge，PX4 失去外部控制链后进入失速/下降。
   分类正确（未误判 crash），但若 3-UAV 主实验要求"机体仍可悬停"，需高终端评估
   是否保留 px4_bridge（仅 kill exploration/traj）或改用 communication 模式。
3. RT p95=0.49 仍低于 0.5 目标（与 RUN-20260822T173640Z 一致的已知偏差），不豁免门、仅记录。
