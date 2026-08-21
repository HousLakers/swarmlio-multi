# Execution Issue — 2-UAV preflight (RUN-20260821T060734Z-2uav-preflight)

- 写者：experiment executor（DeepSeek）
- 时间：2026-08-21T06:12Z
- 状态：**未修复任何代码**；一次性 approval package 已消费；runroot 已保留；
  等待 Sol 复审与最小修复计划（`state/sol_plan.md`）。

## 背景

按 `state/sol_approval.md` 第 7 节批准执行了一次 manifest 白名单 preflight：

```text
python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml
```

结果：exit 2，`live_preflight.json.passed=false`。静态门 53/53 与全部 live 参数回读通过；
运行期被 collector 的 fail-closed watchdog 以 `corrupted_telemetry:uav0:freshness` 为首因
abort。完整证据见 runroot 的 `execution_result.md`。

## Issue 1（阻断，需 Sol 归因后由 terra 修复）

**现象**：`launch/2uav_bridges.launch` 无法启动 `swarm_lio/px4_bridge.py`；roslaunch 报
`ERROR: cannot launch node of type [swarm_lio/px4_bridge.py]: swarm_lio`，随后
`No processes to monitor` 退出。px4_bridge_1/2 从未运行。

**证据**：
- `results/RUN-20260821T060734Z-2uav-preflight/logs/bridges.log`
- 复现：`bash -lc 'source /opt/ros/noetic/setup.bash; source /home/houslakers/swarm_ws/devel/setup.bash;
  source /home/houslakers/racer_ws/devel/setup.bash; echo $ROS_PACKAGE_PATH'`
  → `/home/houslakers/racer_ws/src:/opt/ros/noetic/share`（无 swarm_ws/src）；
  `rospack find swarm_lio` → `Error: package 'swarm_lio' not found`。
- 仅 source swarm_ws 时 `ROS_PACKAGE_PATH=/home/houslakers/swarm_ws/src:/opt/ros/noetic/share`
  （正常）；再 source racer_ws 后被覆盖。`swarm_lio` 包确实存在于
  `/home/houslakers/swarm_ws/src/Swarm-LIO2/swarm_lio/`（含 `scripts/px4_bridge.py`）。

**影响**：bridges 死亡 → 预期接线（/mavros_relay/odom_*、drone_state 中继）缺失 →
下游 gt_mapper 的 scan+odom 同步链无数据 → RACER 持续 `no odom` → collector 在
startup grace 后 fail-closed abort。

**归因问题（供 Sol 判断）**：是 `scripts/two_uav_runner.py` 的 `process_specs()` 子进程
环境组合（sourcing 顺序 / ROS_PACKAGE_PATH 显式导出）问题，还是 racer_ws devel 空间
extend 配置 / workspace baseline 问题？最小修复需保证 runner 子进程环境能 `rospack find
swarm_lio`。

## Issue 2（疑似，需 terra 复核）

**现象**：collector 在最终 fleet metrics 中记录 `process_death:/two_uav_gt_mapper` 与
`lost_after_seen: ["/two_uav_gt_mapper"]`；但 gt_mapper 自身日志
（`logs/ros/two_uav_gt_mapper.log`）显示进程存活至 signal-15（runner 停栈时刻），
期间无崩溃/退出痕迹。

**影响**：若 liveness 检测误报，会污染 abort 原因与 fleet 指标。需要复核
`scripts/two_uav_collector.py` 的节点存活检测逻辑（`process_death:` 分支）。

## Issue 3（背景事实，供 Sol 参考）

- world 文件 `2uav_outdoor_50x50_v1.world` 无 lidar/livox/scan/sensor 定义；
  `/uav0/livox/scan`、`/uav1/livox/scan` 的发布者注册来自 spawn 模型插件（topic owner
  为 `/gazebo`），但 scan 是否真的发布未经证实（gt_mapper 收到 0 条 scan 配对）。
