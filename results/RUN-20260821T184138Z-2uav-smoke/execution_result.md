# 2-UAV smoke execution result

- Runroot: `RUN-20260821T184138Z-2uav-smoke`
- Command: `python3 scripts/two_uav_runner.py launch --manifest experiments/manifests/2uav_smoke.yaml`
- Exit code: `2`
- Decision: **`SMOKE_FAIL_ABORT`** —— goal 已发布；uav0 正常执行（pos_cmd/ACK 2540、
  移动 21.68 m）；**uav1 未接令**（起点 inflated-occupancy 无法规划），sim 56.26
  时 uav1 occupancy 通道停更 >5 s → collector fail-closed abort
  （`corrupted_telemetry:uav1:freshness`）。推进至 **sim 56.26/120（~47%）**（首次 smoke
  仅 32.39）。
- Active lifecycle after exit: absent —— teardown 证据完整
  （`execution_result.json` stop：top_level 5、descendants 18、`kill []`、
  `survivors []`、`identity_confirmed=true`、`master_port_released=true`、`clean=true`）；
  无残留进程、无 ACTIVE 文件。
- 本 runroot 为最终 append-only 产物；smoke approval package 已消费（receipt
  `a798ca4a…json` 落盘）

## Frozen identity（全部核对通过）

- Multi repo HEAD: `694a9c30aa9ee8f8f04b4f165866ded55a82aa0c` / `main`（dirty tree 由
  source hash manifest 冻结；未 commit）
- Platform repo: `57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`（tracked-clean）
- Single repo: `c01f1f5af40ec25631aa11765a0f21e06834abc4`（tracked-clean）
- Experiment manifest: `5e841a9662fb49b1289951f490b094843740412f9845e122627e8d069fe1a871`
- Static contract: `d106f0ca52bfcad5800d65e9a0f6692a074631cea965e96f5880e99d23461de0`
- Source hash manifest: `1a6e4caa4d784016e763942a601f22c29e1f247a23a582c7927106fc07943ef7`
  （12/12+3 OK，含 px4_bridge.py 绑定）
- Runner: `67b6a343ea841bbfa54e23d72b6643aa22dde62c8bf47a243f83617ab760d6a2`
- `two_uav_collector.py`: `5b6cbd4b7ac027bc1f8d75c33dda3fd3e0c0ac877bfbde05f52eb2c8cf77b396`
- `two_uav_gt_mapper.py`: `aa67881daa58dd13d3328ff40f0c93c59b71951943a99990493c4665f2d83cd9`
- `two_uav_preflight.py`: `35969b9698fcd802b87c6370ebe9c8e14e50154f2439a3093916e26e67dcd345`
- `px4_bridge.py`: `b673080c46916790431f257aea1a27fa8616adeb6b409fe22968e0316b57f34f`
- 公共 baseline manifest: `ce595cafba088955b38c4c9bd1d08f9af254dbfa0bf013481372a75e17980944`
- PX4 iris model template: `e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225`
- Smoke approval package:
  `a798ca4a30cab5972bc652074433f471fd6bf85dc0f09d3a87e3f88f2bcb3874`
  （consumed；`stage: smoke`、`allowed_actions: [launch]`、`max_uses: 1`、
  `issuance_id: smoke-20260822-bridge-readiness-and-occupancy-1`；启动前无 receipt、
  无 ACTIVE、环境探针 OK、负载 1.48/1.37/1.07）

## 执行阶段

1. 静态 53/53、workspace probe 3/3；启动前 live 门 46/46（readiness、payload、TF、
   参数回读、24 s soak）通过。
2. goal 发布（"publishing and latching message for 3.0 seconds"）→ 120 sim s 监视。
3. 运行至 **sim 56.26**（23 行 telemetry；前 22 行 complete、无 abort）；sim 56.26
   uav1 occupancy 通道停更 → collector fail-closed abort。
4. 停栈：teardown 完整（descendants 18、kill []、survivors []、clean）。

## 逐机报告（交接要求）

| 指标 | uav0 | uav1 |
|---|---|---|
| trajectory | **8** | **0** |
| pos_cmd / ACK | **2540 / 2540**（last_ack_id=8） | **0 / 0**（last_ack_id=None） |
| ack_timeout | count=0 | count=0 |
| 运动（path_length） | **21.681 m**（freeze=false） | 3.64 m（**freeze=true**，悬停） |
| 末位置 | [6.21, -1.23, 2.56]（已移动） | [1.32, 0.12, 1.50]（悬停位） |
| coverage voxels / ratio | 8129 / 0.0302 | 8786 / 0.0327 |
| telemetry complete / stale | true / [] | true / []（abort 时线 22 stale=['occupancy']） |
| crash | false | false |
| contact ground/inter_uav/obstacle | 0/0/0 | 0/0/0 |
| completion | false（未到 120 s） | false |

