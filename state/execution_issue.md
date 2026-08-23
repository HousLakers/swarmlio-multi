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

---

# Execution Issue（追加）— 2-UAV preflight (RUN-20260821T152941Z-2uav-preflight)

- 写者：experiment executor（DeepSeek）
- 时间：2026-08-21T15:35Z
- 状态：**未修复任何代码**；一次性 approval package（`6280f483…`）已消费；runroot 已
  保留；等待 lead/sol 归因。

## 结果

exit 2，readiness 门 `uav0:frontier: missing nodes: /px4_bridge_1, /px4_bridge_2` 在
180 s 超时后失败，collector 未启动。静态 53/53、workspace probe 3/3、gazebo 双 spawn、
gt_mapper ready、bridges 心跳正常、bridges 节点门（60 s）先通过。

## Issue（供 lead 归因，非现场修复）

1. **探索 FSM 未越过 INIT**：exploration_node 停在 `[FSM]: Drone 1 state: INIT` /
   `wait for init`（初始 `no odom`，sim 6.7 后 odom 到达）；`/planning_vis/frontier_1`
   有发布者注册但 **0 条消息** → frontier payload 门不可能满足。同二进制在前三轮
   （082048Z/091542Z/095346Z）同一门通过，本轮为 RACER init 时序/负载轮次波动。
2. **`rosnode list` 探针 3 s 超时**：racer 门最终采样以空集报两 bridge 节点缺失，而
   bridges 进程全程存活且 bridges 门先通过——疑似 RT≈0.33 负载下探针超时的
   基础设施 flake，与 FSM 未推进复合。判定与是否加固探针由 lead/sol 决定。
3. 残留 rosmaster（gazebo roslaunch auto-start 子进程）未被 runner killpg 覆盖，
   已由执行器清理（端口 11311 释放）——可考虑作为 runner 停栈覆盖面的观察项。

## 其它

- 未修改任何源码/参数/workspace/正式状态；未 commit/push；未覆盖任何旧 runroot
  （现共 10 个 RUN-* 均原样保留）；无残留进程、无 ACTIVE 文件。

---

# Execution Issue（追加）— 2-UAV preflight (RUN-20260821T162356Z-2uav-preflight)

- 写者：experiment executor（DeepSeek）
- 时间：2026-08-21T16:25Z
- 状态：**未修复任何代码**；一次性 approval package（`186c9159…`）已消费；runroot 已
  保留；等待 lead/sol 归因。

## 结果

exit 2。readiness 门（含新 sim-budget frontier 门与 node probe 重试）**全部通过**、
collector 已启动（telemetry 2 行、sim 12.63→14.63、complete、无 abort、TF fresh），
失败在 live 检查：`rosparam get /exploration_node_1/map_ros/depth_filter_maxdist`
**15 s 超时**（uav0 前两个参数回读已通过）。

## Issue（供 lead 归因，非现场修复）

1. **live_checks 的 ROS CLI 15 s 超时**：`two_uav_preflight.py` 的 `ros_output()`
   （15 s、无重试）在负载（RT≈0.33）下对 rosparam get 超时——与上轮 `rosnode list`
   超时同类。runner 已对 readiness 探针加 `node_probe_result` 重试，但 live_checks 的
   rosparam/rostopic CLI 未覆盖。是否加固（重试/加时）由 lead/sol 决定。
2. **runner 停栈对深层子进程覆盖不足**：本轮停栈后 9 个 gazebo roslaunch 深层子进程
   （rosmaster、gzserver×2、px4 sitl×2、mavros×2、px4_bridge×2）未被 killpg 覆盖，
   已由执行器清理（端口 11311 释放）。连续两轮出现（上轮仅 rosmaster，本轮整棵子树），
   建议纳入 runner 停栈覆盖面评估。
3. 系统健康度：除该 CLI 超时外无其它异常证据（frontier 正常发布、telemetry complete）。

## 其它

- 未修改任何源码/参数/workspace/正式状态；未 commit/push；未覆盖任何旧 runroot
  （现共 11 个 RUN-* 均原样保留）；无残留进程、无 ACTIVE 文件。

---

# Execution Issue（追加）— 2-UAV preflight (RUN-20260821T165420Z-2uav-preflight)

- 写者：experiment executor（DeepSeek）
- 时间：2026-08-21T16:58Z
- 状态：**未修复任何代码**；一次性 approval package（`93172bf0…`）已消费；runroot 已
  保留；等待 lead/sol 归因。