- collector 对 `/planning/command_ack_1/2` 报 `topic_owner_missing`（无发布者）——
  preflight 中 RACER 处于 WAIT_TRIGGER 属预期，但 collector 按 frozen contract 将其
  计入 abort 原因。

## 已遵守约束

- 未修改任何源码、manifest、参数、approval package、`project_state.md`、
  `state/SESSION_HANDOFF.md`、`state/current_summary.md`；
- 未 commit / push / 切换分支；
- 未删除或覆盖任何旧 runroot（`RUN-20260820T101702Z-2uav-preflight` 原样保留）；
- 新 runroot `RUN-20260821T060734Z-2uav-preflight` 为最终 append-only 产物；
- 无残留 ROS/Gazebo 进程，无 active lifecycle 文件。

---

# Execution Issue（追加）— 2-UAV preflight (RUN-20260821T064604Z-2uav-preflight)

- 写者：experiment executor（DeepSeek）
- 时间：2026-08-21T06:47Z
- 状态：**未修复任何代码**；一次性 approval package（`8b3b7530…`）已消费；runroot 已
  保留；等待 Sol/terra 最小修复并重新签发 package。
- 批准依据：`state/sol_approval.md` 第 9 节（新 runner `06f2ae31…` 已修复上一轮
  bridges/swarm_lio 环境组合问题）。

## 结果

按第 9 节执行一次 preflight：exit 2，`live_preflight.json.passed=false`。静态 53/53
通过；**任何进程启动前**，`verify_workspace_environment` 门以
`workspace environment probe failed: swarm_lio, exploration_manager, quadrotor_msgs`
拒绝（无 Popen 启动、无 metrics，属基础设施门失败预期）。

## Issue（阻断，runner 脚本缺陷）

**现象**：probe 对三个必需符号全部失败，尽管 `runtime_environment.json` 记录的组合
环境已正确包含双 workspace：

- `swarm_lio` / `exploration_manager`：`[rospack] Error: package not found`；
- `quadrotor_msgs`：`ModuleNotFoundError`。

**根因（已复现）**：`scripts/two_uav_runner.py` 的 `verify_workspace_environment()`
（第 326-346 行）通过 `ros_command_spec()` 运行
`bash -lc "source /opt/ros/noetic/setup.bash; <probe>"`，env 已带组合路径；但
**`/opt/ros/noetic/setup.bash` 会把 `ROS_PACKAGE_PATH` 与 `PYTHONPATH` 重置为仅 noetic
值**，probe 因此全部失败。同文件 `process_specs()`（第 222-225 行）在 source noetic
**之后**调用 `workspace_environment_exports(runroot)` 重新导出组合路径，所以长期进程
环境正确——probe 与 process_specs 的环境构造不一致。

**复现证据**：

```text
source /opt/ros/noetic/setup.bash 前后:
  ROS_PACKAGE_PATH: /home/houslakers/swarm_ws/src:/home/houslakers/racer_ws/src:/opt/ros/noetic/share
                   → /opt/ros/noetic/share
  PYTHONPATH:      <swarm_ws dp>:<racer_ws dp>:<noetic dp> → /opt/ros/noetic/lib/python3/dist-packages

source noetic 后重新导出组合路径:
  rospack find swarm_lio           → /home/houslakers/swarm_ws/src/Swarm-LIO2/swarm_lio  OK
  rospack find exploration_manager → /home/houslakers/racer_ws/src/RACER/swarm_exploration/exploration_manager  OK
  python3 -c 'import quadrotor_msgs.msg' → OK
```

**最小修复方向（供 Sol/terra 决定，不在此实现）**：让 `verify_workspace_environment`
的 probe 与 `process_specs` 保持一致——在 `source /opt/ros/noetic/setup.bash` 之后应用
`workspace_environment_exports(runroot)`（或先 source 再组合导出），使 probe 能解析
swarm_lio、exploration_manager 与 quadrotor_msgs.msg。

## 其它

