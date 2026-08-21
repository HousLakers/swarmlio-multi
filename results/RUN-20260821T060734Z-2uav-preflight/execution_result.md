# 2-UAV preflight execution result

- Runroot: `RUN-20260821T060734Z-2uav-preflight`
- Command: `python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml`
- Exit code: `2`
- Decision: `PREFLIGHT_FAILED_RUNTIME_SAFETY_ABORT`（collector fail-closed watchdog 在
  startup grace 后触发 telemetry freshness abort；非基础设施失败）
- Smoke trigger: not issued（本 package 只批准 preflight）
- Active lifecycle after exit: absent（无 ROS/Gazebo 残留进程，无
  `/tmp/swarmlio_multi_2uav_active.json`）
- 本 runroot 为最终 append-only 产物，一次性 approval package 已消费

## Frozen identity

- Multi repo: `41879e8ccea783895965831f75646ac2a6a43ed7`（`main`，dirty tree 由完整
  hash manifest 绑定；未 commit）
- Platform repo: `57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`（tracked-clean）
- Single repo: `c01f1f5af40ec25631aa11765a0f21e06834abc4`（tracked-clean）
- Source hash manifest: `05fada5472ec02436c6d12c0fef6e4fd766a57911a86ca8abb09bffc6ab077e4`
  （12/12 OK）
- Experiment manifest: `e366f943180cb1471742ab2a84e685d75e64442fd00c8bf75e14a00ee618a0f2`
- Runner: `d6313ef2c25b8fe39d9431a322de064de3bc8734c084e11b791299012c248a64`
- Public baseline manifest: `48d00fca6032c76f59ca26134ff39dba2d555a552c2d73f81e3ca51b4583dc44`
- 50x50 world: `28a306b646297011b564c5ce94ac97634281a5e9a34e337956c5f4a9227c320e`
- One-time approval package:
  `3bf111dbe3d06e0f545ecc4a81cf4636e5a964b370af7dc0d1245b3403359e43`（consumed，
  receipt 见 `results/approval-consumption/`）

## Pre-execution gates（启动前核对）

- 四项摘要全部匹配 sol_approval 第 7 节：manifest、source hash manifest、runner、
  approval package。
- approval 字段：`stage: preflight`、`approved: true`、`allowed_actions: [preflight]`、
  `max_uses: 1`、`issued_by: sol`。
- 无新 package 的消费 receipt（仅旧 `57a76ff0...` receipt 存在）。
- 无 active lifecycle（无 roscore/Gazebo/PX4 进程、无 ACTIVE 文件）。
- 执行环境探针：`netifaces.interfaces()` OK（5 个接口）、localhost TCP bind/listen OK、
  `/tmp` 可写（ACTIVE 路径）。`~/.ros` 只读，但 runner 将 `ROS_LOG_DIR`/`ROS_HOME`
  重定向到 runroot（`logs/ros/`、`logs/ros-home/`），无 `~/.ros` 回落。

## Evidence

- `static_preflight.json`: **passed: true**，53/53 项，13 个 source hashes 记录。
- Stack 启动：gazebo（`/clock` 单一发布者、sim 时间单调推进至 16.77 s）、gt_mapper、
  bridges、racer（exploration/traj servers 启动并进入 WAIT_TRIGGER）、collector。
- `live_checks` 全部通过：required topics 全在、`/clock` 单发布者、`use_sim_time=true`、
  TF 无 cross-talk（空 TF 集，trivial pass）、两机各 16 项冻结+环境参数回读全部正确、
  逐机 logdir 隔离存在。
- `live.watchdog_soak`: **FAILED** —— soak 期间出现 `fleet/abort.request`
  `{"reason": "corrupted_telemetry:uav0:freshness", ...}`。
- 最终 metrics 可用（uav0/uav1/fleet 的 `metrics.json` + `telemetry.jsonl` 均在）；
  `final.safety` 因 abort.request 存在而失败。`live_preflight.json.passed = false`。

## Failure chain（均有日志证据）

1. **bridges launch 直接失败**：`logs/bridges.log` 报
   `ERROR: cannot launch node of type [swarm_lio/px4_bridge.py]: swarm_lio`，
   roslaunch 显示 `No processes to monitor` 并退出。复现确认：在 runner 子进程相同的
   sourcing 顺序（noetic → swarm_ws → racer_ws）下
   `ROS_PACKAGE_PATH=/home/houslakers/racer_ws/src:/opt/ros/noetic/share`，
   **缺少 swarm_ws/src**（仅 source swarm_ws 时为 `swarm_ws/src:/opt/ros/noetic/share`，
   再 source racer_ws 后被覆盖）；`rospack find swarm_lio` 失败。`swarm_lio` 包实际
   存在于 `swarm_ws/src/Swarm-LIO2/swarm_lio/`（含 `scripts/px4_bridge.py`），但子进程
   环境找不到。→ px4_bridge_1/2 从未运行（fleet `process_liveness` 中为 false）。
2. **gt_mapper 全程 0 发布**：`two_uav_gt_mapper` 进程存活（自身日志持续到 signal-15），
   但 `ApproximateTimeSynchronizer(scan, odom, slop=50 ms)` 从未触发（无 scan+odom 配对，
   无 registered-scans 回调日志），`/cloud_registered_1/2`、`/lidar_slam/odom_1/2`、
   `/lidar_slam/pose_1/2` 共 0 条消息。racer.log 从 sim 1.56 起持续
   `[WARN] ...: no odom`。
