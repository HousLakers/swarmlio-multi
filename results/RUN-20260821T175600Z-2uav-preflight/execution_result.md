# 2-UAV diagnostic preflight execution result

- Runroot: `RUN-20260821T175600Z-2uav-preflight`
- Command: `python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml`
- Exit code: `2`
- Decision: **`PREFLIGHT_FAILED_ABORT_PX4_BRIDGE1_DEATH`** —— 48 项检查 46 通过、2 失败
  （`live.watchdog_soak` + `final.safety`）。abort 根因：**uav0 未升空 → px4_bridge_1
  悬停就绪 45 s 超时崩溃**（`physical hover readiness timeout`，sim 23.293）→ topic
  owner 缺失/drift → collector fail-closed abort（sim 24.62）。
- Smoke trigger: not issued（本 package 只批准 diagnostic preflight）
- Active lifecycle after exit: absent —— teardown 证据完整落盘
  （`stop_result.json`：descendants 17、`survivors []`、`clean=true`）；无残留进程、
  无 ACTIVE 文件。
- 本 runroot 为最终 append-only 产物；一次性 approval package 已消费（receipt
  `0093e6f4…json` 落盘）

## Frozen identity（全部核对通过）

- Multi repo HEAD: `694a9c30aa9ee8f8f04b4f165866ded55a82aa0c` / `main`（dirty tree 由
  source hash manifest 冻结；未 commit）
- Platform repo: `57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`（tracked-clean）
- Single repo: `c01f1f5af40ec25631aa11765a0f21e06834abc4`（tracked-clean）
- Experiment manifest: `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`
- Static contract: `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`
- Source hash manifest: `07b8f795cc9b0475c3ba815590b3d4a39c59c50a820e0b53357b6285f028047e`
  （12/12 OK）
- `two_uav_gt_mapper.py`（peer-ray-sensor-origin 诊断）:
  `aa67881daa58dd13d3328ff40f0c93c59b71951943a99990493c4665f2d83cd9`
- `two_uav_collector.py`: `5b6cbd4b7ac027bc1f8d75c33dda3fd3e0c0ac877bfbde05f52eb2c8cf77b396`
- `two_uav_preflight.py`: `35969b9698fcd802b87c6370ebe9c8e14e50154f2439a3093916e26e67dcd345`
- Runner: `67b6a343ea841bbfa54e23d72b6643aa22dde62c8bf47a243f83617ab760d6a2`
- 公共 baseline manifest: `ce595cafba088955b38c4c9bd1d08f9af254dbfa0bf013481372a75e17980944`
- PX4 iris model template: `e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225`
- One-time approval package:
  `0093e6f41f6fab1417f7e9444b88c6ea2731b36fab765c779cca6a7414a85779`
  （consumed；`stage: preflight`、`allowed_actions: [preflight]`、`max_uses: 1`、
  `issuance_id: preflight-20260822-peer-ray-sensor-origin-1`；启动前无 receipt、
  无 ACTIVE、环境探针 OK、负载 1.34/1.07/0.95）

## 执行结果（46/48）

**通过项**：静态 53/53、workspace probe 3/3、全部 readiness 门、live 检查（payload/TF/
参数回读/logdir）、final.metrics available。

**失败项**：
- `live.watchdog_soak`: abort.request 在 soak 期间出现（`{"reason":
  "corrupted_telemetry:topic_owner_missing", …}`）。
- `final.safety`: abort.request 存在。

## 失败链（证据，供 lead 归因）

1. **uav0 全程未升空**：uav0 position z 时间线 `0.05→0.09→0.12→0.11→0.08→0.05→0.03`
   （从未 ≥1.20 m）；uav1 正常悬停 `z≈1.49 m`。
2. **px4_bridge_1 悬停就绪超时崩溃**（`logs/bridges.log`）：
   `[FATAL] [sim 23.293] [Bridge 1] 实体悬停超时：需要 OFFBOARD+armed、z>=1.20m、
   |vz|<=0.20m/s 连续 1.00s（timeout=45.0s）` → `RuntimeError: physical hover
   readiness timeout` → exit 1（`px4_bridge.py:192/260`，swarm_ws 第三方脚本，不在
   multi hash manifest 内）。px4_bridge_1 stdout 停在"正在请求 OFFBOARD 模式并解锁…"
   （sim 6.343）后无更多输出。
3. **px4_bridge_1 死亡 → collector fail-closed abort**（fleet metrics 累计）：
   `corrupted_telemetry:topic_owner_missing`（首个）、
   `namespace_or_tf_cross_talk:topic_owner_drift`、`process_death:/px4_bridge_1`
   （`process_liveness[/px4_bridge_1]=false`、`lost_after_seen=[/px4_bridge_1]`）；
   abort 于 sim 24.62（soak 内）。
4. 观察：uav0 `coverage.observed_voxels=0`（未升空，扫描点几乎全在 planner box 外）；
   uav0 未升空的原因（OFFBOARD 请求未生效 / PX4 未响应）需 lead/terra 调查
   px4_bridge↔PX4 交互。

## 诊断交付（转录自 `logs/gt_mapper.log`，原样；判定归 lead）

**endpoint/ray/union removed（第二快照 sim 20.0）**：

```text
uav0 source: peer_candidates=907  peer_endpoint_candidates=907  peer_ray_candidates=1218  peer_removed_points=1218
uav1 source: peer_candidates=588  peer_endpoint_candidates=588  peer_ray_candidates=2205  peer_removed_points=2205
（第一快照 sim 10.17：uav0 removed=174/ray=174；uav1 removed=2037/ray=2037）
```