## 结果

exit 2，readiness 门 `uav0:mavros_odom: no payload` 120 s 超时。静态 53/53、workspace
probe 3/3、gazebo 双 spawn、mavros +PUB 注册 odom、gt_mapper ready 均正常；mavros
odom 零消息（gazebo.log 无 PX4 heartbeat）。

## 归因上下文（供 lead 判定）

1. **机器极端过载**：失败时 `load average: 66.91`；sim 推进极慢（gazebo.log 末段 sim
   ~0.70，gt_mapper 首帧在 154 wall s 后 sim 1.168 → RT≈0.008，远低于常态 0.33）；
   PX4 侧 `Too many subscriptions, failed to add: vehicle_mocap_odometry` ×2。属负载/
   基础设施类时序失败，非代码回归；同门在 RT≈0.33 轮次通过。
2. **修复验证（正向）**：runner 新 teardown（descendant closure）本轮生效——停栈后
   **无任何残留进程**（对比前两轮需人工清理 rosmaster/深层子树）。建议 lead 确认是否
   需在 start_stack 异常路径（无 ACTIVE）也持久化 teardown 快照（本轮无
   stop_result.json，以无残留+gazebo 级联日志为证据）。
3. CLI retry（`readonly_cli_retry`）本轮未执行（失败早于 live_checks），无 retry 记录
   属预期。

## 其它

- 未修改任何源码/参数/workspace/正式状态；未 commit/push；未覆盖任何旧 runroot
  （现共 12 个 RUN-* 均原样保留）；无残留进程、无 ACTIVE 文件。

---

# Execution Issue（追加）— 2-UAV preflight (RUN-20260821T170558Z-2uav-preflight)

- 写者：experiment executor（DeepSeek）
- 时间：2026-08-21T17:13Z（重启后补录）
- 状态：**未修复任何代码**；一次性 approval package（`65c50e12…`，issuance_id
  `preflight-20260822-load-retry-1`）已消费；runroot 已保留；等待 lead/sol 归因。

## 结果

exit 2，readiness 门 `uav1:mavros_odom: no payload` 120 s 超时。uav0 链路通过
（sim 1.315 首帧 scan+odom 同步）；uav1 odom 零消息。

## 归因（供 lead 判定）

1. **负载运行窗口内再次飙升**：issuance 为 load-retry（启动时 load 1.77），但运行期间
   负载冲高至 29.0/67.5/49.1（1/5/15 min）；gazebo.log
   `CON: Lost connection, HEARTBEAT timed out` ×3 —— mavros-PX4 心跳丢失 → uav1
   odom 未及流动。属基础设施/负载类时序失败，非代码回归。
2. **readiness payload probe 泄漏（新增）**：runner `topic_payload_seen()` 的
   `subprocess.run(..., timeout=3)` 执行 `bash -lc "…; rostopic echo -n 1 …"`；超时时
   杀掉 bash 但 `rostopic echo` 孙进程成为孤儿（负载下等不到消息挂住）。本轮泄漏 39 个，
   已由执行器清理。建议评估 probe 使用进程组/超时后递归清理。
3. 主栈 teardown（descendant closure）继续有效：无 roslaunch/gzserver/px4/mavros 残留。

## 其它

- 未修改任何源码/参数/workspace/正式状态；未 commit/push；未覆盖任何旧 runroot
  （现共 14 个 RUN-* 均原样保留）；无残留进程、无 ACTIVE 文件。

---

# Execution Issue（追加）— 2-UAV preflight (RUN-20260821T172635Z-2uav-preflight)

- 写者：experiment executor（DeepSeek）
- 时间：2026-08-21T17:28Z
- 状态：**未修复任何代码**；一次性 approval package（`29fedcce…`，
  `preflight-20260822-post-reboot-retry-1`）已消费；runroot 已保留；等待 lead/sol 判定。

## 结果

exit 2，**48 项检查 47 通过、1 失败**。唯一失败：`final.safety`（fleet
`telemetry_completeness=false`，因 uav0 occupancy 通道在最终 metrics 快照时停更 >5 s）。
readiness/live/24 s soak/final metrics 全部通过；无 abort；teardown 证据完整落盘
（`stop_result.json`：clean=true、survivors=[]、master_port_released=true）。

## Issue（供 lead 判定，非现场修复）