## goal 后 start-inflated 与 hover-voxel provenance（交接要求）

- **`Astar vehicle start is inside inflated occupancy` 共 1349 次，末次 sim 56.167
  （goal 后），位置 `(1.35293, 0.171142, 1.49432)`** —— uav1 悬停位。uav1 因起点在
  膨胀区内无法规划 → 未接令（无 command 通道）→ 悬停不动。
- **hover-voxel provenance**（`logs/gt_mapper.log`）：**77 个 voxel 全部
  `source_uav: "uav0"`，total point_hits 5549** —— uav1 悬停区域体素全部由 uav0 扫描
  提供（peer-body 回波假设的直接证据；与 preflight 诊断轮一致）。

## 失败链（供 lead 归因）

1. goal 发布 → **uav0 接令执行**（trajectory 8、pos_cmd/ACK 2540、移动 21.68 m、
   coverage 8129）——uav0 链路正常。
2. **uav1 未接令**：其 vehicle start（悬停位 1.353, 0.171, 1.494）持续 inside inflated
   occupancy（1349 次至 sim 56.167）→ 无法规划 → 无 command（与首次 smoke 同问题）。
3. uav1 悬停不动，occupancy 发布为低速率模式（同 preflight）→ 运行中 occupancy 停更
   >5 s → collector fail-closed abort（sim 56.26）。
4. fleet：8/8 进程存活（px4_bridge_1/2 均正常——bridge 修复生效）、
   `fleet_coverage_ratio=0.0354`、`map_consistency_jaccard=0.7773`、
   `overlap_ratio=0.9101`、`minimum_inter_uav_distance_m=1.3776`、`fleet_contact_count=0`。

## wall/sim 与 teardown

- wall/sim：sim `12.26 → 56.26`（44.00 sim s）/ wall 128.6 s，**RT ≈ 0.342**。
- teardown：top_level 5、descendants 18、term 23、kill []、survivors []、
  identity_confirmed/master_port_released/clean 全 true；无残留进程。

## Artifact hashes

- `manifest.yaml`:
  `5e841a9662fb49b1289951f490b094843740412f9845e122627e8d069fe1a871`
- `2uav_static.yaml`:
  `d106f0ca52bfcad5800d65e9a0f6692a074631cea965e96f5880e99d23461de0`
- `2uav_approval.yaml`:
  `a798ca4a30cab5972bc652074433f471fd6bf85dc0f09d3a87e3f88f2bcb3874`
- `runtime_environment.json`:
  `d191f11c0f7d018c18dca406c12fa8dc51f6327cacadde1a0c2a65c51acce171`
- `workspace_environment_probe.json`:
  `0407d96611464f335ab30dc8127be7d39ea0e065ca6e55b475d3eff1e89a4577`
- `process_specs.json`:
  `0647b39dcc623aee138c0bd073a7cfa232bf38e2602c3285aba206da2e05613c`
- `static_preflight.json`:
  `fdda172f5e4efe68332320b90568c61f8cfb642a3b5e9ed213a85586afb787ad`
- `live_preflight.json`:
  `a79e2597ae016c1914585f12872cee00a73e659b17a577338928a4c91bb93897`
- `execution_result.json`:
  `c0b3b5b50811177d6f8d6885f108daa41f704b9729e491a67c0d6bbf0f055aee`
- `fleet/abort.request`:
  `53464f20cc6517509db5ea333604ed41021425e03db9c63d8dce24fcd1f513dd`
- `uav0/metrics.json`:
  `ba1f59334fd3f2fcfc525592f655653346e3c6ded8f25da768b49964a273f40f`
- `uav1/metrics.json`:
  `4b28d67fa0a33d9c9bdfe62d49be3089d8c6cd679014bd0f7cc0b04efff44d23`
- `fleet/metrics.json`:
  `7f1b388dd5852583934bfc441918d06379acdb9787698aa6dd4a046257d4bf22`
- `logs/gt_mapper.log`:
  `19b1a10a71819cce900033fa80b21cc6e21be08ae2ff280302e6c8d151ff325a`
- `logs/racer.log`:
  `48a5efc48c8238544a5143181560d6d7dc7eea308cb2f6cb41f8267b0c314d26`

## Next gate

smoke 失败（abort，sim 56.26/120），package 已消费，runroot 为最终产物。按交接指令
交回 lead-planning 审核；不得同包重试、延长、调参、手工 goal、复用旧 runroot、修改
源码。luna 后续分析由 lead 安排。