3. **collector 数据面近乎空转**：逐机 telemetry 仅 health=16、occupancy=76；
   odometry/cloud/frontier=0 全程；`telemetry_stale_channels: [odometry, cloud, frontier]`；
   TF 从未流动（`tf_last_wall_s` 恒 null；px4 launch 按设计禁用 mavros TF send）。
4. **fail-closed abort（按设计工作）**：20 s startup grace 后，collector 判定 uav0
   freshness 超限并写 `fleet/abort.request`（首个原因）；最终 fleet metrics 累计 6 个
   abort 原因：uav0/uav1 freshness、missing_tf ×2、topic_owner_missing
   （`/planning/command_ack_1/2` 无发布者）、`process_death:/two_uav_gt_mapper`。
5. runner 停栈（`stop_result.json`：collector/racer/gt_mapper/gazebo sigterm+sigkill，
   bridges already_exited），删除 ACTIVE 文件，退出码 2。无残留进程。

## Observations（供 Sol 分类，非结论）

- 本轮是首次 runtime 安全层带真实证据完整触发（grace → freshness abort → 全局停止），
  fail-closed 路径本身工作正常；与上一轮（2026-08-20，纯基础设施失败）不同。
- `process_death:/two_uav_gt_mapper` 与 gt_mapper 自身日志（进程存活至 signal-15）矛盾，
  疑似 collector liveness 检测偏差，需 terra 复核。
- 首要阻断：runner 子进程环境 ROS_PACKAGE_PATH 组合不含 swarm_ws/src → bridges 死亡；
  以及 scan/odom 供应链从未流动（world 文件无 lidar 传感器定义，scan 发布者注册来自
  spawn 模型插件，是否真的发布未经证实）。归因（runner 环境组合 / workspace baseline /
  其它）由 Sol 决定。
- 详情见 `state/execution_issue.md`。

## Artifact hashes

- `manifest.yaml`:
  `e366f943180cb1471742ab2a84e685d75e64442fd00c8bf75e14a00ee618a0f2`
- `2uav_static.yaml`:
  `fa3be02954ea86280c19c8b41c1ca194e7d565351857051e9c0f8536e0d7e8d6`
- `2uav_approval.yaml`:
  `3bf111dbe3d06e0f545ecc4a81cf4636e5a964b370af7dc0d1245b3403359e43`
- `runtime_environment.json`:
  `ddd46de52a22fcf3fbaf8b238babd00f110dbc48e5686d5d97bdf086c5d7be52`
- `process_specs.json`:
  `a18827c6dfa835f86000638eb84629d6398349051f61d4ecbc3e716b5af53f30`
- `static_preflight.json`:
  `adb4a7ae725632c209073a19aaba0bf5b854e94b9c94b605462553d7f9827a6e`
- `live_preflight.json`:
  `0f2c4fcce1cdb8d5e42e5f48067e7fced53c34efadf53a87de99e976b056acbe`
- `stop_result.json`:
  `6d963f8315a87fed8d53e90f9a7d19a0b908534d7b147c8e4faab770d61689e2`
- `uav0/metrics.json` / `uav1/metrics.json`:
  `aaeb0cf02fac425ab7b0ddb124fdb34e8d06928181fd52346bf2210880684594`
- `fleet/metrics.json`:
  `708b98cd1a14cdc71ce61e9f77acb09895cf0a2349f440db6550fa6a441910d4`
- `fleet/abort.request`:
  `d8020e48d582521a10a70e5ad1e6bea42b58664c6bde75d02635fe04427b0e7b`
- `uav0/telemetry.jsonl`:
  `f7232e3e3e507564538daee85a2f1338d0c86a31dcb9bbf0022f21803d936eb8`
- `uav1/telemetry.jsonl`:
  `4018b08785915939a63985f5f4fdecceb87ee7ae0da42368413c7a327d8d0059`
- `fleet/telemetry.jsonl`:
  `7d6e27c05946a9d45cd61d06dfa98667c063a3bcd1250409598bf26f61c23578`
- `logs/gazebo.log`:
  `d65ce1277f68247499c73c2c0955867de2e512b5e09a662259fd04ea9ca5c9d2`
- `logs/racer.log`:
  `84237703035a2b5a3acb463ef339ae22e6cbcf64400c7bf3a90a057568145739`
- `logs/bridges.log`:
  `43b44b2a8e060828d61d179642c54ac2e25de9f280d60d8a5a3f26e0285e6c35`
- `logs/gt_mapper.log`:
  `dce939bc0c62bedf871e6270a5d7c42f20b1a4b8ec03c4d48be595f3512d4abb`
- `logs/collector.log`: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
  （0 字节；collector 自身日志在 `logs/ros/two_uav_collector.log`）

## Next gate

本 package 已消费，runroot 为最终 append-only 产物。按 `state/sol_approval.md` 第 7 节：
不得复用旧/新 package、不得进入 smoke、不得修改源码/参数/正式状态文件。本轮证据与
脚本级疑点已移交 Sol 复审（`state/execution_issue.md`）；任何新的 preflight 需要 Sol
重新签发一次性 package。