1. **occupancy 通道 5 s freshness 边界**：occupancy 自然速率 ~6.5 wall s/条（22→23 间隔
   ≈6.5 s，RT≈0.358），逼近 5 s 阈值；全 run 周期 telemetry 均 complete，仅**停栈最终
   快照**时机敏感触发 stale。属本类问题第四次出现（run 5 frontier → smoke trajectory →
   本轮 occupancy）——低速率/事件驱动通道 vs 5 s 连续 freshness 合同的边界。occupancy
   在无 goal preflight 下是否应保持连续 freshness，由 Sol/lead 按 frozen contract 决定。
2. teardown 验证（正向）：descendant-closure teardown 本轮完整生效并落盘
   （top_level 5 + descendants 18、term 23、kill []、survivors []、
   identity_confirmed/master_port_released/clean 全 true）。

## 其它

- 未修改任何源码/参数/workspace/正式状态；未 commit/push；未覆盖任何旧 runroot
  （现共 15 个 RUN-* 均原样保留）；无残留进程、无 ACTIVE 文件。

---

# Execution Issue（追加）— 2-UAV preflight (RUN-20260821T175600Z-2uav-preflight)

- 写者：experiment executor（DeepSeek）
- 时间：2026-08-21T17:58Z
- 状态：**未修复任何代码**；一次性 approval package（`0093e6f4…`，
  `peer-ray-sensor-origin-1`）已消费；runroot 已保留；等待 lead/sol 归因。

## 结果

exit 2，46/48 通过。失败：`live.watchdog_soak` + `final.safety`（abort.request 存在，
首因 `corrupted_telemetry:topic_owner_missing`）。诊断交付门全部满足（endpoint/ray/
union removed、发布恒等式、uav1_hover_voxels provenance、sim≥15 inflated-occupancy）。

## Issue（真实运行时故障，供 lead 归因）

1. **uav0 未升空**：uav0 position z 全程 0.03-0.12 m（从未 ≥1.20 m）；uav1 正常悬停
   z≈1.49 m。
2. **px4_bridge_1 悬停就绪超时崩溃**（`logs/bridges.log`）：`[FATAL] 实体悬停超时：
   需要 OFFBOARD+armed、z>=1.20m、|vz|<=0.20m/s 连续 1.00s（timeout=45.0s）` →
   `RuntimeError: physical hover readiness timeout` → exit 1
   （`px4_bridge.py:192/260`，swarm_ws 第三方脚本，不在 multi hash manifest 内）。
   stdout 停在"正在请求 OFFBOARD 模式并解锁…"（sim 6.343）后无输出。
3. **abort 链**：px4_bridge_1 死亡 → topic owner 缺失/drift（
   `topic_owner_missing`、`topic_owner_drift`、`process_death:/px4_bridge_1`）→
   collector fail-closed abort（sim 24.62）。fail-closed 行为正确（进程死亡为真实故障）。
4. 观察：uav0 coverage=0（未升空，扫描点几乎全在 planner box 外）；uav0 未升空的
   原因（OFFBOARD 请求未生效 / PX4 未响应）需 lead/terra 调查 px4_bridge↔PX4 交互。
5. 诊断数据（转录）：removed==ray candidates（uav0 1218、uav1 2205）；发布恒等式成立
   （438038==439256−1218、354629==356834−2205）；uav1_hover_voxels 14 个 voxel 全部
   source_uav="uav0"；sim≥15 inflated-occupancy 448 次、末次 sim 24.523 @
   (0.0043,-0.011,0.035)（uav0 地面位）。

## 其它

- 未修改任何源码/参数/workspace/正式状态；未 commit/push；未覆盖任何旧 runroot
  （现共 16 个 RUN-* 均原样保留）；无残留进程、无 ACTIVE 文件。

---

# Execution Issue（追加）— 2-UAV smoke (RUN-20260821T184138Z-2uav-smoke)

- 写者：experiment executor（DeepSeek）
- 时间：2026-08-21T18:45Z
- 状态：**未修复任何代码**；smoke approval package（`a798ca4a…`，
  `smoke-20260822-bridge-readiness-and-occupancy-1`）已消费；runroot 已保留；等待
  lead/luna/sol 归因。

## 结果

exit 2，`exit_reason=abort_requested`（**sim 56.26/120**，~47%，较首次 smoke 32.39
有进展）。uav0 正常执行（trajectory 8、pos_cmd/ACK 2540、移动 21.68 m、freeze=false、
coverage 8129）；uav1 未接令（command 全 0、freeze=true、悬停 z≈1.5）。

## Issue（供 lead 归因，非现场修复）

