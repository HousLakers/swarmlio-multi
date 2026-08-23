# 2-UAV odom-alias diagnostic preflight execution result

- Runroot: `RUN-20260821T095346Z-2uav-preflight`
- Command: `python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml`
- Exit code: `0`
- Decision: **`PREFLIGHT_PASS`** —— `live_preflight.json.passed = true`，48/48 项检查
  全部通过，无 abort。诊断快照与计数已转录；诊断门逐项核对见下（gate 5 未满足，需
  lead 判定）。
- Smoke trigger: not issued（本 package 只批准 diagnostic preflight）
- Active lifecycle after exit: absent（5 进程全部 sigterm+sigkill，无 ACTIVE 文件）
- 本 runroot 为最终 append-only 产物；一次性 approval package 已消费（receipt
  `296d93cc…json` 落盘）

## Frozen identity（全部核对通过）

- Multi repo HEAD: `694a9c30aa9ee8f8f04b4f165866ded55a82aa0c` / `main`（dirty tree 由
  source hash manifest 冻结；未 commit）
- Platform repo: `57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`（tracked-clean）
- Single repo: `c01f1f5af40ec25631aa11765a0f21e06834abc4`（tracked-clean）
- Experiment manifest: `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`
- Static contract: `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`
- Source hash manifest: `2d99a213de37c8228ddbb86a12d748b1b94480289be974d846506fc95efc7788`
  （12/12 OK）
- `two_uav_gt_mapper.py`（odom alias 修复 + peer filter 计数）:
  `2c4ab51bdecc26d03030ef93631f2376ba991178ea915ab787900096bb0df6ff`
- `two_uav_collector.py`: `2343f0b9024878ea9a5c58d6e4cb941cd99b3950fd3a4184be355361d134aeb4`
- Runner: `9e3141efafe8a6f618075d8fe6281b9a41e12f5542cad6d7def25fc377150621`
- 公共 baseline manifest: `ce595cafba088955b38c4c9bd1d08f9af254dbfa0bf013481372a75e17980944`
- PX4 iris model template: `e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225`
- One-time approval package:
  `296d93cc0fade2bc2a977da067495a78a502d132de2fd6cb2d58e1bc5cb4fa03`（consumed；
  `stage: preflight`、`allowed_actions: [preflight]`、`max_uses: 1`；启动前无 receipt、
  无 active lifecycle、环境探针 OK）

## 执行结果（48/48 全部通过）

- `static_preflight.json`: **passed: true**，53/53。
- `workspace_environment_probe.json`: 三项全部 `ok: true`。
- Readiness/live 门全部通过：双机 payload、唯一 TF、参数回读 16×2、logdir 隔离、
  **24 s no-goal soak 通过**、`final.metrics` available、`final.safety` 通过。
- 停栈干净：5 进程 sigterm+sigkill；无 abort.request；无残留进程。

## wall/sim 推进量与 RT factor

- fleet telemetry 8 行：sim `13.01 → 25.03`（推进 12.02 sim s），wall `19858.4 →
  19892.6`（34.2 s），**RT factor ≈ 0.352**；
- `clock.monotonic=true`、`telemetry_completeness=true` 全程、`abort_reasons=[]`。

## 诊断快照（转录自 `logs/gt_mapper.log`，第二快照 sim 20.005 原样）

**mapper inputs/outputs（两批）**：

```text
[10.765] uav1 mapper inputs={'scan': 98, 'odom': 274, 'pairs': 91, 'empty_scan': 0, 'empty_filtered': 0} outputs=91
[10.765] uav0 mapper inputs={'scan': 100, 'odom': 282, 'pairs': 94, 'empty_scan': 0, 'empty_filtered': 0} outputs=94
[20.000] uav1 mapper inputs={'scan': 191, 'odom': 551, 'pairs': 184, 'empty_scan': 0, 'empty_filtered': 0} outputs=184
[20.000] uav0 mapper inputs={'scan': 192, 'odom': 559, 'pairs': 186, 'empty_scan': 0, 'empty_filtered': 0} outputs=186
```

**mapper_body_diagnostic（4 条，原样转录；第一快照 sim 10.765、第二快照 sim 20.005）**：

```json
{"geometry_id":"iris.sdf.jinja:e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225","peer":"uav0","peer_candidates":399,"peer_pose_status":{"available":81,"stale":10},"peer_preserved_unavailable_points":22446,"peer_removed_points":399,"published_points":201429,"raw_points":2184000,"registered_points":201828,"self_candidates":0,"self_pose_status":{"available":87,"stale":4},"source":"uav1"}
{"geometry_id":"iris.sdf.jinja:e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225","peer":"uav1","peer_candidates":159,"peer_pose_status":{"available":87,"missing":3,"stale":4},"peer_preserved_unavailable_points":17097,"peer_removed_points":159,"published_points":209956,"raw_points":2256000,"registered_points":210115,"self_candidates":0,"self_pose_status":{"available":93,"stale":1},"source":"uav0"}
{"geometry_id":"iris.sdf.jinja:e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225","peer":"uav0","peer_candidates":701,"peer_pose_status":{"available":164,"stale":20},"peer_preserved_unavailable_points":39062,"peer_removed_points":701,"published_points":353171,"raw_points":4416000,"registered_points":353872,"self_candidates":0,"self_pose_status":{"available":178,"stale":6},"source":"uav1"}
{"geometry_id":"iris.sdf.jinja:e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225","peer":"uav1","peer_candidates":195,"peer_pose_status":{"available":179,"missing":3,"stale":4},"peer_preserved_unavailable_points":17097,"peer_removed_points":195,"published_points":363302,"raw_points":4464000,"registered_points":363497,"self_candidates":0,"self_pose_status":{"available":185,"stale":1},"source":"uav0"}
```

