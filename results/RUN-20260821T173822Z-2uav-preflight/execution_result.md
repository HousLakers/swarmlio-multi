# 2-UAV diagnostic preflight execution result

- Runroot: `RUN-20260821T173822Z-2uav-preflight`
- Command: `python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml`
- Exit code: `0`
- Decision: **`PREFLIGHT_PASS`** —— `live_preflight.json.passed = true`，**48/48 项检查
  全部通过**，无 abort（collector freshness 修复后，上一轮唯一失败的
  `final.safety` 已通过）。
- Smoke trigger: not issued（本 package 只批准 diagnostic preflight；按流程需 lead
  审核后另行签发 smoke package）
- Active lifecycle after exit: absent —— teardown 证据完整落盘
  （`stop_result.json`：descendants 18、`kill []`、`survivors []`、
  `identity_confirmed=true`、`master_port_released=true`、`clean=true`）；
  无残留进程、无 ACTIVE 文件。
- 本 runroot 为最终 append-only 产物；一次性 approval package 已消费（receipt
  `f1c7638e…json` 落盘）

## Frozen identity（全部核对通过）

- Multi repo HEAD: `694a9c30aa9ee8f8f04b4f165866ded55a82aa0c` / `main`（dirty tree 由
  source hash manifest 冻结；未 commit）
- Platform repo: `57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`（tracked-clean）
- Single repo: `c01f1f5af40ec25631aa11765a0f21e06834abc4`（tracked-clean）
- Experiment manifest: `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`
- Static contract: `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`
- Source hash manifest: `996eee46c5f4cba9f33bf773b64c4fc0a781095f748975920a506ec3c4f5e7a9`
  （12/12 OK）
- `two_uav_collector.py`（occupancy freshness 修复）:
  `5b6cbd4b7ac027bc1f8d75c33dda3fd3e0c0ac877bfbde05f52eb2c8cf77b396`
- Runner: `67b6a343ea841bbfa54e23d72b6643aa22dde62c8bf47a243f83617ab760d6a2`
- `two_uav_preflight.py`: `35969b9698fcd802b87c6370ebe9c8e14e50154f2439a3093916e26e67dcd345`
- `two_uav_gt_mapper.py`: `7ea6243d1518fc5e1a30f7b33c35378b645871fb201768e0a15f5c57f6d169ae`
- 公共 baseline manifest: `ce595cafba088955b38c4c9bd1d08f9af254dbfa0bf013481372a75e17980944`
- PX4 iris model template: `e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225`
- One-time approval package:
  `f1c7638e764e8dccad0e87e1b217c86561fc953dafdfec1c5912e13dcb5263c2`
  （consumed；`stage: preflight`、`allowed_actions: [preflight]`、`max_uses: 1`、
  `issuance_id: preflight-20260822-final-freshness-reference-1`；启动前无 receipt、
  无 ACTIVE、环境探针 OK、负载 0.61/0.86/0.86）

## 执行结果（48/48 全部通过）

- `static_preflight.json`: **passed: true**，53/53；workspace probe 3/3。
- readiness 门全部通过：双机 payload（raw/registered cloud+odom、frontier）、
  px4_bridge_1/2 节点。
- live 检查全部通过：required_topics、`/clock` 单发布者、`use_sim_time`、唯一 TF
  （`world→uav0/1/base_link`）、两机 16 项参数回读、logdir 隔离。
- **24 s watchdog soak 通过**（"watchdog evidence complete"）。
- **`final.metrics`: available；`final.safety`: 通过**（"final safety metrics complete"）
  —— 上轮唯一失败的 occupancy freshness 边界已随 collector 修复消除。
- 停栈：5 顶层 + 18 descendants 全部 term，`kill []`、`survivors []`、clean。

## wall/sim 与 fleet/逐机指标

- wall/sim：sim `13.18 → 25.19`（12.00 sim s）/ wall 35.6 s，**RT ≈ 0.338**；
  `clock.monotonic=true`、`telemetry_completeness=true` 全程、`abort_reasons=[]`。

**fleet**：`abort_reasons=[]`、`telemetry_completeness=true`、
`tf_parents={uav0/base_link:[world], uav1/base_link:[world]}`、8/8 进程存活、
`lost_after_seen=[]`、`never_seen=[]`、`fleet_coverage_ratio=0.0132`、
`minimum_inter_uav_distance_m=1.4583`、`map_consistency_jaccard=0.7307`、
`overlap_ratio=0.9046`、`fleet_contact_count=0`、`clock.last_sim_s=25.584`。

| 指标 | uav0 | uav1 |
|---|---|---|
| cloud / odometry | 144 / 144 | 144 / 144 |
| frontier | 774 | 865 |
| health / occupancy | 15 / 25 | 15 / 26 |
| telemetry_complete / stale | true / [] | true / [] |
| crash / freeze | false / true（无 goal） | false / true |
| coverage voxels / ratio | 2871 / 0.0107 | 3280 / 0.0122 |
| completion | false（无 goal，预期） | false |
| contact ground/inter_uav/obstacle | 0/0/0 | 0/0/0 |

## Artifact hashes

- `manifest.yaml`:
  `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`
- `2uav_static.yaml`:
  `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`
- `2uav_approval.yaml`:
  `f1c7638e764e8dccad0e87e1b217c86561fc953dafdfec1c5912e13dcb5263c2`
- `runtime_environment.json`:
  `6d90a379ed64a1f2454a3d37fdbb87e8fbffe04a8e2f9d3a38fa0da5b1dc9758`
- `workspace_environment_probe.json`:
  `0407d96611464f335ab30dc8127be7d39ea0e065ca6e55b475d3eff1e89a4577`
- `process_specs.json`:
  `19938dec754d003f7c46f417a3f14b8df9e8a2c99a21ee2b39e3363b87228ee0`
- `static_preflight.json`:
  `d3ee52bba124e0518d16dbabd1201faa80b6f03657a7fc11328c5a212a2ac51e`
- `live_preflight.json`:
  `3d61bab1bfbdd7471847d878dd5926c99958b9962d501012b81ccdfef81e2a72`
- `stop_result.json`:
  `300562a8acc33303ff970ed31e5071bea02661d4c758f823bcdb8d2bc49b427f`
- `uav0/metrics.json`:
  `4a9354208374329da7382c037571ea487ce4895401c47ea2edaf957aab15ebff`
- `uav1/metrics.json`:
  `c27d8a931db7bc8089fc666c9f0137426aabf5d4ea3173e38f0ed9768345f43e`
- `fleet/metrics.json`:
  `54adcc1bdafa389d54e27150e0d326007217646558c0b31c6de62d13b3b3d932`
- `uav0/telemetry.jsonl`:
  `e6f012c1fd9a5652c296b680908d378eb2d00d0b0455d7cec695106d88bd3d3f`
- `uav1/telemetry.jsonl`:
  `760cefd0529f9cd57553c5561ed8d2b54f14cf3eee1ae93cdb2b5d078a5fe1d3`
- `fleet/telemetry.jsonl`:
  `fea483fe3b852e28d873d8360be7beedc4dc18d7aeecb22579cd25508454b8a6`

## Next gate

preflight **通过（48/48）**，但按流程需交回 lead-planning 审核本 runroot 后，才可另行
签发 `stage: smoke` package；不得自动进入 smoke。package 已消费，不得复用；未修改
任何源码/参数/workspace/正式状态。