1. **uav1 起点 inflated-occupancy 持续**：goal 后 `Astar vehicle start is inside
   inflated occupancy` **1349 次**、末次 **sim 56.167** @ uav1 悬停位
   `(1.35293, 0.171142, 1.49432)` → uav1 无法规划、未接令（与首次 smoke 同问题）。
2. **hover-voxel provenance 直接证据**：uav1 悬停区 **77 个 voxel 全部
   `source_uav:"uav0"`（5549 hits）**——uav1 悬停区域体素由 uav0 扫描提供，支持
   peer-body 回波污染共享地图假设（与 preflight 诊断轮一致）。
3. **uav1 occupancy 通道运行中停更 >5 s**（sim 56.26，`stale:['occupancy']`）→
   fail-closed abort。uav1 未接令静止时 occupancy 为低速率发布（同 preflight 模式），
   5 s freshness 阈值下时机敏感。occupancy 合同语义需 Sol 判定。
4. 正向：px4_bridge_1/2 全程存活（bridge-readiness 修复生效）；teardown 完整
   （descendants 18、kill []、survivors []、clean）。

## 其它

- 未修改任何源码/参数/workspace/正式状态；未 commit/push；未覆盖任何旧 runroot
  （现共 19 个 RUN-* 均原样保留）；无残留进程、无 ACTIVE 文件。

---

# Execution Issue（追加）— 2-UAV smoke (RUN-20260821T191146Z-2uav-smoke)

- 写者：experiment executor（DeepSeek）
- 时间：2026-08-21T19:14Z
- 状态：**未修复任何代码**；smoke approval package（`fdf91a8a…`，
  `smoke-20260822-peer-inflation-endpoint-mask-1`）已消费；runroot 已保留；等待
  lead/luna/sol 归因。

## 结果

exit 2，`exit_reason=abort_requested`（sim 50.99/120，~42%）。**双机均接令执行**
（uav0 trajectory 6/pos_cmd 2062/移动 11.69 m；uav1 trajectory 5/pos_cmd 2273/
移动 9.33 m）——**uav1 首次在 smoke 中执行**（前两次未接令）。abort 为 uav1
occupancy 通道运行中停更 >5 s（sim 50.99）。

## Issue（供 lead 归因，非现场修复）

1. **peer-inflation-endpoint-mask 修复显著生效（正向）**：start-inflated 从 1349 次降
   至 **229 次**、末次 sim 17.753（uav1 升空途中），之后不再阻塞 → uav1 成功规划执行。
2. **uav1 occupancy 5 s freshness 运行中触发**：执行中 occupancy 发布短暂停滞（计数停
   52）→ `stale:['occupancy']` → fail-closed abort。occupancy 合同第五次同类触发
   （frontier→trajectory→occupancy 系列）；是否调整合同/发布行为由 Sol 判定。
3. hover-voxel provenance：uav0 视角 16 个 voxel（全 source_uav="uav0"，记录 uav1 原
   悬停区）；uav1 已移动，hover voxel 较前次（77）减少。
4. teardown 完整（descendants 18、kill []、survivors []、clean）；RT≈0.324。

## 其它

- 未修改任何源码/参数/workspace/正式状态；未 commit/push；未覆盖任何旧 runroot
  （现共 21 个 RUN-* 均原样保留）；无残留进程、无 ACTIVE 文件。

---

# Execution Issue（追加）— 2-UAV preflight (RUN-20260821T202125Z-2uav-preflight)

- 写者：experiment executor（DeepSeek）
- 时间：2026-08-21T20:22Z
- 状态：**未修复任何代码**；一次性 approval package（`be77efb9…`，
  `compute-overlay-010m-1`）已消费；runroot 已保留；等待 lead/sol 归因。

## 结果

exit 2，`running resource gate failed: swap activity observed`。静态 **55/55** 与
workspace probe 通过；启动资源门（`resource_capacity_startup.json` ok:true）通过；
运行中资源门（`resource_capacity_ready.json` ok:false）检测到 swap-in 活动拒绝。

## Issue（资源/基础设施类，供 lead 判定）

1. **内存不足触发 swap**：运行中 MemAvailable 13.63→6.88 GB、swap_in 29491→29619
   （+128）→ 新资源门 fail-closed 拦截。双机全栈内存占用 ~12 GB（racer RSS 7.2 GB +
   gazebo 5.2 GB / MemTotal 16.17 GB）——**16 GB 内存不足以舒适运行双机全栈**，与上轮
   resource profile 诊断一致。
