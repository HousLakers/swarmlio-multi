# 2-UAV diagnostic preflight execution result

- Runroot: `RUN-20260821T194922Z-2uav-preflight`
- Command: `python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml`
- Exit code: `0`
- Decision: **`PREFLIGHT_PASS`** —— `live_preflight.json.passed = true`，**49/49 项检查
  全部通过**（较上轮新增 1 项），无 abort。occupancy 快照与 resource profile 已采集。
- Smoke trigger: not issued（本 package 只批准 diagnostic preflight）
- Active lifecycle after exit: absent —— teardown 完整（`stop_result.json`：descendants
  18、`kill []`、`survivors []`、`identity_confirmed=true`、`master_port_released=true`、
  `clean=true`）；无残留进程、无 ACTIVE 文件。
- 本 runroot 为最终 append-only 产物；一次性 approval package 已消费（receipt
  `3b30d659…json` 落盘）

## Frozen identity（全部核对通过）

- Multi repo HEAD: `694a9c30aa9ee8f8f04b4f165866ded55a82aa0c` / `main`（dirty tree 由
  source hash manifest 冻结；未 commit）
- Platform repo: `57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`（tracked-clean）
- Single repo: `c01f1f5af40ec25631aa11765a0f21e06834abc4`（tracked-clean）
- Experiment manifest: `5e841a9662fb49b1289951f490b094843740412f9845e122627e8d069fe1a871`
- Static contract: `d269f96c3c59fc15035ee8fcb0d47b97ae41db60f6ad00c726a8ae783e38c303`
- Source hash manifest: `0d240a7df3f442ded8eca4b0ae9bfc72b5995272fdfe501cd18824c67cef22ff`
  （12/12+3 OK）
- `two_uav_runner.py`（resource profile 采集）:
  `f818feec31d8ad8bc480b11d851580bd7d3fdb0fca571a5879bd83ba5bff41f2`
- `two_uav_collector.py`（occupancy snapshot）:
  `1685dcd64a442423fd3c00d4c1062e84e2fa667f01e2aee1009e195a7ad36eca`
- `two_uav_preflight.py`: `50fd9d421b64080f9b8616321a85032bd1b7ce4204276ba67ddd5fb2b69eac92`
- `two_uav_gt_mapper.py`: `c90383cb1083b554e50355405353d5a5e3ed3ce9a586a2d30962f8fc40a5c4e9`
- `px4_bridge.py`: `b673080c46916790431f257aea1a27fa8616adeb6b409fe22968e0316b57f34f`
- 公共 baseline manifest: `ce595cafba088955b38c4c9bd1d08f9af254dbfa0bf013481372a75e17980944`
- PX4 iris model template: `e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225`
- One-time approval package:
  `3b30d6591f22be886e188607875aea569fe4e8e0ec88a30a0cb1959f463db33f`
  （consumed；`stage: preflight`、`allowed_actions: [preflight]`、`max_uses: 1`、
  `issuance_id: preflight-20260822-occupancy-snapshot-resource-profile-1`；启动前无
  receipt、无 ACTIVE、环境探针 OK、负载 0.63/0.43/0.69）

## 执行结果（49/49 全部通过）

- `static_preflight.json`: **passed: true**，53/53；workspace probe 3/3。
- readiness/live 门全部通过（payload、TF、参数回读、logdir、**24 s soak**）。
- `final.metrics` available；**`final.safety` 通过**；无 abort.request。
- teardown：descendants 18、`survivors []`、clean。

## 双机 occupancy received/processed/coalesced/age/duration（转录）

occupancy 统计位于各机 `metrics.json` 的 `coverage` 子字典（collector `commit_occupancy_snapshot`）：

| 字段 | uav0 | uav1 |
|---|---|---|
| received | **35** | **46** |
| processed | **7** | **7** |
| coalesced | **28**（=35−7） | **38**（=46−7） |
| processed_age_s | 0.019 | 0.012 |
| message_age_s | 0.605 | 0.0 |
| last_processed_wall_s | 9275.686 | 9275.693 |
| last_processed_sim_s | None | None |
| callback_wall_duration_s（末值） | ~9 µs | ~6 µs |
| processing_wall_duration_s（末值） | ~17 µs | ~6 µs |