**发布恒等式（published == registered − removed）**：

```text
uav0: published_points=438038 == registered_points=439256 − 1218 ✓
uav1: published_points=354629 == registered_points=356834 − 2205 ✓
```

**uav1_hover_voxels provenance（uav0 视角第二快照，14 个 voxel，全部 source_uav="uav0"）**：

```json
{"4,-1,5":{"first_sim_time":16.219,"point_hits":124,"recent_sim_time":19.922,"source_uav":"uav0"},
 "4,0,5":{"first_sim_time":16.521,"point_hits":123,"recent_sim_time":19.922,"source_uav":"uav0"},
 "5,-1,4":{"first_sim_time":14.72,"point_hits":103,"recent_sim_time":16.119,"source_uav":"uav0"},
 "5,-1,5":{"first_sim_time":14.819,"point_hits":598,"recent_sim_time":19.922,"source_uav":"uav0"},
 "5,-2,5":{"first_sim_time":16.42,"point_hits":36,"recent_sim_time":19.82,"source_uav":"uav0"},
 "5,0,4":{"first_sim_time":14.819,"point_hits":108,"recent_sim_time":16.119,"source_uav":"uav0"},
 "5,0,5":{"first_sim_time":14.819,"point_hits":558,"recent_sim_time":19.922,"source_uav":"uav0"},
 "5,1,5":{"first_sim_time":17.322,"point_hits":19,"recent_sim_time":19.419,"source_uav":"uav0"},
 "6,-1,4":{"first_sim_time":14.72,"point_hits":78,"recent_sim_time":16.022,"source_uav":"uav0"},
 "6,-1,5":{"first_sim_time":14.919,"point_hits":286,"recent_sim_time":19.922,"source_uav":"uav0"},
 "6,-2,5":{"first_sim_time":15.121,"point_hits":59,"recent_sim_time":19.82,"source_uav":"uav0"},
 "6,0,4":{"first_sim_time":14.819,"point_hits":83,"recent_sim_time":15.923,"source_uav":"uav0"},
 "6,0,5":{"first_sim_time":16.022,"point_hits":247,"recent_sim_time":19.922,"source_uav":"uav0"},
 "6,1,5":{"first_sim_time":17.219,"point_hits":22,"recent_sim_time":19.419,"source_uav":"uav0"}}
```

**sim≥15 实际 vehicle-start inflated-occupancy**（`logs/racer.log`）：
- 共 **448 次** `Astar vehicle start is inside inflated occupancy`；
- **末次 sim 24.523（>15）**，start 位置 `(0.00434, -0.01102, 0.03494)`——uav0 地面位
  （z≈0.035，因 uav0 未升空）；
- 早前轮次该警告出现在 uav1 悬停点 (1.545, -0.094, 1.470)（RUN-…095346Z）。

## wall/sim 与 teardown

- 全 run 7 行 telemetry（sim 12.63→24.62）均 complete、无 abort 至第 6 行；abort 于
  sim 24.62。
- teardown：descendants 17、`survivors []`、`clean=true`；无残留进程。

## Artifact hashes

- `manifest.yaml`:
  `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`
- `2uav_static.yaml`:
  `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`
- `2uav_approval.yaml`:
  `0093e6f41f6fab1417f7e9444b88c6ea2731b36fab765c779cca6a7414a85779`
- `runtime_environment.json`:
  `3e294c71be9848e0e5e8ccf0bd359d7f8bc4e47980dfd1a27b295adcc188dabf`
- `workspace_environment_probe.json`:
  `0407d96611464f335ab30dc8127be7d39ea0e065ca6e55b475d3eff1e89a4577`
- `process_specs.json`:
  `61cd9df39ea820b39d2b0563a529226a3d452316d3256ecb6cafd9e0b6a88aa1`
- `static_preflight.json`:
  `2c25a79191240527185e53356cf147f1ad5d677218a41e50b96a1ea5f11f9a7e`
- `live_preflight.json`:
  `50fbf7b3d9919a1215b4d6242340af9278b44e7f1b3218ab965bf303a039aa67`
- `stop_result.json`:
  `0fa09189fe5e9e63085eef2ac07470cb7961fa21a83ffbb143d835d4297d3182`
- `fleet/abort.request`:
  `0c41008fd1f800d32892b8544d3b403406dcddc237b8c845e6b36f16cb439e60`
- `uav0/metrics.json`:
  `5e4160fb9ae929e25752ab8bedd1271ac1132f5fae4f3d892a1d166290396955`
- `uav1/metrics.json`:
  `2f4577bb3afb1e21ac5464576c9d45d5a9f6df339a3aa5b137dd75d3d9084dc2`
- `fleet/metrics.json`:
  `de861b7e2c37e769439ffd79bab4a0eba263e03f3721057d40b9728894ff4af1`
- `logs/gt_mapper.log`:
  `914386ef2a2eeae42c168cc271cd437a54ae4d709758b8c81144e185740c2ec8`
- `logs/bridges.log`:
  `4df6bd858ba77e5dc122ec802c42373bf20e39d261feb1526d7560d461be8eae`

## Next gate

诊断交付门全部满足（endpoint/ray/union removed、发布恒等式、uav1_hover_voxels
provenance、sim≥15 inflated-occupancy 均已采集转录）；失败为真实运行时故障
（uav0 未升空 → px4_bridge_1 崩溃 → owner abort）。package 已消费，runroot 为最终
产物。按交接指令交回 lead-planning 审核；不得执行 smoke、不得同包重试、不得修改
任何代码/参数。
