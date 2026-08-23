# 2-UAV diagnostic preflight execution result

- Runroot: `RUN-20260821T183523Z-2uav-preflight`
- Command: `python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml`
- Exit code: `0`
- Decision: **`PREFLIGHT_PASS`** —— `live_preflight.json.passed = true`，**48/48 项检查
  全部通过**，无 abort（px4_bridge readiness 修复后，上一轮 uav0 未升空→bridge 崩溃
  的失败模式已消除；uav0 本轮正常升空 z≈1.45，px4_bridge_1 存活）。
- Smoke trigger: not issued（本 package 只批准 preflight；按流程需 lead 审核后另行签发
  smoke package）
- Active lifecycle after exit: absent —— teardown 证据完整落盘
  （`stop_result.json`：descendants 18、`survivors []`、`clean=true`）；无残留进程、
  无 ACTIVE 文件。
- 本 runroot 为最终 append-only 产物；一次性 approval package 已消费（receipt
  `b697986c…json` 落盘）

## Frozen identity（全部核对通过）

- Multi repo HEAD: `694a9c30aa9ee8f8f04b4f165866ded55a82aa0c` / `main`（dirty tree 由
  source hash manifest 冻结；未 commit）
- Platform repo: `57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`（tracked-clean）
- Single repo: `c01f1f5af40ec25631aa11765a0f21e06834abc4`（tracked-clean）
- Experiment manifest: `5e841a9662fb49b1289951f490b094843740412f9845e122627e8d069fe1a871`
- Static contract: `d106f0ca52bfcad5800d65e9a0f6692a074631cea965e96f5880e99d23461de0`
- Source hash manifest: `1a6e4caa4d784016e763942a601f22c29e1f247a23a582c7927106fc07943ef7`
  （12/12+3 OK——新增绑定 `px4_bridge.py` 与 single repo history 副本）
- `two_uav_gt_mapper.py`: `aa67881daa58dd13d3328ff40f0c93c59b71951943a99990493c4665f2d83cd9`
- `two_uav_collector.py`: `5b6cbd4b7ac027bc1f8d75c33dda3fd3e0c0ac877bfbde05f52eb2c8cf77b396`
- `two_uav_preflight.py`: `35969b9698fcd802b87c6370ebe9c8e14e50154f2439a3093916e26e67dcd345`
- Runner: `67b6a343ea841bbfa54e23d72b6643aa22dde62c8bf47a243f83617ab760d6a2`
- `px4_bridge.py`（bridge-readiness 修复，经 source hash manifest 绑定）:
  `b673080c46916790431f257aea1a27fa8616adeb6b409fe22968e0316b57f34f`
- 公共 baseline manifest: `ce595cafba088955b38c4c9bd1d08f9af254dbfa0bf013481372a75e17980944`
- PX4 iris model template: `e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225`
- One-time approval package:
  `b697986cae1f23ef987481394b9f168f39dc73cae3e2ee5decf4adc43a770e8a`
  （consumed；`stage: preflight`、`allowed_actions: [preflight]`、`max_uses: 1`、
  `issuance_id: preflight-20260822-bridge-readiness-retry-1`；启动前无 receipt、
  无 ACTIVE、环境探针 OK、负载 0.55/0.27/0.55）

## 执行结果（48/48 全部通过）

- `static_preflight.json`: **passed: true**，53/53；workspace probe 3/3。
- readiness 门全部通过：双机 payload、px4_bridge_1/2 节点。
- live 检查全部通过：required_topics、`/clock` 单发布者、`use_sim_time`、唯一 TF、
  两机 16 项参数回读、logdir 隔离。
- **24 s watchdog soak 通过**（"watchdog evidence complete"）。
- **`final.metrics`: available；`final.safety`: 通过**（"final safety metrics
  complete"）。
- teardown：descendants 18 全部 term、`survivors []`、clean。

## 修复验证（正向）

- **uav0 本轮正常升空**：position `[0.06, -0.08, 1.45]`（上轮卡在地面 z<0.12）；
  **px4_bridge_1 存活**（`process_liveness[/px4_bridge_1]=true`，上轮
  `physical hover readiness timeout` 崩溃已消除）；无 abort、无 process death。