观察（转录）：**received 远大于 processed**（uav0 35→7、uav1 46→7，coalesced=received
−processed）——collector 收到大量 occupancy 消息但仅处理 7 条（合并/丢弃）。运行结束
时两机 message_age_s 均 <1 s（新鲜，未触发 stale）；该 received/processed 差异与
occupancy freshness 判断窗口的交互供 lead 分析。

## resource_usage.jsonl（五 role CPU/RSS/RT summary，转录末次采样）

| role | cpu_cores | rss_kb | threads |
|---|---|---|---|
| gazebo | **1.251** | **5 172 340（~5.2 GB）** | 258 |
| racer | **1.685** | **7 212 516（~7.2 GB）** | 47 |
| gt_mapper | 0.286 | 102 812 | 28 |
| bridges | 0.099 | 136 360 | 33 |
| collector | 0.030 | 54 108 | 48 |

- 系统内存：MemTotal 16.17 GB；运行中 MemAvailable 由 ~13 GB 降至 **~1.35 GB**——
  栈总内存占用 ~12 GB（racer+gazebo 占 ~12.4 GB RSS）；
- loadavg 采样期由 0.6 升至 5.97（1-min）；runroot 内 `rt_factor` 字段为采样间瞬时值
  （0.0/1.96-1.98 交替，因 sim 推进与采样窗口错位），整体 RT 以 fleet telemetry 为准
  ≈ 0.342。

## wall/sim 与 fleet/逐机指标

- wall/sim：sim `12.82 → 24.86`（12.04 sim s）/ wall 35.2 s，**RT ≈ 0.342**；全程
  telemetry complete、无 abort。
- **fleet**：`abort_reasons=[]`、`telemetry_completeness=true`、8/8 进程存活、
  `fleet_coverage_ratio=0.0090`、`minimum_inter_uav_distance_m=1.4507`（见 metrics）、
  `map_consistency_jaccard=0.7238`、`overlap_ratio=0.8463`、`fleet_contact_count=0`。
- **逐机**：uav0 `complete=true/stale=[]/crash=false/freeze=true/coverage=1856`；uav1
  `complete=true/stale=[]/crash=false/freeze=true/coverage=2141`（两机悬停，无 goal 预期）。

## Artifact hashes

- `manifest.yaml`:
  `5e841a9662fb49b1289951f490b094843740412f9845e122627e8d069fe1a871`
- `2uav_static.yaml`:
  `d269f96c3c59fc15035ee8fcb0d47b97ae41db60f6ad00c726a8ae783e38c303`
- `2uav_approval.yaml`:
  `3b30d6591f22be886e188607875aea569fe4e8e0ec88a30a0cb1959f463db33f`
- `runtime_environment.json`:
  `949a129f1ffa881082ca576093318bac3565185d263c3e38ce8758ac6a62b271`
- `workspace_environment_probe.json`:
  `0407d96611464f335ab30dc8127be7d39ea0e065ca6e55b475d3eff1e89a4577`
- `process_specs.json`:
  `aec8fe87f07076fe340d88f6696930bd231370bafd4329b290ce092d4028aefc`
- `static_preflight.json`:
  `6c26a86a81dfecb96ec4969ed8c42a8775174a2533ff86fb12ca42bdadbd86ee`
- `live_preflight.json`:
  `9b57074f0a0bf2e9ee3644a7ec1de42319a5445622f808cc41e3bcc8b95e9680`
- `stop_result.json`:
  `0090c835872f1b81d169b0ca1f2863b41f287eda14a8fb832ef516db1ca2c292`
- `resource_usage.jsonl`:
  `58866f750163ac5ef8eb0457b54d1f70a2bd7acf8f7d2b8112b4d37d9fe70edd`
- `uav0/metrics.json`:
  `642ad7464256174e96c84f6a8370531ad52037bed7c857f43fe6b90382debdbd`
- `uav1/metrics.json`:
  `78a415a549e45e63f7b31bf81608172ebacddf9ff113f38e5619d512e2f18c09`
- `fleet/metrics.json`:
  `3c35f9550041bc90d3da5d8b4b495236f2bc6e14541c050f05f327e8e4f9df43`

## Next gate

preflight **通过（49/49）**，occupancy 快照与资源画像已转录。按流程需交回 lead-planning
审核后另行签发后续 package；不得自动进入 smoke。package 已消费，不得复用；未修改任何
源码/参数/workspace/正式状态。