2. 新资源门（compute-overlay 修改引入）按设计工作：swap 活动时拒绝，防止内存不足下
   继续运行导致二次失败。fail-closed 行为正确。
3. 方向建议（供 lead 决定）：降低栈内存占用（如 RACER 参数/地图分辨率）、或提高内存
   余量、或调整资源门阈值；是否需为 smoke 拆分负载。

## 其它

- 未修改任何源码/参数/workspace/正式状态；未 commit/push；未覆盖任何旧 runroot
  （现共 22 个 RUN-* 均原样保留）；无残留进程、无 ACTIVE 文件。

---

# Execution Handoff（追加）— 2-UAV smoke (RUN-20260822T173640Z-2uav-smoke)

- 写者：experiment executor
- 时间：2026-08-23T01:43Z
- 状态：**未修改任何代码**；smoke approval package（`22e160bb…`，
  `smoke-20260823-2uav-first-pass-1`）已消费；runroot 已保留；runroot 内含
  `execution_result.md` 与 `execution_result.json`。
- 批准依据：lead handoff（2026-08-23 01:28）—— 前序 preflight
  （`3deec733…`，readback-numeric-1）PASS 后签发的一次性 `stage: smoke` launch，
  duration_sim_s=120、repetitions=1。

## 结果

exit 0，`exit_reason=duration_complete`，`final_safety_passed=true`，
`final_safety_detail="smoke command chain complete"`。120 sim s 全时长运行完成、
**无 abort**（`abort_reasons: []`）。smoke 前 live 门 53/53、启动+running 资源门均通过、
teardown clean（survivors=[]、kill=[]、identity_confirmed、master_port_released）。
`fleet_contact_count=0`（地面/障碍/机间均无接触）。双机均执行：
uav0 trajectory 83 / 121.27 m / ack 10178；uav1 trajectory 52 / 51.43 m / ack 12238。

## 交接建议（handoff_status: SMOKE_COMPLETE → result-reporting）

```text
handoff_status: SMOKE_COMPLETE
handoff_model: result-reporting
handoff_command:
只读取该 RUN-20260822T173640Z-2uav-smoke，生成 state/luna_review.md；不改源码或正式状态。
重点审核：uav1 freeze=true（但 52 trajectory、51.43 m、12238 ack，非早期不接令模式）、
RT factor p50=0.41（<0.5 target 未达成）、fleet_coverage_ratio=0.114、
map_consistency_jaccard=0.639、overlap_ratio=0.904、minimum_inter_uav_distance_m=1.479。
package smoke-20260823-2uav-first-pass-1（22e160bb）已消费，禁止复用。
```

## 关键数据

| 指标 | 值 |
|------|-----|
| last_sim_s | 150.886 |
| fleet_coverage_ratio | 0.114（30655/268912 voxels） |
| map_consistency_jaccard | 0.639 |
| minimum_inter_uav_distance_m | 1.479 |
| overlap_ratio | 0.904 |
| telemetry_completeness | true |
| process_liveness | 8/8 存活 |
| RT factor（161/179 valid） | p50=0.41、p95=0.43、max=1.99 |
| 资源门（startup→running） | load1 1.32→4.14、MemAvailable 11.79→5.56 GiB、swap 0→0 |
| uav0 / uav1 | crash=false/false、freeze=false/**true**、contact 0/0、ack_timeout 0/0 |

## 交接分析（供 luna/lead/sol 参考，非现场修复）

1. **RT < 0.5 target**：主动探索稳态 RT≈0.41（preflight hover 态 RT≈2.0，低约 5 倍）。
   双机全栈 + gazebo + collector 同机算力饱和；是否接受/优化/调整算力分配由 lead 定。
2. **uav1 freeze=true 需归因**：freeze 与 uav1 实际执行数据（52 trajectory、51.43 m）
   并存，疑似检测语义（末段无新 trajectory 窗口）或与 occupancy 低速率发布相关；
   telemetry 全通道 complete、无 stale，无 abort。freeze 判定逻辑需 luna/sol 复核。
3. **正向里程碑**：本实验首个 2-UAV 全时长 smoke 无 abort 完成；双机规划-执行-移动链路
   完整；资源门在真实负载下未触发；安全门（contact=0）有效。

## 其它

- 未修改任何源码/参数/workspace/正式状态；未 commit/push；未覆盖任何旧 runroot
  （现共 23 个 RUN-* 均原样保留）；无残留进程、无 ACTIVE 文件。