## wall/sim 与 fleet/逐机指标

- wall/sim：sim `11.31 → 19.33`（8.02 sim s）/ wall 29.2 s，**RT ≈ 0.275**；
  `clock.monotonic=true`、`telemetry_completeness=true` 全程、`abort_reasons=[]`。

**fleet**：`abort_reasons=[]`、`telemetry_completeness=true`、
`tf_parents={uav0/base_link:[world], uav1/base_link:[world]}`、8/8 进程存活、
`fleet_coverage_ratio=0.0098`、`minimum_inter_uav_distance_m=1.4164`、
`map_consistency_jaccard=0.6507`、`overlap_ratio=0.9262`、`fleet_contact_count=0`、
`clock.last_sim_s=21.085`。

| 指标 | uav0 | uav1 |
|---|---|---|
| cloud / odometry | 114 / 114 | 117 / 117 |
| frontier | 895 | 1068 |
| health / occupancy | 13 / 31 | 13 / 46 |
| position | [0.06, -0.08, 1.45]（已升空） | [1.54, -0.08, 1.41] |
| telemetry_complete / stale | true / [] | true / [] |
| crash / freeze | false / true | false / false |
| coverage voxels / ratio | 1844 / 0.0069 | 2489 / 0.0093 |
| completion | false（无 goal，预期） | false |
| contact ground/inter_uav/obstacle | 0/0/0 | 0/0/0 |

## Artifact hashes

- `manifest.yaml`:
  `5e841a9662fb49b1289951f490b094843740412f9845e122627e8d069fe1a871`
- `2uav_static.yaml`:
  `d106f0ca52bfcad5800d65e9a0f6692a074631cea965e96f5880e99d23461de0`
- `2uav_approval.yaml`:
  `b697986cae1f23ef987481394b9f168f39dc73cae3e2ee5decf4adc43a770e8a`
- `runtime_environment.json`:
  `dc6115ff12d835b7e6dfd3a7a26295d514109df9a6d7ccaf9ece004a3ba5eb13`
- `workspace_environment_probe.json`:
  `0407d96611464f335ab30dc8127be7d39ea0e065ca6e55b475d3eff1e89a4577`
- `process_specs.json`:
  `3211cecd3f63695fd5092dedc4f0ab838905f8aeb581a2a02a36bcf8fdc49243`
- `static_preflight.json`:
  `fdda172f5e4efe68332320b90568c61f8cfb642a3b5e9ed213a85586afb787ad`
- `live_preflight.json`:
  `f2f82f573ddf764dd6dfd8cc757a016a3cc1db29c6494bb3da16e3511b91807a`
- `stop_result.json`:
  `0b065600317041a9f71e2ebbaf6cd0805c23ea40b3e0ea5eee29d573b51a6d30`
- `uav0/metrics.json`:
  `f1f8f2fcb298c35c8bd167670335fd78d1ced0c3943774127ef4afd9e10e01fe`
- `uav1/metrics.json`:
  `340d28464f8c07afb6ce547c184358fa7c37d33cc41f4785045f37e9364ff06d`
- `fleet/metrics.json`:
  `3f24bc6e91c25c358876f6bb39ed9d8e4caa59a11f33ce3dc51d4d9511f9ec28`
- `uav0/telemetry.jsonl`:
  `9821feff85bd65216b648a68682d573442c5835dfb3e0e9723d6fe5c0d2aa06a`
- `uav1/telemetry.jsonl`:
  `437c1d7673d876414c60bd8f86166b79e0fe5fded6a07c0d659c669cebef8ad7`
- `fleet/telemetry.jsonl`:
  `806867e318cda739072254c9af3e9efeea7e7c7deed70644fe0dbd4046851427`

## Next gate

preflight **通过（48/48）**，但按流程需交回 lead-planning 审核本 runroot 后，才可另行
签发 `stage: smoke` package；不得自动进入 smoke。package 已消费，不得复用；未修改
任何源码/参数/workspace/正式状态。