## 诊断门逐项核对（机械核对 + 原始转录；结论判定归 lead）

1. **第二快照 peer pose available 占比 > 50%（双向）**：
   - uav0 source 视 uav1：`available 179 / (179+3+4) = 96.2%`；
   - uav1 source 视 uav0：`available 164 / (164+20) = 89.1%`；
   - 两条均 > 50% → **满足**。（对比上一轮 uav0 视角仅 2/187，odom alias 修复后双向
     peer pose 可用率大幅改善——转录观察，不做假设结论。）
2. **第二快照 pre-filter `peer_candidates > 0`（双向）**：uav0 视 uav1 = 195；
   uav1 视 uav0 = 701；均 > 0 → **满足**。
3. **累计 `peer_removed_points == peer_candidates` 且 `published_points ==
   registered_points - peer_removed_points`**：
   - uav0：removed 195 == candidates 195；published 363302 == 363497 − 195 ✓；
   - uav1：removed 701 == candidates 701；published 353171 == 353872 − 701 ✓；
   - → **满足**。
4. **unavailable scan 未删点，preserved 计数可审核**：
   - uav0 视 uav1：`peer_preserved_unavailable_points = 17097`（两快照一致），
     peer_pose_status 含 `missing:3`（两快照一致）；
   - uav1 视 uav0：`peer_preserved_unavailable_points = 22446 → 39062`（增加），
     peer_pose_status 无 missing；
   - 计数存在且随运行增长/一致 → **可审核（转录）**。
5. **sim≥15 两出生点 `Astar vehicle start is inside inflated occupancy` 不再持续出现**：
   - `logs/racer.log` 该警告共 **222 次**，首次 sim 9.391、**末次 sim 25.146**，末次
     start 位置为 uav1 悬停点 `(1.54529, -0.0939654, 1.47009)`；
   - 该警告在 sim≥15 仍持续出现 → **未满足**（原始计数转录；原因判定归 lead）。
6. **wall/sim/RT factor**：sim 推进 12.02 s / wall 34.2 s → **RT ≈ 0.352**
   （保留既有 RT≈0.33 负载风险）。

## fleet / 逐机指标

**fleet**：`abort_reasons=[]`、`telemetry_completeness=true`、
`tf_parents={uav0/base_link:[world], uav1/base_link:[world]}`、8/8 进程存活、
`fleet_coverage_ratio=0.0113`、`minimum_inter_uav_distance_m=1.4610`、
`map_consistency_jaccard=0.7505`、`overlap_ratio=0.9172`、`fleet_contact_count=0`。

| 指标 | uav0 | uav1 |
|---|---|---|
| telemetry_complete / stale | true / [] | true / [] |
| crash / freeze | false / true（无 goal） | false / true |
| coverage voxels | 2476 | 2821 |
| contact ground/inter_uav/obstacle | 0/0/0 | 0/0/0 |

## Artifact hashes

- `manifest.yaml`:
  `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`
- `2uav_static.yaml`:
  `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`
- `2uav_approval.yaml`:
  `296d93cc0fade2bc2a977da067495a78a502d132de2fd6cb2d58e1bc5cb4fa03`
- `runtime_environment.json`:
  `ac685c6cf62cda7d38d0cbffea9db4a4d76b4c8ee43eed9ee1e2bb5e85e49fc5`
- `workspace_environment_probe.json`:
  `0407d96611464f335ab30dc8127be7d39ea0e065ca6e55b475d3eff1e89a4577`
- `process_specs.json`:
  `29e2f923ce6f4344925f8a560db7c912c4f36ccf7027c2128f99fe452b75e34f`
- `static_preflight.json`:
  `ec2a81636aa9bebe6d0f36f067bebe64a00f6dfee898cd7c657c1c16fce340e5`
- `live_preflight.json`:
  `b364478f66f58b709cc8ddb24eb8165b70127b018ec7e614ad0b0d50dd335726`
- `stop_result.json`:
  `e7daa805305059994b482c57f7f5db588a51451d7ec6681ebe11a2e703e2f0a9`
- `uav0/metrics.json`:
  `47e18aea89a52f3d27ebd65c94d5bd1ebfbe719482bcfb45fbbfc279494462c7`
- `uav1/metrics.json`:
  `49afd4cc3280d8138f49769e54daecbcbe9b673ba5fd4132bf3105091ac77982`
- `fleet/metrics.json`:
  `2e85639b6072d5ab528be4b59ed781b08784677a4e12e1949b1fd86afa812b4c`
- `logs/gt_mapper.log`:
  `f89313bb1e088edf4220ccdec4a41cb78c880c18cd24b118b006383ae834ff51`
- `logs/racer.log`:
  `5034e62ed34ffc53c1238bda837af444fed95a0fa45a9be3765820943625796f`

## Next gate

基础门 48/48 通过；诊断门 1-4、6 满足/可审核，**诊断门 5 未满足**（`Astar vehicle
start is inside inflated occupancy` 在 sim≥15 持续出现至 sim 25.146）。按第 21 节：
基础门通过但任一诊断门缺证或失败，仍必须回 lead，不得进入 smoke。package 已消费，
不得复用；未修改任何源码/参数/workspace/正式状态。
