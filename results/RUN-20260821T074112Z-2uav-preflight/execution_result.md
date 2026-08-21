# 2-UAV preflight execution result

- Runroot: `RUN-20260821T074112Z-2uav-preflight`
- Command: `python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml`
- Exit code: `2`
- Decision: `PREFLIGHT_FAILED_LIVE_TF_CHECK_ONLY`（唯一失败项为 live 检查
  `live.tf_expected_unique_dynamic_edges`；根因为 preflight 脚本 `tf_parent_sets()`
  使用 `rostopic echo --noarr` 排除了 TFMessage 的 transforms 数组，属脚本缺陷；
  系统实际 TF 数据满足合同）
- Smoke trigger: not issued（本 package 只批准 preflight）
- Active lifecycle after exit: absent（5 进程全部 sigterm+sigkill 停止，无 ACTIVE 文件）
- 本 runroot 为最终 append-only 产物；一次性 approval package 已消费（receipt
  `1718c1cf…json` 落盘）

## Frozen identity（全部核对通过）

- Multi repo: `41879e8ccea783895965831f75646ac2a6a43ed7`（`main`，dirty tree 由 hash
  manifest 绑定；未 commit）
- Platform repo: `57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`（tracked-clean）
- Single repo: `c01f1f5af40ec25631aa11765a0f21e06834abc4`（tracked-clean）
- Experiment manifest: `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`
- Source hash manifest: `41fbe083ccc5cc7a25093985cd1ddf76cec4e852bf6b92a288a5f94e54a30bb0`
  （12/12 OK）
- Static contract: `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`
- Runner: `60bd1a8aa9455139cc4663b53408cc07b64777319a7b4f83b74417e9ebe4bd50`
- 公共 baseline manifest: `ce595cafba088955b38c4c9bd1d08f9af254dbfa0bf013481372a75e17980944`
- PX4 iris model template: `e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225`
  （`iris.sdf.jinja`，laser_livox 传感器含 `always_on=true`）
- `mid360.csv`: `aa1fc08b6a4400608dbd6ee832b7ea3a9c3c37197e734f60f58fe5abf762269a`
- Livox plugin binary: `ad117f9290cc1ef091842023d30af0de89bff14724fc78192250f737442b90b6`
- One-time approval package:
  `1718c1cfda987f61650c8c39becddfc2d6ac6883938fdffd0bc4af860c2c3b10`（consumed；
  启动前无 receipt、无 active lifecycle、环境探针 OK）

## 执行结果（本轮大幅推进）

- `static_preflight.json`: **passed: true**，53/53。
- `workspace_environment_probe.json`: 三项全部 `ok: true`（swarm_lio /
  exploration_manager / quadrotor_msgs）。
- **Readiness 门全部通过**：`/clock`、两机 raw_cloud、mavros_odom、registered_cloud、
  registered_odom、frontier 均有真实 payload（Livox `always_on` 修复生效）；
  px4_bridge_1/2 节点注册。
- `live_checks`：除 TF 项外**全部通过**——required_topics、`/clock` 单发布者、
  `use_sim_time`、两机 10 项 payload（raw_cloud/mavros_odom/registered_cloud/
  registered_odom/frontier）、两机 16 项参数回读、logdir 隔离。
- **`live.watchdog_soak`: 通过**（"watchdog evidence complete"：fleet telemetry 完整、
  topic owner 证据完整、TF freshness 有数值、逐机 coverage available）。
- **`final.metrics`: available**；**`final.safety`: 通过**（"final safety metrics
  complete"，无 abort、无 crash、telemetry_complete、coverage available）。
- 停栈干净：5 进程全部 sigterm+sigkill；无 abort.request；无残留进程。

## 唯一失败项：`live.tf_expected_unique_dynamic_edges`

- 观测值：`{'uav0/base_link': [], 'uav1/base_link': []}`——live 检查认为两机 TF 父节点
  集为空，未满足"唯一父 `world`"合同。
- **但系统实际 TF 数据满足合同**（collector 独立证据，`fleet/metrics.json`）：
  `tf_parents: {'uav0/base_link': ['world'], 'uav1/base_link': ['world']}`；
  `tf_last_wall_s` 数值新鲜；全程无 `namespace_or_tf_cross_talk:*` 与
  `missing_tf:*` abort（collector 的 TF 回调会 abort 非唯一父/多父/缺失）。
