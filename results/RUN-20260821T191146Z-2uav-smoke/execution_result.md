# 2-UAV smoke execution result

- Runroot: `RUN-20260821T191146Z-2uav-smoke`
- Command: `python3 scripts/two_uav_runner.py launch --manifest experiments/manifests/2uav_smoke.yaml`
- Exit code: `2`
- Decision: **`SMOKE_FAIL_ABORT`** —— goal 已发布；**双机均接令执行**（peer-inflation-
  endpoint-mask 修复使 uav1 摆脱 start-inflated 阻塞），sim 50.99 时 uav1 occupancy
  通道停更 >5 s → collector fail-closed abort（`corrupted_telemetry:uav1:freshness`）。
  推进至 **sim 50.99/120（~42%）**。
- Active lifecycle after exit: absent —— teardown 证据完整
  （`execution_result.json` stop：top_level 5、descendants 18、`kill []`、
  `survivors []`、`identity_confirmed=true`、`master_port_released=true`、`clean=true`）；
  无残留进程、无 ACTIVE 文件。
- 本 runroot 为最终 append-only 产物；smoke approval package 已消费（receipt
  `fdf91a8a…json` 落盘）

## Frozen identity（全部核对通过）

- Multi repo HEAD: `694a9c30aa9ee8f8f04b4f165866ded55a82aa0c` / `main`（dirty tree 由
  source hash manifest 冻结；未 commit）
- Platform repo: `57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`（tracked-clean）
- Single repo: `c01f1f5af40ec25631aa11765a0f21e06834abc4`（tracked-clean）
- Experiment manifest: `5e841a9662fb49b1289951f490b094843740412f9845e122627e8d069fe1a871`
- Static contract: `d106f0ca52bfcad5800d65e9a0f6692a074631cea965e96f5880e99d23461de0`
- Source hash manifest: `a932046b25198a692d1932f4cf3b315692b6d4a85d137cf4f5e21b2ee0f6b5c5`
  （12/12+3 OK）
- `two_uav_gt_mapper.py`（peer-inflation-endpoint-mask）:
  `c90383cb1083b554e50355405353d5a5e3ed3ce9a586a2d30962f8fc40a5c4e9`
- `two_uav_collector.py`: `5b6cbd4b7ac027bc1f8d75c33dda3fd3e0c0ac877bfbde05f52eb2c8cf77b396`
- `two_uav_preflight.py`: `35969b9698fcd802b87c6370ebe9c8e14e50154f2439a3093916e26e67dcd345`
- Runner: `67b6a343ea841bbfa54e23d72b6643aa22dde62c8bf47a243f83617ab760d6a2`
- `px4_bridge.py`: `b673080c46916790431f257aea1a27fa8616adeb6b409fe22968e0316b57f34f`
- 公共 baseline manifest: `ce595cafba088955b38c4c9bd1d08f9af254dbfa0bf013481372a75e17980944`
- PX4 iris model template: `e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225`
- Smoke approval package:
  `fdf91a8adbb310fccbf5d426043df05850eab84623d0a77de70d9e0d1a062eca`
  （consumed；`stage: smoke`、`allowed_actions: [launch]`、`max_uses: 1`、
  `issuance_id: smoke-20260822-peer-inflation-endpoint-mask-1`；启动前无 receipt、
  无 ACTIVE、环境探针 OK、负载 0.40/0.81/1.29）

## 执行阶段

1. 静态 53/53、workspace probe 3/3；启动前 live 门 46/46 通过。
2. goal 发布 → 120 sim s 监视；运行至 **sim 50.99**（20 行 telemetry；前 19 行
   complete、无 abort）。
3. sim 50.99 uav1 occupancy 通道停更 → collector fail-closed abort。
4. 停栈：teardown 完整（descendants 18、kill []、survivors []、clean）。

## 逐机报告（交接要求：command 链、运动、freeze、coverage）