- 环境 baseline 本身合格：三个包均真实存在且可解析；workspace 未修改（符合第 9 节
  "不得修改 workspace"约束）。
- 未修改任何源码/参数/正式状态；未 commit/push；未覆盖任何旧 runroot；无残留进程。

---

# Execution Issue（追加）— 2-UAV preflight (RUN-20260821T065748Z-2uav-preflight)

- 写者：experiment executor（DeepSeek）
- 时间：2026-08-21T07:01Z
- 状态：**未修复任何代码**；一次性 approval package（`0944b9c0…`）已消费；runroot 已
  保留；等待 Sol/terra 复审。
- 批准依据：`state/sol_approval.md` 第 10 节（runner probe prefix 修复已生效：workspace
  probe 三项全部通过，stack 完整启动）。

## 结果

exit 2，`live_preflight.json.passed=false`。静态 53/53 通过；workspace probe 通过；
gazebo/两架 PX4 SITL/两架 mavros 全部启动成功（mavros 连接 PX4：Got HEARTBEAT；
vehicle_spawn：Successfully spawned entity；master.log 有
`+PUB [/uav0/livox/scan] /gazebo`、`+PUB [/uav1/livox/scan] /gazebo`）。
随后 **readiness 门 `uav0:raw_cloud: no payload` 超时**（120 s 内 `/uav0/livox/scan`
零消息），runner 停栈退出。

## Issue（阻断，lidar 仿真插件数据链路，非 runner）

**现象**：gazebo 注册了 `/uav0/livox/scan`、`/uav1/livox/scan` 发布者，但从未发布任何
消息。

**证据**（`logs/gazebo.log`）：
- `cannot convert str:` 异常 **2 次**（uav0、uav1 各一），均紧跟
  `load csv file name:…/livox_laser_simulation/scan_mode/mid360.csv`，并伴随
  `data size:800000`——`liblivox_laser_simulation.so` 在解析 mid360.csv 扫描模式时抛出
  boost::bad_lexical_cast 风格异常，扫描生成/发布链路断裂；
- `ERROR [simulator_mavlink] poll timeout 0, 25` ×4（PX4 SITL 侧，次级症状）。

**背景**：spawn 的 `iris` 模型（PX4 sitl_gazebo-classic
`models/iris/iris.sdf.last_generated`）含 `laser_livox` 传感器（插件
`liblivox_laser_simulation.so`，`<ros_topic>/scan</ros_topic>`，无
`<always_on>`，`update_rate=10`）。模型与插件来自环境/workspace baseline，不在 multi
仓库 hash 冻结文件内；`launch/2uav_px4_sitl.launch` 的 `vehicle=iris` 决定该模型。

**归因问题（供 Sol/terra 判断）**：`liblivox_laser_simulation` 插件版本与 gazebo/boost
兼容性、mid360.csv 解析失败、或 iris 模型/环境 baseline 配置；最小修复需让
`/uav0/livox/scan`、`/uav1/livox/scan` 有真实 scan payload 流出（与单机 20 m 水平全向
baseline 的 lidar 数据源一致）。

## 其它

- 本轮 runner/env 门全部通过；fail-closed readiness 门在最早 payload 点正确拦截，证据
  清晰。无 metrics 属预期（collector 未启动）。
- 未修改任何源码/参数/workspace/正式状态；未 commit/push；未覆盖任何旧 runroot
  （现共 4 个 RUN-* 均原样保留）；无残留进程。

---

# Execution Issue（追加）— 2-UAV preflight (RUN-20260821T074112Z-2uav-preflight)

- 写者：experiment executor（DeepSeek）
- 时间：2026-08-21T07:44Z
- 状态：**未修复任何代码**；一次性 approval package（`1718c1cf…`）已消费；runroot 已
  保留；等待 Sol/terra 复审。
- 批准依据：`state/sol_approval.md` 第 11 节（Livox headless baseline 修复：laser_livox
  传感器 `always_on=true`，model/CSV/plugin 三层 identity 绑定）。

