# 2-UAV preflight execution result

- Runroot: `RUN-20260821T075253Z-2uav-preflight`
- Command: `python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml`
- Exit code: `2`
- Decision: `PREFLIGHT_FAILED_WATCHDOG_SOAK_FRONTIER_FRESHNESS`（48 项检查 46 通过；
  live TF 检查已通过；唯一失败为 soak 期间 uav0 frontier 通道停更 >5 s，collector
  fail-closed abort `corrupted_telemetry:uav0:freshness`）
- Smoke trigger: not issued（本 package 只批准 preflight）
- Active lifecycle after exit: absent（5 进程全部 sigterm+sigkill，无 ACTIVE 文件）
- 本 runroot 为最终 append-only 产物；一次性 approval package 已消费（receipt
  `bc75e406…json` 落盘）

## Frozen identity（全部核对通过）

- Multi repo: `41879e8ccea783895965831f75646ac2a6a43ed7`（`main`，dirty tree 由 hash
  manifest 绑定；未 commit）
- Platform repo: `57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`（tracked-clean）
- Single repo: `c01f1f5af40ec25631aa11765a0f21e06834abc4`（tracked-clean）
- Experiment manifest: `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`
- Source hash manifest: `3ef1ce50b80fa3742462acf49f2312e34188673a3b56e824c7e6be16c8a39640`
  （12/12 OK）
- `two_uav_preflight.py`: `afa8b3821b2c8f3e2dfda2f5f65e5d960145ee1bf277d10c220157bde231a567`
- Static contract: `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`
- Runner: `60bd1a8aa9455139cc4663b53408cc07b64777319a7b4f83b74417e9ebe4bd50`
- 公共 baseline manifest: `ce595cafba088955b38c4c9bd1d08f9af254dbfa0bf013481372a75e17980944`
- PX4 iris model template: `e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225`
- `mid360.csv`: `aa1fc08b6a4400608dbd6ee832b7ea3a9c3c37197e734f60f58fe5abf762269a`
- Livox plugin binary: `ad117f9290cc1ef091842023d30af0de89bff14724fc78192250f737442b90b6`
- One-time approval package:
  `bc75e406c7f9d94d4514abfd57588d23b7791f7af7216667ea6a5cb08a70713b`（consumed；
  启动前无 receipt、无 active lifecycle、环境探针 OK）

## 执行结果（48 项检查：46 通过 / 2 失败）

**通过项**：
- `static_preflight.json`: **passed: true**，53/53。
- `workspace_environment_probe.json`: 三项全部 `ok: true`。
- Readiness 门全部通过：`/clock`、两机 raw_cloud/mavros_odom/registered_cloud/
  registered_odom/frontier 真实 payload；px4_bridge_1/2 注册。
- **`live.tf_expected_unique_dynamic_edges`: 通过**（"all expected TF edges observed"——
  `--noarr` 修复生效，两机唯一父 `world` 被 CLI sampler 正确解析）。
- required_topics、`/clock` 单发布者、`use_sim_time`、两机 10 项 payload、两机 16 项参数
  回读、logdir 隔离全部通过。
- `final.metrics`: available。

**失败项**：
- `live.watchdog_soak`: **FAILED** —— soak 期间出现 `fleet/abort.request`
  `{"reason": "corrupted_telemetry:uav0:freshness", ...}`。
- `final.safety`: **FAILED** —— abort.request 存在。

## Failure（soak 期间 uav0 frontier 通道停更，fail-closed 按设计）

- uav0 逐机 telemetry：cloud=100、odometry=101、frontier=585、health=11、occupancy=20；
  `telemetry_stale_channels: ['frontier']`、`telemetry_complete: false`；cloud/odometry
  在 abort 时仍计数（数据面大部分正常）。
- 时间线：fleet telemetry 5 行（sim 12.99 → 20.999），前 4 行
  `telemetry_completeness=true`、无 abort；第 5 行（sim 20.999）出现
  `corrupted_telemetry:uav0:freshness`。
- collector 在 startup grace（20 s）后按 frozen freshness 合同（5 s wall）判定 uav0
  frontier 停更 → 写 append-only abort.request → 全局停栈（5 进程 sigterm+sigkill）。
- 8/8 进程存活（exploration_node_1/2、px4_bridge_1/2、traj_server_1/2、collector、
  gt_mapper）；`lost_after_seen: []`；TF 正常
  （`tf_parents: {uav0/base_link: [world], uav1/base_link: [world]}`，freshness 数值
  持续更新）。

## 上下文证据（racer.log，供 Sol 归类）