- **根因（preflight 脚本缺陷，已证实）**：`scripts/two_uav_preflight.py` 的
  `tf_parent_sets()`（第 326-344 行）运行
  `rostopic echo -n 10 /tf --noarr`；rostopic 的 `--noarr`（"exclude arrays"，
  `create_field_filter` 中 `if echo_noarr and '[' in t: continue`）会跳过
  TFMessage 的唯一字段 `transforms`（`TransformStamped[]`），导致输出恒为空，
  `frame_id`/`child_frame_id` 永远解析不到。该检查因此**无论 TF 是否正常都失败**。

## 本轮通过的数据证据（供 luna/Sol 后续分析）

- uav0 telemetry：cloud=118、odometry=118、frontier=1200、health=13、occupancy=50、
  pos_cmd/trajectory/ack=0；
- uav1 telemetry：cloud=120、odometry=120、frontier=1200、health=13、occupancy=60、
  pos_cmd/trajectory/ack=0；
- `minimum_inter_uav_distance_m = 1.4953`（两机静态 1.5 m 间距，合理）；
- 两机 `crash=false`、`freeze=true`（preflight 无 goal，无人机静止属预期）、
  `completion` 未观测（无 goal，预期）、`coverage.available=true` 但
  `observed_voxels=0`（RACER 处于 WAIT_TRIGGER，occupancy 计数低；非 abort 项）；
- `fleet_coverage_ratio=0.0`、`overlap_ratio=0.0`、`map_consistency_jaccard=0.0`；
- 8/8 进程存活：exploration_node_1/2、px4_bridge_1/2、traj_server_1/2、collector、
  gt_mapper。

## Progress vs 前几轮

第 1 轮：collector soak abort（旧 runner 无 payload 门）；第 2 轮：workspace probe 门
（runner bug，已修复）；第 3 轮：readiness 门 raw_cloud 零消息（Livox 插件 csv 异常，
已修复）；**第 4 轮（本轮）：全部数据流与安全门通过，唯一失败为 live TF 检查的
`--noarr` 脚本缺陷**。系统本身已满足 preflight 合同数据要求。

## Artifact hashes

- `manifest.yaml`:
  `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`
- `2uav_static.yaml`:
  `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`
- `2uav_approval.yaml`:
  `1718c1cfda987f61650c8c39becddfc2d6ac6883938fdffd0bc4af860c2c3b10`
- `runtime_environment.json`:
  `6f4a2120ce924cbebf699cc177a99c94e8e4e4763d886d9b551e376bb986c93c`
- `workspace_environment_probe.json`:
  `0407d96611464f335ab30dc8127be7d39ea0e065ca6e55b475d3eff1e89a4577`
- `process_specs.json`:
  `5066c0e4b412fa8dba35d7a48bb0d8cd03c8f8919dd190bafef61803f262d70c`
- `static_preflight.json`:
  `8ad9f3e32c9cdb8fdc1630b43b23b69afaa3d1cd289c944a7c667fe425e29dfc`
- `live_preflight.json`:
  `902569353230032e67891946bde15070fc5d36977ee50280feee3aef0015d394`
- `stop_result.json`:
  `e7daa805305059994b482c57f7f5db588a51451d7ec6681ebe11a2e703e2f0a9`
- `uav0/metrics.json`:
  `a30631a9befa4db22999abca402572b75373b044badc440b03b682b83c9282d6`
- `uav1/metrics.json`:
  `05edba455a6f419b250c9a31736742232e50ee334e0a970a2c8a93c6e6f04398`
- `fleet/metrics.json`:
  `d65e8e44d3c82715c417b85bb7428a53a8ee7371fde825b8d59cce094da525f0`
- `logs/gazebo.log`:
  `deb51a3d4069c6f12960f10be48154ef807f0eb94c7014177ad88c6a81ecf395`
- `logs/bridges.log`:
  `19fc9cd3eac1d568b4280fa6fbae7ec1d46d4c4ce64ff926bf69094cd41ab85d`
- `logs/racer.log`:
  `58bf0116dbdfae709874ced910e0aefa77fa3af7f52570c26fb9752c96f4771f`
- `logs/gt_mapper.log`:
  `882222930796343fa1224e3525d1f47239492f760aa86240b1b183608d4d5b23`

## Next gate

package 已消费，runroot 为最终产物。按 sol_approval 第 11 节：不得复用 package、不得
launch/smoke、不得修改源码/参数/workspace/正式状态。live TF 检查 `--noarr` 脚本缺陷已
移交 Sol/terra 复审（`state/execution_issue.md`）；修复（移除 `--noarr` 或改用
rospy 订阅采样）后需 Sol 重新签发一次性 preflight package。
