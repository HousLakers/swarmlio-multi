# 2-UAV diagnostic preflight execution result

- Runroot: `RUN-20260821T190032Z-2uav-preflight`
- Command: `python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml`
- Exit code: `0`
- Decision: **`PREFLIGHT_PASS`** —— `live_preflight.json.passed = true`，**48/48 项检查
  全部通过**，无 abort。peer-inflation-endpoint-mask 诊断已采集转录。
- Smoke trigger: not issued（本 package 只批准 diagnostic preflight；按流程需 lead
  审核后另行签发）
- Active lifecycle after exit: absent —— teardown 证据完整
  （`stop_result.json`：descendants 18、`survivors []`、`clean=true`）；无残留进程、
  无 ACTIVE 文件。
- 本 runroot 为最终 append-only 产物；一次性 approval package 已消费（receipt
  `6ce1ec44…json` 落盘）

## Frozen identity（全部核对通过）

- Multi repo HEAD: `694a9c30aa9ee8f8f04b4f165866ded55a82aa0c` / `main`（dirty tree 由
  source hash manifest 冻结；未 commit）
- Platform repo: `57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`（tracked-clean）
- Single repo: `c01f1f5af40ec25631aa11765a0f21e06834abc4`（tracked-clean）
- Experiment manifest: `5e841a9662fb49b1289951f490b094843740412f9845e122627e8d069fe1a871`
- Static contract: `d106f0ca52bfcad5800d65e9a0f6692a074631cea965e96f5880e99d23461de0`
- Source hash manifest: `a932046b25198a692d1932f4cf3b315692b6d4a85d137cf4f5e21b2ee0f6b5c5`
  （12/12+3 OK）
- `two_uav_gt_mapper.py`（peer-inflation-endpoint-mask 诊断）:
  `c90383cb1083b554e50355405353d5a5e3ed3ce9a586a2d30962f8fc40a5c4e9`
- `two_uav_collector.py`: `5b6cbd4b7ac027bc1f8d75c33dda3fd3e0c0ac877bfbde05f52eb2c8cf77b396`
- `two_uav_preflight.py`: `35969b9698fcd802b87c6370ebe9c8e14e50154f2439a3093916e26e67dcd345`
- Runner: `67b6a343ea841bbfa54e23d72b6643aa22dde62c8bf47a243f83617ab760d6a2`
- `px4_bridge.py`: `b673080c46916790431f257aea1a27fa8616adeb6b409fe22968e0316b57f34f`
- 公共 baseline manifest: `ce595cafba088955b38c4c9bd1d08f9af254dbfa0bf013481372a75e17980944`
- PX4 iris model template: `e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225`
- One-time approval package:
  `6ce1ec44d6b71d78aac31e6e63e44a4da7e6460e7ca95f677c776e921e07e5b3`
  （consumed；`stage: preflight`、`allowed_actions: [preflight]`、`max_uses: 1`、
  `issuance_id: preflight-20260822-peer-inflation-endpoint-mask-1`；启动前无 receipt、
  无 ACTIVE、环境探针 OK、负载 0.96/0.88/1.30）

## 执行结果（48/48 全部通过）

- `static_preflight.json`: **passed: true**，53/53；workspace probe 3/3。
- readiness/live 门全部通过（payload、TF、参数回读、logdir、**24 s soak**）。
- `final.metrics` available；**`final.safety` 通过**；无 abort.request。
- teardown：descendants 18、`survivors []`、clean。

## peer-inflation-endpoint-mask 诊断（转录自 `logs/gt_mapper.log`，原样；判定归 lead）

**第二快照（sim 20.0）**：

```text
uav0 source (peer=uav1): peer_candidates=1172  peer_endpoint_candidates=1172
                         peer_ray_candidates=5317  peer_removed_points=10033
                         peer_unavailable_body_candidates=168  peer_unavailable_inflation_candidates=779
                         published_points=365130  registered_points=375163
uav1 source (peer=uav0): peer_candidates=126  peer_endpoint_candidates=126
                         peer_ray_candidates=740  peer_removed_points=12287
                         peer_unavailable_body_candidates=0  peer_unavailable_inflation_candidates=66
                         published_points=385254  registered_points=397541
```

