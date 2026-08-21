# 2-UAV preflight execution result

- Runroot: `RUN-20260821T082048Z-2uav-preflight`
- Command: `python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml`
- Exit code: `0`
- Decision: **`PREFLIGHT_PASS`** —— `live_preflight.json.passed = true`，48/48 项检查
  全部通过，无 abort。
- Smoke trigger: not issued（本 package 只批准 preflight；按 sol_approval 第 13 节，
  即使 preflight 通过也必须先交回 lead 审核，不得自动进入 smoke）
- Active lifecycle after exit: absent（5 进程全部 sigterm+sigkill，无 ACTIVE 文件）
- 本 runroot 为最终 append-only 产物；一次性 approval package 已消费（receipt
  `57a21fa5…json` 落盘）

## Frozen identity（全部核对通过）

- Multi repo: `41879e8ccea783895965831f75646ac2a6a43ed7`（`main`，dirty tree 由 hash
  manifest 绑定；未 commit）
- Platform repo: `57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`（tracked-clean）
- Single repo: `c01f1f5af40ec25631aa11765a0f21e06834abc4`（tracked-clean）
- Experiment manifest: `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`
- Source hash manifest: `0970f2e4b29aad999753270adb2cd8535d53826b4b0b651bced887e559657596`
  （12/12 OK）
- `two_uav_collector.py`（frontier 通道分类修复）:
  `efb27ff4335863f86e319a27ce8a06d8ad24ab90b3cf5eccac655d13c2540004`
- Static contract: `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`
- Runner: `60bd1a8aa9455139cc4663b53408cc07b64777319a7b4f83b74417e9ebe4bd50`
- 公共 baseline manifest: `ce595cafba088955b38c4c9bd1d08f9af254dbfa0bf013481372a75e17980944`
- PX4 iris model template: `e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225`
- `mid360.csv`: `aa1fc08b6a4400608dbd6ee832b7ea3a9c3c37197e734f60f58fe5abf762269a`
- Livox plugin binary: `ad117f9290cc1ef091842023d30af0de89bff14724fc78192250f737442b90b6`
- One-time approval package:
  `57a21fa5fb90400fafb589df8beeaaecebc0f0e50084240b6905db6afe8b9fa4`（consumed；
  启动前无 receipt、无 active lifecycle、环境探针 OK）

## 执行结果（48/48 全部通过）

- `static_preflight.json`: **passed: true**，53/53。
- `workspace_environment_probe.json`: 三项全部 `ok: true`。
- Readiness 门全部通过：`/clock`、两机 raw_cloud/mavros_odom/registered_cloud/
  registered_odom/frontier 真实 payload；px4_bridge_1/2 注册。
- `live.required_topics`: all present；`live.clock_single_publisher`: 1；
  `live.use_sim_time`: true。
- **`live.tf_expected_unique_dynamic_edges`: 通过**（"all expected TF edges observed"）。
- 两机 10 项 payload、两机 16 项参数回读、logdir 隔离全部通过。
- **`live.watchdog_soak`: 通过**（"watchdog evidence complete"）。
- **`final.metrics`: available**；**`final.safety`: 通过**（"final safety metrics
  complete"）。
- 停栈干净：5 进程全部 sigterm+sigkill；无 abort.request；无残留进程。

## wall/sim 推进量与 RT factor（sol_approval 第 13 节要求）

- fleet telemetry 共 6 行，`clock.monotonic` 全程 true；
- soak 窗口：sim `12.92 → 22.92`（推进 10.00 sim s），wall `14284.2 → 14316.9`
  （32.7 s），**RT factor ≈ 0.306**；
- 全程 `telemetry_completeness=true`、`abort_reasons=[]`。

## fleet 指标

- `abort_reasons: []`；`telemetry_completeness: true`；
- `tf_parents: {uav0/base_link: [world], uav1/base_link: [world]}`（唯一父，无 cross-talk）；
- `process_liveness`: 8/8 true（exploration_node_1/2、px4_bridge_1/2、traj_server_1/2、
  collector、gt_mapper）；`lost_after_seen: []`；
- `fleet_coverage_ratio: 0.0133`；`minimum_inter_uav_distance_m: 1.4712`；
- `map_consistency_jaccard: 0.7996`；`overlap_ratio: 0.9193`；`fleet_contact_count: 0`；
- `clock.last_sim_s: 24.173`。