| 指标 | uav0 | uav1 |
|---|---|---|
| trajectory | **6** | **5** |
| pos_cmd / ACK | **2062 / 2062**（last_ack_id=6） | **2273 / 2273**（last_ack_id=5） |
| ack_timeout | 0 | 0 |
| 运动（path_length） | **11.69 m**（freeze=false） | **9.33 m**（freeze=false） |
| 末位置 | [-4.96, -4.23, 2.35] | [3.24, 3.97, 2.66] |
| coverage voxels / ratio | 6264 / 0.0233 | 8868 / 0.0330 |
| telemetry complete / stale | true / [] | true / []（abort 时线 19 stale=['occupancy']） |
| crash / contact | false / 0 | false / 0 |
| completion | false（未到 120 s） | false |

**关键：uav1 首次在 smoke 中接令执行**（trajectory 5、移动 9.33 m）——peer-
inflation-endpoint-mask 修复使 uav1 摆脱 start-inflated 阻塞（前两次 smoke uav1 均
未接令）。

## start-inflated 与 hover-voxel provenance（交接要求）

- **`Astar vehicle start is inside inflated occupancy` 共 229 次（前次 smoke 1349 次），
  末次 sim 17.753**、位置 `(1.45019, 0.0315323, 1.08722)`（uav1 升空途中）——sim
  17.75 后不再出现，uav1 成功规划执行。
- **hover-voxel provenance**：uav0 source 视角 16 个 voxel（全部 `source_uav:"uav0"`，
  记录 uav1 原悬停区域）；uav1 source 视角 0 个。uav1 已移动，hover 区 voxel 减少
  （前次 77 个）。

## 失败链（供 lead 归因）

1. goal 发布 → **双机接令执行**（uav0 2062 指令、uav1 2273 指令，均移动/规划正常）。
2. **uav1 occupancy 通道运行中停更 >5 s**（sim 50.99，`stale:['occupancy']`；计数停在
   52）→ collector fail-closed abort。occupancy 5 s freshness 合同在运行中再次触发
   （第五次同类：frontier→trajectory→occupancy 系列）。
3. fleet：8/8 进程存活、`fleet_coverage_ratio=0.0361`、`map_consistency_jaccard=0.5576`、
   `overlap_ratio=0.8648`、`minimum_inter_uav_distance_m=1.4579`、`fleet_contact_count=0`。

## wall/sim 与 teardown

- wall/sim：sim `12.97 → 50.99`（38.02 sim s）/ wall 117.3 s，**RT ≈ 0.324**。
- teardown：descendants 18、term 23、kill []、survivors []、clean；无残留进程。

## Artifact hashes

- `manifest.yaml`:
  `5e841a9662fb49b1289951f490b094843740412f9845e122627e8d069fe1a871`
- `2uav_static.yaml`:
  `d106f0ca52bfcad5800d65e9a0f6692a074631cea965e96f5880e99d23461de0`
- `2uav_approval.yaml`:
  `fdf91a8adbb310fccbf5d426043df05850eab84623d0a77de70d9e0d1a062eca`
- `live_preflight.json`:
  `c61831b1aebab363fdb118858c57191fde32a2711be7f55657cdfc410368a264`
- `execution_result.json`:
  `2fc9db30af08a9db5bbebd7a4024a5be4b1de3a759bf30cbc2ec93c64eb58b58`
- `fleet/abort.request`:
  `52fb8b49096374c957c2e96f14154b0845b01ab943d32f673bd1853e94dcb396`
- `uav0/metrics.json`:
  `765f82409a4fe23f01d50883d9d984a8de755843159ee1a4d6dde5cde9f11b83`
- `uav1/metrics.json`:
  `60b258aa590f1a169414a35b370565905209e704bc673c4a87f46f04f3f85416`
- `fleet/metrics.json`:
  `159b2b41c9699e2353609f03fcc77e4297f4b8fe6c8ba8374b8da25db66691fe`
- `logs/gt_mapper.log`:
  `edef27020297a2bd7c5b1765401cc64d2488aa54fbcddc2f64f02138b34146e1`
- `logs/racer.log`:
  `b58072ce2a48919a799a5ca0c16b4913ada8ea5cd444982be6f3648ccf3fb9cf`

## Next gate

smoke 失败（abort，sim 50.99/120），但**双机协同执行首次达成**（uav1 摆脱 start-
inflated）。package 已消费，runroot 为最终产物。按交接指令交回 lead-planning 审核；
不得同包重试、延长、调参、手工 goal、复用旧 runroot、修改源码。