## 结果

exit 2，`live_preflight.json.passed=false`。**唯一失败项**为
`live.tf_expected_unique_dynamic_edges`（观测两机 TF 父节点集为空）。其余全部通过：
workspace probe、静态 53/53、两机全部 payload 门（raw_cloud/mavros_odom/
registered_cloud/registered_odom/frontier 真实数据流：cloud/odometry ~118-120、
frontier 1200）、参数回读 16×2、logdir 隔离、24 s watchdog soak、final metrics
available、final safety complete、8/8 进程存活、无 abort。

## Issue（阻断，preflight live 检查脚本缺陷）

**现象**：live 检查 `tf_parent_sets()` 对两机都解析到空父节点集；但 collector 独立证据
（`fleet/metrics.json`）显示 TF 实际正常：
`tf_parents: {'uav0/base_link': ['world'], 'uav1/base_link': ['world']}`、freshness 数值
新鲜、全程无 cross-talk/missing_tf abort。

**根因（已证实）**：`scripts/two_uav_preflight.py` 第 326-344 行 `tf_parent_sets()`
运行 `rostopic echo -n 10 /tf --noarr`；rostopic 的 `--noarr` 语义为 "exclude arrays"
（`create_field_filter`：`if echo_noarr and '[' in t: continue`），会跳过 TFMessage 的
唯一字段 `transforms`（`TransformStamped[]`），因此该 echo 输出恒为空，
`frame_id`/`child_frame_id` 永远解析不到。此检查**无论 TF 是否正常都必然失败**。

**最小修复方向（供 Sol/terra 决定，不在此实现）**：移除 `--noarr`（或改用 rospy
`rospy.Subscriber("/tf", TFMessage, ...)` 采样），使 live TF 检查能解析
`world→uav0/base_link`、`world→uav1/base_link` 唯一动态边；并建议增加与 collector
TF 证据的一致性校验。

## 其它

- 本轮为至今最接近通过的一次：全部数据流与安全门通过，仅 live TF 检查脚本缺陷导致
  fail-closed 拒绝（fail-closed 行为本身正确）。
- 两机 `freeze=true`（preflight 无 goal，静止属预期）、`coverage.available=true` 但
  `observed_voxels=0`、`completion` 未观测——均为 preflight 无 goal 的预期记录，非
  abort 项，供 luna 后续分析。
- 未修改任何源码/参数/workspace/正式状态；未 commit/push；未覆盖任何旧 runroot
  （现共 5 个 RUN-* 均原样保留）；无残留进程。

---

# Execution Issue（追加）— 2-UAV preflight (RUN-20260821T075253Z-2uav-preflight)

- 写者：experiment executor（DeepSeek）
- 时间：2026-08-21T07:55Z
- 状态：**未修复任何代码**；一次性 approval package（`bc75e406…`）已消费；runroot 已
  保留；等待 Sol/lead 判定。
- 批准依据：`state/sol_approval.md` 第 12 节（live TF sampler 修复：`tf_echo_argv()`
  移除 `--noarr`、`parse_tf_parent_sets()` 独立纯函数）。

## 结果

exit 2，`live_preflight.json.passed=false`。**48 项检查 46 通过、2 失败**。通过项包括：
live TF 检查（`live.tf_expected_unique_dynamic_edges: True "all expected TF edges
observed"`——`--noarr` 修复生效）、两机全部 payload 门、参数回读 16×2、logdir 隔离、
final metrics available。失败项：`live.watchdog_soak`（soak 期间出现
`abort.request: {"reason": "corrupted_telemetry:uav0:freshness"}`）与 `final.safety`
（abort.request 存在）。

## Issue（soak 期间 uav0 frontier 通道停更 → fail-closed abort）