- exploration_node_1 全程活跃：`wait for trigger`（无 goal，preflight 预期）、
  `No coverable frontier`、`Astar candidate start is inside inflated occupancy`、
  `Ignore registered cloud while sensor is outside map: (1.487, -0.009, 0.049)`——
  两机传感器在地面 z≈0.05（未起飞），planner box z 范围 1.15-2.7，部分云在 box 外被忽略。
- uav0 coverage：`available=true`、`observed_voxels=2226`、`ratio=0.0083`（本轮已有部分
  coverage，优于 run 4 的 0）。
- 模拟 RT 因子约 0.33（soak 24.4 s wall 内 sim 仅推进 ~8 s）——主机 CPU 饱和；frontier
  发布循环可能受调度饥饿出现 >5 s 间隙。
- 两机 `crash=false`、`freeze=true`（无 goal 静止，预期）、`completion` 未观测（预期）。

## 归因问题（供 Sol/lead 判断，不在此修复）

1. **frontier freshness 合同 vs 无 goal preflight 状态**：exploration_node_1 的 frontier
   发布在 "No coverable frontier" 时可能停更 >5 s（run 4 通过、run 5 失败，存在轮次间
   波动）。是否应在无 goal 的 preflight soak 中强制 frontier 通道 5 s 新鲜度，需 Sol 按
   frozen contract 决定（当前实现 fail-closed，行为符合合同）。
2. **RT 因子 0.33**：主机负载高（2×PX4 SITL + gazebo headless + 2×RACER + collector），
   可能放大发布间隙；非本轮直接根因但值得记录。

## Artifact hashes

- `manifest.yaml`:
  `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`
- `2uav_static.yaml`:
  `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`
- `2uav_approval.yaml`:
  `bc75e406c7f9d94d4514abfd57588d23b7791f7af7216667ea6a5cb08a70713b`
- `runtime_environment.json`:
  `e065f6598afea19cb4ff835d76adec7d8bf102bc27bf041c04cda12176db4bb8`
- `workspace_environment_probe.json`:
  `0407d96611464f335ab30dc8127be7d39ea0e065ca6e55b475d3eff1e89a4577`
- `process_specs.json`:
  `ff09dd88f45b221dd5c3910b0438d173b566328838942da36879a88e4e583d54`
- `static_preflight.json`:
  `baa8a525525ead3f23cbed67d855d81011f2064439ab0657f10768893393429b`
- `live_preflight.json`:
  `c38dc14f4b449c92f864726f1a57e5a493a79dc3cee959eed88cab33540623ff`
- `stop_result.json`:
  `e7daa805305059994b482c57f7f5db588a51451d7ec6681ebe11a2e703e2f0a9`
- `fleet/abort.request`:
  `f2853f4637153ce085b36ab5f80ad6bad9191580a6f25928114afe86bf3ed51d`
- `uav0/metrics.json`:
  `9ae116c216ecf9dfa6c6aacd1ed054575c8d6fd10bcab128d4c455f5dfca17b4`
- `uav1/metrics.json`:
  `8f74310e5f27068c3d5b8e36c63933d5fdb799e75f0079278cd32cee14a2c321`
- `fleet/metrics.json`:
  `2ceb52f03c3a8c2b60ffc387f089bd0c8d28a166c2bc80f07e2eb5720dd5c762`
- `uav0/telemetry.jsonl`:
  `cf0b864a6ee018b4d50af152b8071c8b9e74a0039db06b2ddc8db8701a033072`
- `uav1/telemetry.jsonl`:
  `e84147b3133251f481eeb427577d8e82d5a92dbbfd7a6c7a6f6032a61bcc6523`
- `fleet/telemetry.jsonl`:
  `ba33588a2201df7337c1ef40b5860463a7e635aed71c9b90e3b4f7baf90b09a7`
- `logs/racer.log`:
  `ec7d63333a711a890640f3796277423e5bc44d9f394e07cf87705ce4b0aa932b`
- `logs/gazebo.log`:
  `58cae8339436df16e0d9219c43832bfbb1b5c46d52f205145f409a63eba51ed4`
- `logs/bridges.log`:
  `61b77cbe516ac765b5adc785242a01ffaad7cf6bbeac8419de5226eea8518a19`
- `logs/gt_mapper.log`:
  `c73d002e41821b6fdbd2ac6050e9cc497ab36aac2d74366f8e6cf697fd139bbb`

## Next gate

package 已消费，runroot 为最终产物。按 sol_approval 第 12 节：不得复用 package、不得
launch/smoke、不得修改源码/参数/workspace/正式状态。frontier freshness 合同与无 goal
soak 的适配问题已移交 Sol/lead 判定（`state/execution_issue.md`）；若需调整合同或修复
发布链路，由 Sol 决定最小方案并重新签发一次性 preflight package。
