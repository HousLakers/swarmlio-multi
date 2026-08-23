# 2-UAV diagnostic preflight execution result

- Runroot: `RUN-20260821T091542Z-2uav-preflight`
- Command: `python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml`
- Exit code: `0`
- Decision: **`PREFLIGHT_PASS`** —— `live_preflight.json.passed = true`，48/48 项检查
  全部通过，无 abort。诊断交付门满足：`logs/gt_mapper.log` 含 uav0/uav1 各 2 条可解析
  `mapper_body_diagnostic=<JSON>`（geometry_id 绑定、registered_points 非零、self/peer
  candidate 累计值与 pose-status counters 齐全）。
- Smoke trigger: not issued（本 package 只批准 diagnostic preflight）
- Active lifecycle after exit: absent（5 进程全部 sigterm+sigkill，无 ACTIVE 文件）
- 本 runroot 为最终 append-only 产物；一次性 approval package 已消费（receipt
  `aef23aef…json` 落盘）

## Frozen identity（全部核对通过）

- Multi repo HEAD: `694a9c30aa9ee8f8f04b4f165866ded55a82aa0c` / `main`（dirty tree 由完整
  source hash manifest 冻结；未 commit）
- Platform repo: `57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`（tracked-clean）
- Single repo: `c01f1f5af40ec25631aa11765a0f21e06834abc4`（tracked-clean）
- Experiment manifest: `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`
- Static contract: `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`
- Source hash manifest: `a962c13024a4cdbadfc3a667ead557214af249698afbfcbedd69749af69c5f03`
  （12/12 OK）
- `two_uav_collector.py`: `2343f0b9024878ea9a5c58d6e4cb941cd99b3950fd3a4184be355361d134aeb4`
- `two_uav_gt_mapper.py`（含 mapper_body_diagnostic）:
  `38645cdac77388f8546fe94f2c9d4f332d727500260d4ef2329e19d9f818a690`
- Runner: `9e3141efafe8a6f618075d8fe6281b9a41e12f5542cad6d7def25fc377150621`
- 公共 baseline manifest: `ce595cafba088955b38c4c9bd1d08f9af254dbfa0bf013481372a75e17980944`
- PX4 iris model template: `e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225`
- One-time approval package:
  `aef23aefd98998693f57e4328010363bd849dfae794ab7691ff5b1b7baa57079`（consumed；
  `stage: preflight`、`allowed_actions: [preflight]`、`max_uses: 1`；启动前无 receipt、
  无 active lifecycle、环境探针 OK）

## 执行结果（48/48 全部通过）

- `static_preflight.json`: **passed: true**，53/53。
- `workspace_environment_probe.json`: 三项全部 `ok: true`。
- Readiness/live 门全部通过：双机 payload、唯一 TF（`world→uav0/1/base_link`）、参数
  回读 16×2、logdir 隔离、**24 s no-goal soak 通过**、`final.metrics` available、
  `final.safety` 通过。
- 停栈干净：5 进程 sigterm+sigkill；无 abort.request；无残留进程。

## wall/sim 推进量与 RT factor

- fleet telemetry 7 行：sim `12.92 → 24.93`（推进 12.02 sim s），wall `17576.0 →
  17612.1`（36.1 s），**RT factor ≈ 0.333**；
- `clock.monotonic=true` 全程；`telemetry_completeness=true` 全程；`abort_reasons=[]` 全程。

## 诊断交付（转录自 `logs/gt_mapper.log` 原始值，未作判断/未实施点过滤）

**mapper inputs/outputs（原样）**：

```text
[10.765] uav0 mapper inputs={'scan': 100, 'odom': 282, 'pairs': 94, 'empty_scan': 0, 'empty_filtered': 0} outputs=94
[10.765] uav1 mapper inputs={'scan': 93, 'odom': 276, 'pairs': 87, 'empty_scan': 0, 'empty_filtered': 0} outputs=87
[20.013] uav1 mapper inputs={'scan': 183, 'odom': 553, 'pairs': 177, 'empty_scan': 0, 'empty_filtered': 0} outputs=177
[20.013] uav0 mapper inputs={'scan': 192, 'odom': 560, 'pairs': 187, 'empty_scan': 0, 'empty_filtered': 0} outputs=186
```

**mapper_body_diagnostic JSON（4 条，原样转录）**：