**现象**：uav0 的 `/planning_vis/frontier_1`（发布者 `exploration_node_1`）在 soak 后期
停更 >5 s（freshness 合同 5 s，startup grace 20 s 已过）；cloud/odometry 仍流动
（abort 时 100/101）。collector 按 frozen contract fail-closed abort，全局停栈。

**上下文证据**（`logs/racer.log`）：exploration_node_1 全程活跃（`wait for trigger`、
`No coverable frontier`、A* 尝试、`Ignore registered cloud while sensor is outside map`
——传感器在地面 z≈0.05，planner box z∈[1.15,2.7]，部分云在 box 外）；uav0 coverage
`observed_voxels=2226`（ratio 0.0083）；模拟 RT 因子约 0.33（主机 CPU 饱和，可能放大
发布间隙）。8/8 进程存活、TF 正常、`lost_after_seen: []`。run 4 同类状态 soak 通过、
run 5 失败——存在轮次间波动。

**归因问题（供 Sol/lead 决定，不在此修复）**：
1. 无 goal 的 preflight soak 中，exploration_node_1 的 frontier 发布在
   "No coverable frontier" 时可能停更 >5 s；当前 collector 按 frozen freshness 合同
   对 frontier 通道 fail-closed。是否应在无 goal preflight 中强制 frontier 5 s 新鲜度，
   或调整合同/发布行为（最小方案由 Sol 定）。
2. RT 因子 0.33（2×PX4 SITL + gazebo headless + 2×RACER + collector 同机），
   发布循环受调度饥饿的放大效应值得记录。

## 其它

- 未修改任何源码/参数/workspace/正式状态；未 commit/push；未覆盖任何旧 runroot
  （现共 6 个 RUN-* 均原样保留）；无残留进程、无 ACTIVE 文件。

---

# Execution Issue（追加）— 2-UAV smoke (RUN-20260821T083254Z-2uav-smoke)

- 写者：experiment executor（DeepSeek）
- 时间：2026-08-21T08:35Z
- 状态：**未修复任何代码**；smoke approval package（`3986a46c…`）已消费；runroot 已
  保留；等待 lead/luna/sol 审核。
- 批准依据：`state/sol_approval.md` 第 14 节（preflight PASS 48/48 后签发的一次性
  `stage: smoke` launch，120 sim s）。

## 结果

exit 2，`exit_reason=abort_requested`（sim 32.39/120，~27%）。46/46 启动前 live 门（含
24 s soak）通过、goal 已发布；uav0 接受唯一 bspline 并执行（freeze=false、移动 3.38 m、
pos_cmd/ack 各 278）；随后 uav0 规划失败（A* timeout / no path）、trajectory 通道停更
>5 s → collector fail-closed abort `corrupted_telemetry:uav0:freshness`。uav1 全程未接令
（其 planner 报 vehicle start inside inflated occupancy）。RT ~0.339。按第 14 节此失败
按真实 smoke 失败保留。

## Issue（供 Sol/lead 判定的两个观察，非现场修复）

1. **trajectory 通道合同**：collector 在首个 PositionCommand 后把 trajectory 加入连续
   5 s freshness 通道，但 `/planning/bspline_1` 由 traj_server 事件驱动发布（接受新
   bspline 才发布）；规划失败后不再发布 → 5 s 门触发 abort。与 run 5 frontier 属同一
   类别（事件驱动发布者 vs 连续 freshness 合同）。是否调整合同或发布行为由 Sol 定。
2. **规划失败本身**：uav0 A* 大量 timeout（rejects 以 outside/inflated_neighbor 为主）
   与 uav1 起点 inside inflated occupancy——属 RACER 规划/地图层行为，超出本轮执行
   范围，需 luna/sol 归因（单机节点 vs 多机协调；20 m 水平全向基线在 50×50 场景的
   规划行为）。

## 其它

- 未修改任何源码/参数/workspace/正式状态；未 commit/push；未覆盖任何旧 runroot
  （现共 7 个 RUN-* 均原样保留）；无残留进程、无 ACTIVE 文件。