## 逐机指标

| 指标 | uav0 | uav1 |
|---|---|---|
| cloud | 132 | 130 |
| odometry | 132 | 131 |
| frontier | 815 | 912 |
| health | 14 | 14 |
| occupancy | 23 | 27 |
| telemetry_complete | true | true |
| telemetry_stale_channels | [] | [] |
| crash / freeze | false / true（无 goal 静止） | false / true |
| coverage voxels / ratio | 3121 / 0.0116 | 3336 / 0.0124 |
| completion（无 goal） | false（预期） | false（预期） |
| contact ground/inter_uav/obstacle | 0/0/0 | 0/0/0 |

## 说明（供 lead 审核）

- frontier 通道分类修复生效：两机 frontier 均出现多次（815/912），soak 期间
  visualization 静默不再触发 freshness abort（run 5 的失败模式已消除）。
- RT factor ≈ 0.306 仍偏低（2×PX4 SITL + gazebo headless + 2×RACER + collector 同机
  CPU 饱和）；第 13 节明确指出这是 smoke 前独立负载风险，freshness 合同未放宽。smoke
  是否进行、何时进行由 lead 在审核本 runroot 后决定。

## Artifact hashes

- `manifest.yaml`:
  `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`
- `2uav_static.yaml`:
  `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`
- `2uav_approval.yaml`:
  `57a21fa5fb90400fafb589df8beeaaecebc0f0e50084240b6905db6afe8b9fa4`
- `runtime_environment.json`:
  `7e66bf3510a4cc153e9d0ddba42bf64139cd1881ebf394c9c8b609ebd132d94d`
- `workspace_environment_probe.json`:
  `0407d96611464f335ab30dc8127be7d39ea0e065ca6e55b475d3eff1e89a4577`
- `process_specs.json`:
  `7efeedbbde4cbb8e696bd67c1c890be69622684894f713ae303ce386f94270e3`
- `static_preflight.json`:
  `ea29114e9e4cfd19cf82a42faa561fb47a91efa03fda1479b0af37475443b0a6`
- `live_preflight.json`:
  `b8023fafe5e3f0eef786e2776e4a80b2778c518eb4888bc717d97d3af857afe1`
- `stop_result.json`:
  `e7daa805305059994b482c57f7f5db588a51451d7ec6681ebe11a2e703e2f0a9`
- `uav0/metrics.json`:
  `43961a8ff95670a8fcf78cb237ba21e2e03bd8bf9a2b3260cee40cc822e78c5a`
- `uav1/metrics.json`:
  `45690ff86aa8deb214fa14a5d8834c45a99c3182a5561131a13045e40386542f`
- `fleet/metrics.json`:
  `76fc27da6d728b3f4adb90a50e9152c9aaeed335d22699878a4bfd381b63b7ae`
- `uav0/telemetry.jsonl`:
  `643b3564d23e62412841f05e401298dd82dec966d2c10ffe42428aa38cefd807`
- `uav1/telemetry.jsonl`:
  `e9596648794f73f9b63d7228201011c8bf2ab1114bf8b41e54a186be5a750d19`
- `fleet/telemetry.jsonl`:
  `ca15dc0140c006b4ad0bde3d1ef92581ecd3f8dfcc7ab344fcc7c6a1526edd4e`
- `logs/gazebo.log`:
  `164a6c66afcdc6a020a27f9c684818a10bdd9312de99423a182b755ef7196da0`
- `logs/racer.log`:
  `6505f357b4fc37b0a8117a689d91f6dee60a389a38505a539389454ba73c8469`
- `logs/bridges.log`:
  `239a7aaff8c185f2226d41f532188f8e47db49a672182123d4821c93b271548f`
- `logs/gt_mapper.log`:
  `3d2c656e17e550a9aec503937100cbaf115ddf69944bca200a7a7b5558a2dbe2`

## Next gate

preflight 通过，但按 sol_approval 第 13 节与 skill 规则：**必须先交回 lead-planning
审核本 runroot**（live_preflight、最终 metrics、逐机证据、RT factor 负载风险），
**不得自动进入 smoke**。smoke 需要 Sol 另行签发 `stage: smoke` package。本 package 已
消费，不得复用。