- **发布恒等式成立**：uav0 `365130 == 375163 − 10033` ✓；uav1 `385254 == 397541 −
  12287` ✓。
- 本轮 `peer_removed_points`（10033/12287）为 endpoint∪ray∪unavailable 的并集口径，
  大于 ray candidates（5317/740）——与上轮（removed==ray）口径不同，转录供 lead 核对
  语义。
- **uav1_hover_voxels 本轮为空** `{}`（上轮 smoke/preflight 非空）——转录观察，是否与
  endpoint-mask 过滤/记录窗口有关由 lead 判定。

## wall/sim 与 fleet/逐机指标

- wall/sim：sim `13.40 → 25.40`（12.00 sim s）/ wall 35.2 s，**RT ≈ 0.341**；全程
  telemetry complete、无 abort。
- **fleet**：`abort_reasons=[]`、`telemetry_completeness=true`、8/8 进程存活、
  `fleet_coverage_ratio=0.0085`、`minimum_inter_uav_distance_m=1.4507`、
  `map_consistency_jaccard=0.7238`、`overlap_ratio=0.8463`、`fleet_contact_count=0`、
  `clock.last_sim_s=25.743`。
- **逐机**：uav0 `complete=true/stale=[]/crash=false/freeze=true/coverage=1945/pos
  [-0.01,-0.02,1.49]`（悬停）；uav1 `complete=true/stale=[]/crash=false/freeze=true/
  coverage=1975/pos [1.49,0.0,1.49]`（悬停）。

## Artifact hashes

- `manifest.yaml`:
  `5e841a9662fb49b1289951f490b094843740412f9845e122627e8d069fe1a871`
- `2uav_static.yaml`:
  `d106f0ca52bfcad5800d65e9a0f6692a074631cea965e96f5880e99d23461de0`
- `2uav_approval.yaml`:
  `6ce1ec44d6b71d78aac31e6e63e44a4da7e6460e7ca95f677c776e921e07e5b3`
- `runtime_environment.json`:
  `76ad20c71bee202e4ee0290f8462b7cdf245719cc3035087e7f8f0e1e2fcb221`
- `workspace_environment_probe.json`:
  `0407d96611464f335ab30dc8127be7d39ea0e065ca6e55b475d3eff1e89a4577`
- `process_specs.json`:
  `8241f161f011dd53029b8d0979e698172317b3d1da9c69bdb3966d3b6bb00651`
- `static_preflight.json`:
  `9f410d9634e64762bfdc974668695592b9ac1ba00b506d9d6e879e308550e22f`
- `live_preflight.json`:
  `9825075064bfd13776ba8612da057057de5eddf690a49c68aa08c653843047ab`
- `stop_result.json`:
  `b445ad9be42d4915b96294da89e5c9026a370853e5f029bd3de46d315cfa6005`
- `uav0/metrics.json`:
  `fa8a175c20aafcc6b258860f17cc051d3c79d92e366612882efb4a044a3400e8`
- `uav1/metrics.json`:
  `ef99fc1667b86ce25ec929bafe50da1fec3fc02363ad496684b7a1ff49b91325`
- `fleet/metrics.json`:
  `21b16cb8d8f5b39ed4ea487222cc9443a59f0dde2f269c3cab213835cab4a46c`
- `logs/gt_mapper.log`:
  `87febb59a1faa2f41f3d93c1ec2db1ab72c969be1c9373ca4246014c4ec3619c`

## Next gate

preflight **通过（48/48）**，诊断已转录。按流程需交回 lead-planning 审核本 runroot
后，才可另行签发后续 package；不得自动进入 smoke。package 已消费，不得复用；未修改
任何源码/参数/workspace/正式状态。