```json
{"geometry_id":"iris.sdf.jinja:e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225","peer":"uav1","peer_candidates":0,"peer_pose_status":{"missing":3,"stale":91},"raw_points":2256000,"registered_points":210115,"self_candidates":0,"self_pose_status":{"available":94},"source":"uav0"}
{"geometry_id":"iris.sdf.jinja:e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225","peer":"uav0","peer_candidates":381,"peer_pose_status":{"available":87},"raw_points":2088000,"registered_points":192978,"self_candidates":0,"self_pose_status":{"available":87},"source":"uav1"}
{"geometry_id":"iris.sdf.jinja:e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225","peer":"uav0","peer_candidates":712,"peer_pose_status":{"available":177},"raw_points":4248000,"registered_points":339868,"self_candidates":0,"self_pose_status":{"available":177},"source":"uav1"}
{"geometry_id":"iris.sdf.jinja:e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225","peer":"uav1","peer_candidates":0,"peer_pose_status":{"available":2,"missing":3,"stale":182},"raw_points":4488000,"registered_points":365764,"self_candidates":0,"self_pose_status":{"available":187},"source":"uav0"}
```

按第 18 节交付门逐项核对（仅转录，不下结论）：
- geometry_id 全部绑定 `iris.sdf.jinja:e8ae6d24…`（与本批准 frozen model identity 一致）；
- `registered_points` 非零：uav0 210115→365764、uav1 192978→339868；
- `self_candidates` 均为 0；`peer_candidates`：uav0→uav1 视角 0（两条）、uav1→uav0
  视角 381→712（两条）；
- pose-status counters：uav0 视 uav1 为 `{missing:3, stale:91}` → `{available:2,
  missing:3, stale:182}`；uav1 视 uav0 为 `{available:87}` → `{available:177}`。

（执行器仅转录原始值；peer-body 假设成立与否、是否需要点过滤由 lead/sol 判定。）

## fleet / 逐机指标

**fleet**：`abort_reasons=[]`、`telemetry_completeness=true`、
`tf_parents={uav0/base_link:[world], uav1/base_link:[world]}`、8/8 进程存活、
`lost_after_seen=[]`、`fleet_coverage_ratio=0.0105`、
`minimum_inter_uav_distance_m=1.4753`、`map_consistency_jaccard=0.7839`、
`overlap_ratio=0.8913`、`fleet_contact_count=0`、`clock.last_sim_s=25.214`。

| 指标 | uav0 | uav1 |
|---|---|---|
| cloud / odometry | 143 / 144 | 141 / 141 |
| frontier | 853 | 951 |
| health / occupancy | 16 / 30 | 16 / 31 |
| telemetry_complete / stale | true / [] | true / [] |
| crash / freeze | false / true（无 goal） | false / true |
| coverage voxels / ratio | 2494 / 0.0093 | 2565 / 0.0095 |
| completion | false（无 goal，预期） | false |
| contact ground/inter_uav/obstacle | 0/0/0 | 0/0/0 |

## Artifact hashes

- `manifest.yaml`:
  `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`
- `2uav_static.yaml`:
  `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`
- `2uav_approval.yaml`:
  `aef23aefd98998693f57e4328010363bd849dfae794ab7691ff5b1b7baa57079`
- `runtime_environment.json`:
  `ac4a1f103383f3007e9372bbec76f143c6aad665276527aea7bea547d41e2853`
- `workspace_environment_probe.json`:
  `0407d96611464f335ab30dc8127be7d39ea0e065ca6e55b475d3eff1e89a4577`
- `process_specs.json`:
  `a03e710cd49f69e604dfd31babbdf0ff07e1dca885f1bcf6c2d15494c247ac4a`
- `static_preflight.json`:
  `7efaa9134eb4057a394a8d8e432d87a300325d7f2e7e5f249738318b2b465890`
- `live_preflight.json`:
  `60bf1d94ab98960fea12d40a32084e36f022363e717056c9e12b26cbfc80cfff`
- `stop_result.json`:
  `e7daa805305059994b482c57f7f5db588a51451d7ec6681ebe11a2e703e2f0a9`
- `uav0/metrics.json`:
  `86651b2e34efb4111f6ae832361352bb93ec6805687fc5c8c1ffb9d151f3bec3`
- `uav1/metrics.json`:
  `4d626c9e9d89639ad2d84243af6359d5f4b598e00b8b65840575d2719e960b36`
- `fleet/metrics.json`:
  `c964d8952af4947c31fcea2c98ce75f23a97bba1581c5f2040d4f93f3849d3c7`
- `logs/gt_mapper.log`:
  `bf1ae38e645b11cd5f2118868da24320005b4e8b812e2f5a5020e0924fe26988`

## Next gate

preflight 通过且诊断交付门满足，但按第 18 节与交接指令：**交回 lead-planning** 审核
（诊断原始值转录完成，未作 peer-body 假设判断、未实施点过滤、未修改任何代码/参数）。
smoke 未授权。package 已消费，不得复用。
