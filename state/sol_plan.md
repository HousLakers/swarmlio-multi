# Sol 受限计划：2-UAV 静态接入与 preflight 证据准备

- 日期：2026-08-20
- 角色：Lead/Sol
- 适用 manifest：`experiments/manifests/2uav_smoke.yaml`（唯一）
- 当前决定：`NOT_APPROVED / BLOCKED_PENDING_VERIFIED_2UAV_INTEGRATION`
- 实验权限：无；不得启动 preflight、仿真、2-UAV smoke 或长跑

## 1. 目标

在不修改 `range20m_omnidirectional_v1` 单机节点参数与算法语义的前提下，为 UAV0、
UAV1 建立可审计的静态多机接线和机器可读 preflight。只有源码身份、逐机运行参数、
namespace/TF/vehicle ID/端口、topic、日志与结果目录、telemetry、fleet 指标及 abort
路径全部形成证据，Sol 才能重新评审是否允许执行 manifest 白名单中的 preflight。

本计划不把单机结果外推为 fleet 结论；单机结果只作为两个节点共同采用的 baseline。

## 2. 冻结输入

以下身份和范围不得由实现阶段改变：

- 公共平台：`https://github.com/HousLakers/racer-platform.git`，commit
  `57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`；
- 单机配置：`https://github.com/HousLakers/swarmlio-single.git`，commit
  `c01f1f5af40ec25631aa11765a0f21e06834abc4`；
- overlay：`platform_overlays/range20m_omnidirectional_v1`；
- overlay manifest SHA-256：
  `80d0d06a5a9b3722804c28d3efc6ace9a71d5955b26f8124e12bf3579e0d9529`；
- overlay installer SHA-256：
  `7e2280d5d0ba88ee501764ab5b5ccc3f3724d5b6abf39704badc7a8976349151`；
- 多机编排基点：`41879e8ccea783895965831f75646ac2a6a43ed7`；
- 固定 smoke 范围：2 UAV、120 simulated seconds、1 次、seed `20260814`、
  `shared_async`、`static` partition、0 ms 人工通信延迟、GT 注册；
- 唯一可用实验定义：`experiments/manifests/2uav_smoke.yaml`。不得创建、替换或执行
  其他实验 manifest。

本机身份审计已知事项：公共平台 commit 匹配；冻结单机 Git 仓库实际位于
`swarmlio-single-v2`，而合同路径 `swarmlio-single` 不是 Git 仓库。两项 overlay
SHA-256 在 `swarmlio-single-v2` 中匹配，但该路径歧义必须在实现证据中显式解决，
不得靠隐式目录选择通过身份门。

## 3. 允许写入

本次 Lead/Sol 动作只允许创建或更新：

- `state/sol_plan.md`。

后续 Terra 接受本计划后，仅允许在一个源码写入者约束下修改：

- `swarmlio_multi` 内纯多机 launch、runner、静态 preflight、collector 和 abort 接线；
- `experiments/manifests/2uav_smoke.yaml`，仅用于用已验证命令替换占位符、补齐命令
  白名单和证据要求，不得改变冻结单机参数或扩大 smoke 范围；
- `state/terra_implementation.md`，记录完整 diff、静态检查、编译结果、hash 和参数
  回读证据；
- 如确有必要，RACER/Swarm-LIO 中仅限 namespace、remap、vehicle identity 的多机
  接线；不得改算法和单机参数。

在 Sol 后续审核前不得生成 `state/sol_approval.md` 的批准结论，不得写入新的
`results/RUN-*`。

## 4. Terra 静态接入任务包

Terra 应按以下顺序提交 diff 和证据，不得运行实验：

1. 冻结身份：记录 multi、platform、single 的 remote、commit、branch、工作树状态，
   两个 overlay SHA-256，以及所有将被执行源码/脚本的完整 hash manifest；明确处理
   `swarmlio-single` 与 `swarmlio-single-v2` 的路径歧义。
2. 双机身份：为 UAV0/UAV1 固定且区分 namespace、初始位姿、vehicle/system ID、
   ROS/MAVLink 端口、TF prefix/child frame、日志目录和结果子目录。
3. topic/TF 接线：证明 odometry、cloud、map、frontier、trajectory、pos_cmd、ACK、
   contact、health 均可唯一归属；证明 TF 无重复 child frame、无跨 UAV parent 串线。
4. 时间语义：保证唯一 `/clock`，两节点均使用相同 simulated time；为单调性和
   `use_sim_time` 回读提供静态探针入口。
5. 参数回读：对 UAV0、UAV1 分别生成机器可读回读，至少包含 20 m 有效视距、水平
   360°、`obstacles_inflation=0.35`、三个 guard 开关、GT registration source、map
   mode、partition mode 和通信延迟；任一缺失或不一致即失败。
6. 采集隔离：逐机记录 completion、freeze、crash、contact、coverage、telemetry、
   ACK timeout；fleet 侧记录 coverage、overlap ratio、minimum inter-UAV distance、
   contact count、map consistency、任务分配状态及进程存活。
7. 日志隔离：证明停止任一 UAV 不会覆盖另一架结果；所有输出进入独立子目录，未来
   runroot 只能 append-only。
8. abort 接线：为 crash、严重接触、telemetry 损坏、namespace/TF 串线及 process
   death 建立全局停止路径，同时保留已生成的 append-only 证据。
9. manifest 收口：移除 launch 占位符；将启动、只读监控、停止、采集命令逐项加入
   `command_whitelist`，不得使用 shell 占位符、通配扩权或未固定路径。

## 5. Preflight 成功标准

以下条件必须全部有机器可读证据；声明、代码存在或人工描述不能替代证据：

- 三仓库身份、overlay SHA-256、实现工作树 diff/hash 全部一致且可追溯；
- UAV0/UAV1 的 namespace、初始位姿、ID、端口、topic、TF、日志和结果目录全部唯一；
- 两架 UAV 的冻结参数分别回读成功，值完全一致且与 manifest 相符；
- 唯一 `/clock`、共同 simulated time 和 TF 隔离检查通过；
- 逐机安全/完成/telemetry/ACK 指标和 fleet 指标均有独立落盘路径；
- abort 条件和 append-only 保全路径具有可验证入口；
- `launch_command` 不再是占位符，`command_whitelist` 完整且只含可审核命令；
- Terra 在 `state/terra_implementation.md` 提供 diff、静态检查与必要编译证据；
- Sol 逐项复核上述证据后另行作出批准决定。

任一项失败、缺失或无法唯一归属，批准状态必须保持 `false`。即使静态 preflight
全部满足，也不自动批准 smoke；需要 Sol 独立审核 manifest 和 ACK timeout 合同。

## 6. 当前阻断与决定

当前明确缺少：经过验证的 2-UAV launch、非空命令白名单、机器可读 preflight、
namespace/TF/端口隔离证据、双机参数回读、逐机日志隔离证据、Terra diff/编译证据及
Sol approval。manifest 仍含 `REPLACE_WITH_VERIFIED_2UAV_LAUNCH_COMMAND`。

因此本轮决定为：

```text
approved: false
decision: BLOCKED_PENDING_VERIFIED_2UAV_INTEGRATION
allowed_next_action: TERRA_STATIC_INTEGRATION_AND_EVIDENCE_ONLY
```

## 7. 禁止动作

- 不得启动 preflight、ROS/Gazebo 仿真、2-UAV smoke 或长跑；
- 不得执行 manifest 之外的实验定义或命令；
- 不得修改 20 m 视距、水平 360°、near-field、A* 分类、startup/ACK 语义或任何
  单机算法参数；
- 不得引入通信延迟、丢包、动态分区、参数搜索或额外 UAV；
- 不得混用 GT 与 LIO 注册结果；
- 不得复用 namespace、ID、端口、TF child frame、日志或结果目录；
- 不得用一架 UAV 的 completion/freeze 覆盖另一架状态；
- 不得修改 `project_state.md`、`state/SESSION_HANDOFF.md` 或正式项目状态；
- 不得 commit、push、切换分支或修改远程历史；
- 不得覆盖原始 runroot，不得提交原始大日志、点云、build/devel/install 或密钥；
- 未经 Lead/Sol 重新审核，不得扩大本计划范围或批准实验。

## 8. 2026-08-21 preflight 基础设施失败后的最小返工任务包

### 决定

```text
approved_preflight_retry: false
approved_smoke: false
decision: BLOCKED_PENDING_RUNROOT_ROS_LOG_ISOLATION_FIX
```

本轮 `results/RUN-20260820T101702Z-2uav-preflight/` 在静态 53 项门通过后，因执行沙箱
禁止 `netifaces.interfaces()` 且 roslaunch 不能写 `~/.ros/log`，在 `/clock` 出现前失败。
旧 approval package SHA-256
`57a76ff0e3d1829684cac38b8a725e0d9b36df006be2f5e37cbd58fafd65b60f` 已消费，不得复用。

### 冻结输入

- manifest SHA-256：
  `e366f943180cb1471742ab2a84e685d75e64442fd00c8bf75e14a00ee618a0f2`；
- source hash manifest SHA-256：
  `9dbc2b5ac181f86c786ff7b5d549daf101902abdf911440a400cb53092d209af`；
- 20 m、水平全向、算法参数、50x50 world、UAV 数量、时长、seed、namespace、端口和
  abort 合同全部冻结。

### 根因与目标

`scripts/two_uav_runner.py::process_specs()` 只把 stdout/stderr 写入 runroot，未设置
runroot 专属 `ROS_LOG_DIR`/`ROS_HOME`，ROS 内部日志仍落到共享 `~/.ros`。目标是在每个
新 runroot 内建立独立 ROS 日志/状态目录，并让 runner 启动的全部 ROS/Gazebo/Python
进程继承这些路径。网络接口枚举权限由后续 experiment executor 以受批准的非沙箱/
escalated 执行解决；不得在源码中绕过 ROS 网络检查。

### 允许修改

- `scripts/two_uav_runner.py`；
- 必要的 runner 纯函数/self-test；
- `config/2uav_source_hashes.sha256`；
- `state/terra_implementation.md`。

不得修改 manifest、world、launch、冻结参数、approval package、receipt、旧 runroot、
`project_state.md`、`state/SESSION_HANDOFF.md` 或其它正式状态。

### 实现要求

1. `make_runroot()` 在 `logs/` 下创建不可复用的 ROS log/home 子目录；
2. `process_specs(runroot)` 为所有子进程显式导出指向该 runroot 的 `ROS_LOG_DIR` 和
   `ROS_HOME`，路径必须可审计且不能回落到 `~/.ros`；
3. runroot 中保存的 argv/静态证据能证明实际导出的路径；
4. 增加纯函数或 self-test，证明 UAV0/UAV1/fleet 共用本轮 runroot、不同 runroot 不会
   共享 ROS log/home，且命令不含 `~/.ros`；
5. 更新 source hash 并重新运行 py_compile、runner self-test、12/12 hash、53 项静态
   preflight 和 `git diff --check`。

### 成功标准与下一门

Terra 只提交静态证据，不启动 ROS/Gazebo。Sol 审核 diff 和新 source hash 后，才可签发
新的 `stage: preflight`、`max_uses: 1` approval package。实际重试必须使用 manifest
白名单 preflight 命令并获得允许 ROS 网络接口枚举的执行权限；preflight 通过后仍需 Sol
审核，不能自动进入 smoke。

## 9. 2026-08-21 ROS 子进程环境继承最小返工

### 审核决定

```text
approved_preflight_retry: false
approved_smoke: false
decision: REJECTED_INCOMPLETE_ROS_CHILD_ENVIRONMENT_ISOLATION
```

Terra 第 13 节证明五个 `process_specs()` 长期进程均显式导出 runroot 专属
`ROS_LOG_DIR`/`ROS_HOME`，两个 runroot 的目录也不共享；12/12 source hash、runner
self-test、53/53 静态 preflight 和 `git diff --check` 均通过。但 runner 还会在
`wait_topic()`、`sim_time_s()` 和 smoke trigger 中直接启动 `rostopic` 子进程，这些命令
没有显式绑定 runroot ROS 环境。尤其 `monitor`/`collect` 可由新的 runner 进程执行，
`load_active()` 只读取 runroot，不恢复其 ROS 环境，因此仍可能回落到调用者的 `~/.ros`。

旧 approval package SHA-256
`57a76ff0e3d1829684cac38b8a725e0d9b36df006be2f5e37cbd58fafd65b60f`
已有消费 receipt；本次不得修改、复用或签发新 package。

### 允许修改

- `scripts/two_uav_runner.py`；
- runner 纯函数/self-test；
- `config/2uav_source_hashes.sha256`；
- `state/terra_implementation.md`。

### 最小返工与成功标准

1. 为新建 runroot 和由 `ACTIVE` 恢复的既有 active runroot 构造同一份显式子进程环境，
   其中 `ROS_LOG_DIR`、`ROS_HOME` 必须严格等于该 runroot 的 `logs/ros`、
   `logs/ros-home`；不得使用或继承 `~/.ros`。
2. `Popen` 长期进程、`wait_topic()`、`sim_time_s()`、trigger 以及 runner 调用链内所有
   ROS CLI 子进程均显式继承该环境。`live_checks()` 内部命令也必须在对应环境中执行，
   但不得为此修改 `scripts/two_uav_preflight.py`。
3. 扩展纯函数/self-test：从两个不同 runroot 分别构造环境并证明不共享；模拟从 active
   state 恢复后仍得到原 runroot 路径；枚举 runner 的全部 `subprocess.run/Popen` 入口，
   证明不存在未绑定 ROS 环境的 ROS 命令。
4. 更新 source hash，并重新通过 py_compile、runner self-test、12/12 hash、53/53 静态
   preflight 和 `git diff --check`。

不得启动 ROS/Gazebo，不得修改 manifest、参数、approval package、receipt、旧 runroot、
`project_state.md` 或 `state/SESSION_HANDOFF.md`。完成后只更新 Terra 实现记录并交回 Sol。

## 10. 2026-08-21 第二次 preflight 失败归因与最小返工

### 决定

```text
runroot: results/RUN-20260821T060734Z-2uav-preflight
approved_new_preflight_package: false
approved_smoke: false
decision: BLOCKED_PENDING_RUNTIME_WIRING_AND_DETECTION_REWORK
primary_classification: RUNNER_ENVIRONMENT_COMPOSITION
secondary_classification: COLLECTOR_DETECTION_BIAS
workspace_baseline_change_required: false
```

一次性 approval package SHA-256
`3bf111dbe3d06e0f545ecc4a81cf4636e5a964b370af7dc0d1245b3403359e43`
已消费，不得复用。当前不得签发新 package。

### 审核输入与证据结论

本审核只读取 `state/execution_issue.md`、指定 runroot 的执行结果、live/fleet/abort 证据、
process/runtime 环境快照、日志摘要及定位所需源码；未修改源码或正式项目状态，未启动实验。

已确认的正向证据：静态 53/53、源码 12/12、唯一 `/clock`、sim time 单调、UAV0/UAV1
全部冻结参数与 50×50 环境参数回读、runroot ROS log/home 隔离、逐机/fleet 最终 metrics
落盘及 fail-closed abort/停栈均工作。preflight 仍为失败，不能进入 smoke。

首要故障归为 runner 环境组合，而不是要求先升级 workspace baseline：`swarm_ws` 和
`racer_ws` 的 `.catkin`/`_setup_util.py` 都只声明自身 source/devel 与 `/opt/ros/noetic`，
互不作为 underlay；无论 source 顺序如何，后 source 的 setup 都会移除前一 workspace。
本轮 `process_specs.json` 固定执行 `noetic → swarm_ws → racer_ws`，最终
`ROS_PACKAGE_PATH` 只剩 `racer_ws/src`，导致 `rospack find swarm_lio` 失败、两个 bridge
从未启动。两个工作区内容本身存在且单独 source 可解析，因此本轮不批准重建、改写或提交
公共 workspace baseline；runner 必须按实际独立 workspace 合同构造确定性组合环境。

另有两类独立缺口：

1. collector 最终 `process_death:/two_uav_gt_mapper` 是停机期检测偏差。gt_mapper 日志显示
   它存活至 runner 发出 signal-15；collector 的 `finalize()` 在各进程同时停机时再次调用
   `report()`，把正常 teardown 中已离开 ROS master 的节点追加为 process death。该项污染
   最终 abort reasons，但不是首个 abort。
2. 数据面/TF gate 不完整。GT mapper 直接订阅 `/uavN/livox/scan` 与 MAVROS odom，不依赖
   bridge；Gazebo 日志证明两架 iris 的 Livox 插件和 800000 点 scan pattern 已加载，故
   “world 无传感器”不是结论。但 topic 仅注册、无消息/同步回调证据，registered cloud/odom
   为零。GT mapper 也未发布合同要求的 `world → uavN/base_link` TF，而 live TF 检查对空集
   误判为 `no cross-talk`。这些缺口即使 bridge 修好仍会阻断下一次 preflight。

ACK owner 缺失本轮由 bridge 未启动直接造成；bridge 正常时会在 WAIT_TRIGGER 前创建
`/planning/command_ack_N` publisher，因此不得放宽 ACK owner 或 ACK timeout 合同。

### 允许修改

- `scripts/two_uav_runner.py`；
- `scripts/two_uav_preflight.py`；
- `scripts/two_uav_gt_mapper.py`；
- `scripts/two_uav_collector.py`；
- 上述文件的纯函数/self-test；
- `config/2uav_source_hashes.sha256`；
- `state/terra_implementation.md`。

不得修改 manifest、launch、world、`config/2uav_static.yaml`、冻结参数、任何 workspace
源码/devel/build/install、approval package、receipt、旧 runroot、`project_state.md`、
`state/current_summary.md` 或 `state/SESSION_HANDOFF.md`。

### 最小返工任务

1. **确定性 workspace 组合**：runner 为所有相关子进程构造同时包含 `swarm_ws` 与
   `racer_ws` 的 package、prefix、Python 和 library 路径，且保留 runroot
   `ROS_LOG_DIR`/`ROS_HOME`。不得依赖两次 setup 的先后顺序假装 extend。增加只读离线 probe，
   至少证明相同子进程环境下 `rospack find swarm_lio`、`rospack find exploration_manager`
   和 `import quadrotor_msgs.msg` 全部成功；将组合环境摘要写入未来 runroot。
2. **启动/数据面 readiness fail-closed**：runner 不得以 topic 名已注册代替消息流。等待
   bridge、GT mapper、RACER 时同时检查对应 launch 进程仍存活，并要求双机 raw scan、
   MAVROS odom、registered cloud/odom 与 frontier 至少获得真实消息；任一超时或进程退出，
   在 collector 启动前或 startup grace 内给出唯一、可审计错误并停栈。
3. **GT TF 合同**：GT mapper 对每架 UAV 使用同步后的 GT pose 发布唯一
   `world → uavN/base_link` 动态 TF，timestamp 与注册输出一致；不得发布跨 UAV parent，
   不得改变 20 m、水平全向、过滤或注册参数。补充双机 frame/pose 纯函数 probe及输入、
   同步、空点/有效输出计数诊断。
4. **live preflight 不得空集通过**：TF gate 必须要求两个预期 child 都存在、parent 恰为
   `world` 且各自唯一；required topics 除 owner 存在外，还必须证明关键数据面实际流动。
   空 TF、零消息或只注册 publisher 必须失败。
5. **collector liveness 分离**：活动期 watchdog 在 startup grace 后必须对“从未出现”或
   “出现后消失”的 expected node fail-closed，包括 bridge；正常 runner teardown/finalize
   只能固化最后一个活动期 liveness 状态，不得新增 `process_death`。增加真实运行期死亡、
   从未出现和正常停机三类纯函数 probe。不得放宽 freshness、TF、topic owner、ACK 或
   final safety 合同。

### 验证与下一门

Terra 只能做离线/静态验证，不得启动 roscore、ROS 节点、Gazebo、preflight 或 smoke：

- py_compile runner/preflight/gt_mapper/collector；
- 四个脚本的相关 self-test；
- 两 workspace 确定性组合环境的只读 `rospack`/Python import probe；
- source hash 12/12；
- 静态 preflight 全部通过（若检查数量改变，必须记录新总数和新增检查）；
- `git diff --check`；
- 记录完整 diff、源码 hash、probe 输出和残余风险到 Terra。

Sol 复审上述 diff 与新 source hash 后，才决定是否签发新的 `stage: preflight`、
`max_uses: 1` package；不得自动批准。任何新的 preflight 成功后仍须回 Sol 审核，smoke
继续禁止。

## 11. 第 10 节返工复审：readiness 监视语义仍未闭合

### 决定

```text
reviewed_source_hash_manifest_sha256: 21bd9d5838316db6999654f98d6216d86a5f67d943ab669dcceeca9300ba568c
reviewed_manifest_sha256: e366f943180cb1471742ab2a84e685d75e64442fd00c8bf75e14a00ee618a0f2
approved_new_preflight_package: false
approved_smoke: false
decision: REJECTED_PENDING_MINIMAL_READINESS_REWORK
```

本次只读复审确认：四脚本 `py_compile` 与 self-test 通过，双 workspace 同一 runroot-local
环境中的 `rospack find swarm_lio`、`rospack find exploration_manager`、
`import quadrotor_msgs.msg` 均通过，source hash 为 12/12，静态 preflight 为 53/53，
`git diff --check` 通过。GT mapper 已具备动态 TF 发布，live gate 对预期 TF exact-set 与关键
topic payload fail-closed，collector 也已把 active report 与 finalize teardown 分开。冻结
manifest 未修改；现有 package SHA-256
`3bf111dbe3d06e0f545ecc4a81cf4636e5a964b370af7dc0d1245b3403359e43`
已有 consumption receipt，仍不得复用。

但第 10 节第 2 项尚未满足：`wait_topic_message()` 在一次最长 12 秒的阻塞 echo 及总计
120/180 秒循环期间没有接收或检查任何 Popen；`start_stack()` 仅在整组消息等待结束后执行
一次 `process.poll()`，而且只检查刚启动的那个进程，不检查此前已启动的 Gazebo、GT mapper、
bridge。bridge 启动后也没有独立的 readiness 等待，立即进入 RACER 启动；因此 bridge 或
其他既有进程在 readiness 期间退出时，仍可能直到消息超时才以 `readiness no payload` 报告，
不符合“等待 bridge、GT mapper、RACER 时同时检查对应进程存活、给出唯一可审计错误”的合同。

另有两个必须随最小返工补齐的纯函数证据缺口：GT mapper self-test 只构造
`uav0/base_link`，未按任务包验证双机 child 唯一及各自 pose；preflight self-test 未覆盖
多 parent 和“topic 已注册但 echo 零 payload”负向语义。collector 的
`liveness_state()` 还使用更新前的 `seen` 计算 `never_seen`，导致一个当前已 live、首次观测到
的 expected node 在该帧仍被错误标成 never-seen；虽不改变该帧 `process_death` 集合，但会
污染审计字段和被 finalize 固化的最后活动快照。

### 最小返工范围

只允许修改：

- `scripts/two_uav_runner.py`；
- `scripts/two_uav_preflight.py` 的纯函数/self-test；
- `scripts/two_uav_gt_mapper.py` 的纯函数/self-test；
- `scripts/two_uav_collector.py` 的 `liveness_state()` 及 self-test；
- `config/2uav_source_hashes.sha256`；
- `state/terra_implementation.md`。

不得修改 manifest、launch、world、`config/2uav_static.yaml`、workspace、approval package、
receipt、旧 runroot、`project_state.md`、`state/current_summary.md` 或
`state/SESSION_HANDOFF.md`，不得启动 ROS、Gazebo、preflight 或 smoke。

### 最小返工要求

1. runner 将“消息 payload 等待 + 已启动进程存活检查”合为同一个可测试 gate；每个短轮询
   周期都检查所有已启动 Popen，任一退出立即返回包含进程名与 exit code 的唯一错误，不得等到
   topic 总超时。GT mapper、bridge、RACER readiness 都必须使用该 gate。
2. bridge 必须有明确 readiness：至少确认两个预期 bridge node 已出现，同时持续监视所有已
   启动 Popen；进入 RACER/frontier payload 等待后继续确保 bridge readiness 不丢失。不得以
   放宽 ACK owner/timeout 替代 bridge readiness。
3. runner self-test 使用 fake process/probe 覆盖：payload 成功、零 payload 超时、当前进程
   退出、此前进程退出及 bridge 两节点缺一；不得启动 ROS。
4. GT mapper self-test 同时构造 UAV0/UAV1 transform，断言 parent 均为 `world`、child 唯一、
   各自 position/orientation 正确且 timestamp 与同步输出一致。
5. preflight 将 payload 判定拆为纯函数并测试“topic 可见但 echo 成功且 stdout 为空”必失败；
   TF self-test 增加空集与同一 child 多 parent 拒绝。
6. collector 先形成 `updated_seen = seen ∪ (expected ∩ live)`，再计算 `never_seen` 与
   `lost_after_seen`；self-test 证明首次已 live 的节点不进入 never-seen，活动期缺失仍进入
   process-death，teardown 仍不新增 process-death。

完成后仅运行四脚本 py_compile/self-test、同一组合环境离线 probe、12/12 source hash、
53/53 静态 preflight 和 `git diff --check`，把 diff、hash、验证与残余风险追加到
`state/terra_implementation.md` 后交回 Sol。当前不得创建新的 approval package；smoke
继续禁止。

## 12. 第 11 节返工复审：gate 超时证据与 bridge 快照时序缺口

### 决定

```text
reviewed_source_hash_manifest_sha256: c7ba1e6d272b5679661fb5a172b35610daf42fddca58ad302844a0801188c361
reviewed_manifest_sha256: e366f943180cb1471742ab2a84e685d75e64442fd00c8bf75e14a00ee618a0f2
approved_new_preflight_package: false
approved_smoke: false
decision: REJECTED_PENDING_RUNNER_GATE_SELF_TEST_AND_POST_PROBE_NODE_CHECK
```

本次复审确认第 11 节的大部分返工合格：四脚本编译/self-test 通过，source hash 12/12，
静态 preflight 53/53，`git diff --check` 通过；双 workspace、GT TF、live payload、collector
liveness 修改与冻结 manifest 均符合边界。旧 package SHA-256
`3bf111dbe3d06e0f545ecc4a81cf4636e5a964b370af7dc0d1245b3403359e43`
的 receipt 仍存在，不得复用。

但 runner gate 还有两个相互关联的最小缺口：

1. 第 11 节要求 fake process/probe 覆盖“零 payload 超时”和“bridge 两节点缺一”。当前
   self-test 只直接调用 `readiness_state()` 并断言状态为 `waiting`，没有执行
   `wait_readiness()`，因此没有证明总 deadline 到达后确实抛出带 label/detail 的唯一超时，
   也没有覆盖 gate 的循环、终态 probe 与异常路径。
2. `wait_readiness()` 在 payload probe **之前**读取 bridge node 集合，然后在最长 3 秒的
   payload probe 返回后使用旧 node 快照决定 ready。bridge 在 probe 期间消失时，最后一次
   frontier gate 可能用旧快照通过。终态分支又把 payload 固定传为 `False`，即使 bridge gate
   的 payload probe 恒为 True，也可能产生误导性的 `no payload` detail。这不满足“frontier
   等待期间持续确保 bridge readiness 不丢失”和唯一可审计错误要求。

### 最小返工范围与要求

只允许修改：

- `scripts/two_uav_runner.py` 的 readiness gate 与 self-test；
- `config/2uav_source_hashes.sha256`；
- `state/terra_implementation.md`。

具体要求：

1. 每轮先执行 payload probe，再读取当前 bridge node 集合，最后由
   `readiness_state()` 检查所有 Popen、该次 payload 和 probe 后的 node 快照；ready 决定不得
   使用 probe 前的 node 快照。
2. deadline 后执行一次同语义的最终 probe，不得把 payload 硬编码为 False；若最终仍未 ready，
   错误必须为 `readiness timeout: <label>: <detail>`，若任一 Popen 已退出则仍优先返回包含
   name/exit code 的 process-exit 错误。
3. 为 `wait_readiness()` 注入纯函数 node/time/sleep probe 或采用等价无 ROS 设计。runner
   self-test 必须直接调用该 gate 并覆盖：payload 成功返回、零 payload deadline 超时、当前
   进程退出、此前进程退出、bridge 缺一个节点超时，以及 payload probe 期间 bridge 节点从
   完整变为缺失时不得 ready。不得启动 ROS。

不得改动 preflight、GT mapper、collector、manifest、launch、world、静态参数、workspace、
approval package、receipt、旧 runroot或正式状态文件。完成后仅运行四脚本 py_compile 与已有
self-test、组合环境离线 probe、12/12 source hash、53/53 静态 preflight、
`git diff --check`；追加 Terra 证据后交回 Sol。当前不签发新 package，smoke 继续禁止。

## 13. 2026-08-21 第三次 preflight 基础设施门失败与最小修复

### 决定与归因

```text
runroot: results/RUN-20260821T064604Z-2uav-preflight
consumed_approval_package: 8b3b75309100f43e68808f6380bc44bbfc2cda5de2b766d9ad665eabb07a4937
approved_new_preflight_package: false
approved_smoke: false
decision: BLOCKED_PENDING_PROBE_PREFIX_UNIFICATION
classification: RUNNER_VERIFY_ENVIRONMENT_COMPOSITION
workspace_baseline_change_required: false
```

本次只读取指定 runroot 的 `execution_result.md`、`workspace_environment_probe.json`、
`state/execution_issue.md`、消费 receipt 与定位所需 runner 源码；未启动实验，未修改源码或
正式状态。一次性 package `8b3b7530…a4937` 已由该 runroot 消费，不得复用。

失败发生在任何 ROS/Gazebo Popen 启动前。静态 preflight 53/53、冻结 identity、执行环境的
network/tmp probe 均通过；`runtime_environment.json` 也记录了包含 swarm_ws、racer_ws 与
Noetic 的正确组合路径。因此本次不是 workspace baseline、包缺失或 ROS graph 失败。

根因是 runner 内环境前缀漂移：`ros_command_spec()` 传入的 env 已含组合路径，但
`verify_workspace_environment()` 又执行 `source /opt/ros/noetic/setup.bash; <probe>`，Noetic
setup 在 probe 前把 `ROS_PACKAGE_PATH`/`PYTHONPATH` 等重置为仅 Noetic，导致三个离线 probe
全部失败。相反，`process_specs()` 使用
`source /opt/ros/noetic/setup.bash; <workspace_environment_exports>`，会在 source 后重导出
组合路径。证据明确要求统一前缀，而不是修改两个 workspace。

### 允许修改

只允许修改：

- `scripts/two_uav_runner.py` 的 runtime prefix、workspace probe 与对应 self-test；
- `config/2uav_source_hashes.sha256`；
- `state/terra_implementation.md`。

不得修改 preflight、GT mapper、collector、manifest、launch、world、
`config/2uav_static.yaml`、任何 workspace source/devel/build/install、approval package、
receipt、旧 runroot、`project_state.md`、`state/current_summary.md` 或
`state/SESSION_HANDOFF.md`。不得启动 roscore、ROS 节点、Gazebo、preflight 或 smoke。

### 最小修复要求

1. 抽出一个确定性的 runtime shell prefix：先 source `/opt/ros/noetic/setup.bash`，随后显式
   重导出 `workspace_environment_exports(runroot)` 的全部组合路径及 runroot-local
   `ROS_LOG_DIR`/`ROS_HOME`。`process_specs()` 与 `verify_workspace_environment()` 必须调用
   同一 helper，不能继续各自拼接近似命令。
2. workspace probe 的三个命令必须在该统一 prefix **之后**执行，并继续写
   `workspace_environment_probe.json`。任一失败仍 fail-closed，不得删除或放宽 probe。
3. runner self-test 必须证明：统一 prefix 中 Noetic source 位于组合环境 export 之前；
   `ROS_PACKAGE_PATH`、`CMAKE_PREFIX_PATH`、`PYTHONPATH`、`LD_LIBRARY_PATH`、`ROS_LOG_DIR`、
   `ROS_HOME` 均在 probe 前重导出；process specs 与全部 workspace probe specs 共享完全相同
   prefix；命令不含 `~/.ros`。
4. 离线验证必须使用 runner 生成的**实际 probe argv+env**（不得另写一套手工环境命令）执行
   `rospack find swarm_lio`、`rospack find exploration_manager`、
   `import quadrotor_msgs.msg`，三项全部成功，并记录 stdout/stderr/return code。该验证不需要
   ROS master，也不得启动 ROS 节点。

### 验证与下一门

仅运行：runner py_compile/self-test、上述实际 probe helper 的离线执行、source hash 12/12、
静态 preflight 53/53 和 `git diff --check`。把 diff、hash、完整 probe 输出与残余风险追加到
`state/terra_implementation.md` 后交回 Sol。

Sol 复审新 source hash 与证据后才可签发新的 `stage: preflight`、`max_uses: 1` package；
不得复用 `8b3b7530…a4937`，不得自动执行 preflight，smoke 继续禁止。

## 14. 2026-08-21 第四次 preflight：Livox headless 激活合同与公共 baseline 最小修复

### 决定与归因

```text
runroot: results/RUN-20260821T065748Z-2uav-preflight
consumed_approval_package: 0944b9c08b0646efaaf82494cdca38c0263efa7f6dbc6f4a42ad0f05dd2ef79b
approved_new_preflight_package: false
approved_smoke: false
decision: BLOCKED_PENDING_ENVIRONMENT_BASELINE_REPAIR
classification: MODEL_HEADLESS_SENSOR_ACTIVATION_CONTRACT
csv_parser_is_primary_cause: false
plugin_source_change_required_now: false
```

本次只读审计确认 runner 的静态门、workspace probe、Gazebo/PX4/MAVROS 启动及 fail-closed
readiness 均按合同工作；失败点是 headless Gazebo 中 `/uav0/livox/scan` 在 120 秒内无
payload。一次性 package `0944b9c0…ef79b` 已消费，永久不得复用；本节不批准 smoke，也不
签发新的 preflight package。

执行报告把 `cannot convert str:` 解释为 CSV 解析中断，该解释不成立：CSV reader 使用
`while (!file_stream.eof())`，有效数据读完后会额外处理一个空字符串并打印该行；紧随其后的
`data size:800000` 与插件的 `scan info size:800000` 证明 800000 条有效扫描模式已经全部
装载。`mid360.csv` 的 SHA-256 为
`aa1fc08b6a4400608dbd6ee832b7ea3a9c3c37197e734f60f58fe5abf762269a`。既有成功单机
runroot 的 Gazebo 日志也同时出现同样的空 EOF 告警、`data size:800000` 和
`scan info size:800000`，并留下 downstream PointCloud2/registered cloud/odom owner
证据。因此不得通过删除 CSV 末行、跳过坏行或放宽 raw payload gate 来“修复”。

最小因果差异位于模型运行模式：已知成功单机启动了 `gazebo_gui (gzclient)`；当前 2-UAV
launch 明确 `gui=false`。PX4 `iris.sdf.jinja` 的 Livox `sensor type="ray"` 只有
`visualize=true` 与 `update_rate=10`，其 sensor 直接子项没有 `<always_on>true</always_on>`；
日志显示 ROS publisher 注册成功，但插件 `OnNewLaserScans()` 从未留下任何 payload。该插件
一旦收到 sensor update，会无条件执行 `rosPointPub.publish(scan_point)`。故最小、可证伪的
修复是在共享 iris 模型中显式声明 ray sensor headless always-on，而不是先改插件解析器。

该模型、插件二进制和 CSV 当前未被 `racer_outdoor_50x50_v1` 完整钉住；此外
`livox_laser_simulation` workspace 已存在用户的未提交修改。按照 single/multi 共用公共环境
版本的规则，本缺陷归环境 baseline owner，不能由 multi 仓库静默吸收，也不得覆盖或回滚
既有 workspace 修改。

### 环境负责人允许的最小修改

第一阶段只允许环境负责人处理下列对象：

- PX4 模型源
  `/home/houslakers/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models/iris/iris.sdf.jinja`
  中 Livox ray sensor 的直接子项；
- 公共环境清单
  `/home/houslakers/auto_tune_racer/racer-platform/environment/baselines/racer_outdoor_50x50_v1.yaml`
  的 component identity/contract；若该 baseline 已被发布为不可变版本，则创建一个新版本并
  保留 v1，不得原位伪装同一身份；
- `state/terra_implementation.md`，仅记录 diff、hash、验证和残余风险。

唯一功能改动是在 Livox ray sensor 内加入 `<always_on>true</always_on>`。不得改变
`update_rate=10`、24000 samples、downsample、360 度水平视场、量程、噪声、frame、相对
`livox/scan` topic、两机 namespace、50x50 world 或任何单机 20 m/水平全向参数。生成 SDF
必须由既有 PX4 generator 从 jinja 产生；不得仅手改 `iris.sdf.last_generated`，也不得把
generated artifact 当作源。

公共 baseline 清单必须记录并校验：模型源/实际生成 SDF identity、
`liblivox_laser_simulation.so` identity、插件对应源码 commit 或完整 dirty diff/hash、
`mid360.csv` identity，以及 Livox sensor 的 `always_on=true`、topic/type/rate 和双机唯一
namespace/frame 合同。实施前先保存 `livox_laser_simulation` 当前 dirty inventory；不得
reset、checkout、覆盖这些既有修改。本阶段禁止修改 CSV、CSV reader、插件发布逻辑、multi
manifest/config/launch/runner、approval package、receipt、旧 runroot或正式状态文件。

### 离线验证与升级路径

环境负责人不得在本任务包内启动 ROS、Gazebo、preflight 或 smoke。只做：

1. 渲染 mavlink ID 1/2 的 iris SDF，证明两个 Livox ray sensor 各自且仅有一个直接子
   `always_on=true`，sensor/frame 唯一，topic 保持相对 `livox/scan`；
2. 对渲染 SDF 做 SDF schema check，并证明 samples/downsample/range/update_rate 与修复前
   完全一致；
3. 离线解析 `mid360.csv`，证明 header 后恰有 800000 个合法三元组，并明确空 EOF 告警只是
   reader 日志噪声；
4. 记录模型、生成 SDF、CSV、插件源码/dirty diff、插件二进制和公共 baseline 清单的完整
   SHA-256；执行相关静态 self-test 与 `git diff --check`；
5. 将全部命令、输出、diff、hash 和“尚未获得 headless raw payload 运行证据”的残余风险
   写入 Terra 文档后交回 Sol。

Sol 先审核环境修复及公共 baseline 身份，再单独授权 Terra 只更新
`experiments/manifests/2uav_smoke.yaml`、`config/2uav_static.yaml` 和 source hash 中必要的
baseline 引用；不得修改单机参数。只有 single 与 multi 均引用同一公共环境版本且静态合同
通过后，Sol 才可签发一个新的 `stage: preflight`、`max_uses: 1` package，以 headless
双机 raw scan payload 作为运行证伪门。若加入 `always_on` 后仍为零 payload，停止扩大修改，
回到 Sol，以最小 callback/publication instrumentation 区分“sensor update 未触发”与
“插件回调内失败”；不得预先把 parser 清理与本修复捆绑。preflight 未成功复审前，smoke
持续禁止。

## 15. 第 14 节环境修复复审：功能合格，待身份重绑与 scoped diff 闭环

### 审核决定

```text
reviewed_runroot: results/RUN-20260821T065748Z-2uav-preflight
consumed_approval_package: 0944b9c08b0646efaaf82494cdca38c0263efa7f6dbc6f4a42ad0f05dd2ef79b
environment_repair_semantics: accepted
approved_new_preflight_package: false
approved_smoke: false
decision: BLOCKED_PENDING_BASELINE_IDENTITY_REBIND
```

第一阶段功能修改符合第 14 节边界：Livox ray sensor 只增加一个直接子项
`<always_on>true</always_on>`；双机渲染后分别得到唯一 `laser_livox_0/1` 与
`uav0/1/laser_livox`，`update_rate=10`、24000 samples、downsample、视场、量程、相对
`livox/scan` 均未变化。两个渲染 SDF 的 `gz sdf -k` 退出码为 0，XML 合同 probe 通过；
`mid360.csv` 严格解析得到 800000 个合法三元组。插件源码、CSV、单机参数、multi launch/
runner 和旧 runroot 均未被本阶段修改。公共 baseline 仍为未发布、runtime-pending 身份，允许
在最终冻结前补齐组件合同。

当前不能签发 package，原因不是功能返工失败，而是 identity chain 尚未闭合：公共 baseline
实际 SHA-256 已从 manifest/static 仍声明的
`48d00fca6032c76f59ca26134ff39dba2d555a552c2d73f81e3ca51b4583dc44`
变为
`654346f749fdf7a5f313fb72688e10a0f83315081851747d122637945f3fd114`。
因此现有静态 source hash 虽仍为 12/12，也只证明旧 manifest/config 自洽，不能证明它们绑定了
新的 Livox 环境合同。

PX4 Gazebo 子模块的 iris 模型与其它文件在本任务前已有大量用户修改，不能 reset、checkout
或覆盖。审计确认本次新增 `always_on` 行本身无 whitespace 问题，但同一 Livox 模型块内两条
既有空白行（当前模型第 661、664 行）使该目标文件的 scoped `git diff --check` 失败；允许在
第二阶段只删除这两行的尾随空格。子模块其它文件（包括既有
`launch/multi_uav_mavros_sitl.launch`）的 diff 不属于本次执行路径，不得为追求全子模块 clean
而改动；必须记录其未纳入 package identity 的事实。multi 仓库当前全量 `git diff --check`
无输出。

### 第二阶段允许修改

- PX4 Gazebo 子模块 `models/iris/iris.sdf.jinja`：只删除 Livox 块两条空白行的尾随空格；
  不得改变任何 XML 值或再增加功能修改；
- 公共 baseline `environment/baselines/racer_outdoor_50x50_v1.yaml`：更新上述机械清理后模型
  模板及 mavlink ID 1/2 渲染 SDF 的 SHA-256；
- `experiments/manifests/2uav_smoke.yaml`：只把 `environment_baseline.manifest_sha256`
  更新为最终公共 baseline SHA；不得改变参数、命令白名单、时长、重复数或 approval 状态；
- `config/2uav_static.yaml`：只更新 `environment.baseline_manifest_sha256` 为同一最终 SHA；
- `config/2uav_source_hashes.sha256`：只更新受影响的 static contract 与唯一 manifest hash；
- `state/terra_implementation.md`：追加 diff、最终 hash、验证与残余风险。

不得修改 CSV、CSV reader、插件源码/二进制、world、其它 launch、runner/preflight/collector/
GT mapper、冻结 20 m 水平全向参数、approval package、receipt、旧 runroot、
`project_state.md`、`state/current_summary.md` 或 `state/SESSION_HANDOFF.md`。不得 commit、push，
不得启动 ROS、Gazebo、preflight 或 smoke。

### 验证与下一门

1. 用既有 `jinja_gen.py` 重新渲染 mavlink ID 1/2 到 `/tmp`；运行 `gz sdf -k` 与 XML probe，
   再次证明双机 sensor/frame 唯一及所有冻结 LiDAR 数值不变。
2. 严格解析 CSV 800000/800000；核对插件 source commit、完整 dirty diff hash和 binary hash
   未变化。
3. PyYAML 读取公共 baseline、manifest、static contract，证明三者使用完全相同的最终 baseline
   SHA，且公共 baseline 内 model/render/CSV/plugin identities 与实物一致。
4. `sha256sum -c config/2uav_source_hashes.sha256` 必须 12/12；静态 preflight 必须 53/53。
5. 运行 multi 仓库全量 `git diff --check`、公共 baseline no-index diff check、PX4
   `iris.sdf.jinja` scoped diff check，三者必须无输出。另行记录 PX4 子模块其它既有 diff-check
   债务，不得把它误报为本任务已清理。

完成后交回 Sol 复审。只有最终 baseline identity chain、53/53 静态 preflight 和上述 scoped
diff checks 全部通过，Sol 才可新建一个 `stage: preflight`、`max_uses: 1` package；不得复用
`0944b9c0…ef79b`。该 package 也只能用于 headless 双机 preflight，smoke 仍禁止。

## 16. 2026-08-21 第五次 preflight：live TF CLI 采样偏差最小修复

### 决定与归因

```text
runroot: results/RUN-20260821T074112Z-2uav-preflight
consumed_approval_package: 1718c1cfda987f61650c8c39becddfc2d6ac6883938fdffd0bc4af860c2c3b10
approved_new_preflight_package: false
approved_smoke: false
decision: BLOCKED_PENDING_TF_SAMPLER_REPAIR
classification: LIVE_PREFLIGHT_COLLECTOR_DETECTION_BIAS
runtime_tf_contract_observed: true
```

本轮的 workspace probe、静态 53/53、双机 readiness 数据流、参数回读、日志隔离、
24 s watchdog soak、final metrics 与 final safety 全部通过；唯一失败为
`live.tf_expected_unique_dynamic_edges`。一次性 package `1718c1cf…3b10` 已由该
append-only runroot 消费，不得复用。审核时无 active lifecycle，不批准 smoke。

系统 TF 合同实际满足：`fleet/metrics.json` 由 collector 的 ROS TF 回调记录
`uav0/base_link: [world]`、`uav1/base_link: [world]`，两者 `tf_last_wall_s` 均有新鲜数值，
全程没有 `missing_tf` 或 `namespace_or_tf_cross_talk` abort。live gate 却解析为两个
空 parent set。根因是 `tf_parent_sets()` 执行
`rostopic echo -n 10 /tf --noarr`；`--noarr` 排除数组，而 `tf2_msgs/TFMessage` 的唯一
载荷字段正是 `TransformStamped[] transforms`，所以后续 regex 必然观测不到
`frame_id`/`child_frame_id`。这是 preflight collector 的检测偏差，不是 TF 发布、
GT mapper、namespace 或 baseline 故障。

### 允许修改

- `scripts/two_uav_preflight.py` 的 TF CLI 采样、纯解析 helper 和 self-test；
- `config/2uav_source_hashes.sha256` 中 `two_uav_preflight.py` 这一项 hash；
- `state/terra_implementation.md` 的 diff、hash、验证和残余风险。

不得修改 runner、collector、GT mapper、manifest、static contract、launch、world、公共
baseline、PX4/Livox workspace、CSV、插件、冻结 20 m 水平全向参数、approval package、
receipt、旧 runroot、`project_state.md`、`state/current_summary.md` 或
`state/SESSION_HANDOFF.md`。不得 commit/push，不得启动 ROS、Gazebo、preflight 或 smoke。

### 最小修复要求

1. `tf_parent_sets()` 的 `rostopic echo` argv 从 `/tf` 采样完整 TFMessage，移除
   `--noarr`；保留有限消息数、5 s timeout 和 timeout 时解析 partial stdout 的语义。
2. 将 TF YAML 文本到 `{child: {parents}}` 的转换拆为纯函数。不得通过引用
   `fleet/metrics.json` 使 live gate 与 collector 共用同一证据源；两者必须保持独立。
3. 解析必须保留完整 frame 名，并累积同一 child 的所有 parent；不得过滤
   错 parent 或多 parent。`expected_tf_contract()` 的 exact-set fail-closed 语义不得改动。
4. self-test 必须用包含 `transforms:` 数组的真实 rostopic YAML fixture 覆盖：双机
   `world→uavN/base_link` 解析成功；空输出 fail-closed；缺一 child、错 parent、
   同一 child 多 parent 全部失败；采样 argv 包含 `/tf` 且不包含 `--noarr`。
5. 不得改动 `topic_has_payload()` 中针对大点云等普通 topic 的 `--noarr`；该处只用于
   证明非空 payload，与 TFMessage 内容解析不同。

### 离线验证与下一门

Terra 只能运行：

- `PYTHONPYCACHEPREFIX=/tmp/... python3 -m py_compile scripts/two_uav_preflight.py`；
- `python3 scripts/two_uav_preflight.py --self-test`；
- 纯函数 fixture/probe，证明 argv 不再排除 transforms 数组及 exact-set 语义；
- `sha256sum -c config/2uav_source_hashes.sha256` 12/12；
- 静态 preflight 53/53；
- multi 全量 `git diff --check`。

完成后把精确 diff、新 preflight/source-hash manifest SHA、验证输出和“真实 `/tf`
CLI 采样仍需一次新 preflight 验证”的残余风险写入 Terra 文档，交回 Sol。Sol 复审
后才能新建 `stage: preflight`、`max_uses: 1` package；不得复用
`1718c1cf…3b10`，不得自动执行，smoke 继续禁止。

## 17. 2026-08-21 第六次 preflight：无 goal frontier freshness 合同适配

### 决定与归因

```text
runroot: results/RUN-20260821T075253Z-2uav-preflight
consumed_approval_package: bc75e406c7f9d94d4514abfd57588d23b7791f7af7216667ea6a5cb08a70713b
approved_new_preflight_package: false
approved_smoke: false
decision: BLOCKED_PENDING_FRONTIER_CHANNEL_CLASSIFICATION_REPAIR
classification: COLLECTOR_CONTRACT_MISMATCH_AMPLIFIED_BY_LOW_REALTIME_FACTOR
```

本轮不是双机 namespace、进程、workspace、Livox、TF 或参数接入失败。静态 53/53、workspace
probe、两机 raw cloud/MAVROS odom/registered cloud/odom/frontier payload、16×2 参数回读、
日志隔离和唯一 `world→uavN/base_link` 动态 TF 均通过；8/8 必需节点存活，topic owner
未漂移。唯一原始 abort 是 `corrupted_telemetry:uav0:freshness`：uav0 的 cloud/odometry/
health/occupancy 仍在更新，frontier 已累计 585 条后超过 5 s wall 未更新。

`/planning_vis/frontier_N` 的消息类型和发布位置表明它是规划可视化/状态型 Marker，而不是
固定频率心跳。RACER 在 `computeFrontiersToVisit()` 得到空集合时记录
`No coverable frontier.` 并提前返回；同时无 goal preflight 明确处于 `wait for trigger`。
因此“启动后曾有真实 frontier payload”可证明接线和 namespace，后续无新 Marker 并不能
单独证明 exploration node 或数据链路死亡。当前 collector 已对 WAIT_TRIGGER 中静默的
trajectory/pos_cmd/ack 做阶段适配，却仍把 frontier 硬编码为每 5 s 必须更新，属于 channel
分类遗漏。

模拟实时因子约 0.33 是放大因素：最后一段约 5.3 s sim 时间消耗约 15.7 s wall，并出现
大量 A* timeout/一次 61798 iterations，足以把 Marker 发布间隔放大到 wall freshness 门外；
但进程、TF、cloud 和 odometry 同期持续存活，所以不能把本轮归类为全局调度崩溃。不得用
提高全局 `freshness_s` 或按 RT 比例缩放阈值来掩盖问题，否则会同时削弱关键连续遥测和未来
command/ACK 的 fail-closed 能力。RT 0.33 作为 smoke 前性能风险保留，不在本最小修复中调参。

### 最小修复与允许范围

只允许修改：

- `scripts/two_uav_collector.py` 的遥测 channel 分类纯函数、snapshot/watchdog 组合及 self-test；
- `config/2uav_source_hashes.sha256` 中 collector 对应 SHA-256；
- `state/terra_implementation.md`，追加精确 diff、hash、验证与残余风险。

不得修改 RACER/exploration publisher、单机源码或参数、`freshness_s=5.0`、
`tf_freshness_s=5.0`、command ACK 1.0 s、manifest、`config/2uav_static.yaml`、runner、
preflight、GT mapper、launch/world、公共环境 baseline、approval package、receipt、旧
runroot、`project_state.md`、`state/current_summary.md` 或 `state/SESSION_HANDOFF.md`。
不得 commit/push，不得启动 ROS、Gazebo、preflight 或 smoke。

具体语义：

1. 将 telemetry 合同显式拆为 `continuous freshness` 与 `startup presence` 两类。连续类保持
   `odometry/cloud/health/occupancy`；首次 PositionCommand 后且 completion 前，原样加入
   `trajectory/pos_cmd/ack`。这些通道继续按现有 wall 5 s/ACK 1 s fail-closed。
2. `frontier` 只进入 startup-presence 类：startup grace 后若从未收到过必须 fail-closed；
   收到至少一条后不再以 wall 5 s 判 stale。不得删除 frontier 订阅、计数、逐机证据或
   readiness payload 门。
3. topic-owner 合同必须继续覆盖 `/planning_vis/frontier_1/2` 且要求恰好一个 publisher；
   `/exploration_node_1/2` 必须继续由活动期 liveness 门监控。不得把“曾见过一次”扩大成
   owner 缺失、node death 或 topic drift 的豁免。
4. `telemetry_complete` 必须同时要求：所有 continuous channel 新鲜、所有 startup-presence
   channel 曾出现、现有 ACK/coverage/TF/owner/liveness 合同无放宽。输出需单独列出
   `telemetry_stale_channels` 与 `telemetry_missing_channels`（或等价、可审计的两个字段），
   避免把 presence 缺失伪装成 freshness。
5. self-test 至少覆盖：frontier 从未出现时失败；frontier 出现一次后即使时间超过 5 s，
   无 goal/WAIT_TRIGGER snapshot 仍通过；任一 continuous channel 超时仍失败；首次 command
   后 trajectory/pos_cmd/ack 仍受原 freshness/ACK 合同约束；completion 后的现有语义不回退。

### 离线验证与重新签发门

Terra 只能运行：

- `PYTHONPYCACHEPREFIX=/tmp/... python3 -m py_compile scripts/two_uav_collector.py`；
- `python3 scripts/two_uav_collector.py --self-test` 及上述纯函数负向 probes；
- `sha256sum -c config/2uav_source_hashes.sha256`，必须 12/12；
- 静态 preflight，必须 53/53；
- multi 工作树 `git diff --check`。

Terra 完成后交回 Sol 审核。Sol 只有在范围、diff、source identity 和全部离线验证合格后，
才签发一个新的 `stage: preflight`、`max_uses: 1` package；不得复用
`bc75e406…a70713b`。新 package 只能再次运行
`python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml`。
验收要求是静态 53/53、全部 live checks、24 s no-goal watchdog soak、final safety 全通过，
frontier 每机至少观测一次且 owner/liveness 持续满足。执行结果必须记录 wall/sim 推进量与
实际 RT factor；RT 低不会放宽安全门，若仍约 0.33，则在任何 smoke 审批前单独评估主机负载
和 command/ACK wall-time 风险。本节不批准 smoke。

## 18. 2026-08-21 preflight 通过复审与单次 smoke 决策

### 审核结论

```text
runroot: results/RUN-20260821T082048Z-2uav-preflight
preflight_checks: 48/48 PASS
static_checks: 53/53 PASS
consumed_preflight_package: 57a21fa5fb90400fafb589df8beeaaecebc0f0e50084240b6905db6afe8b9fa4
approved_smoke: true
scope: one manifest-bound 120 sim-second smoke only
```

该 preflight 已证明双机静态接入合格：无 abort，无丢失节点，两机数据流、唯一 TF、
topic owner、参数回读、日志隔离、24 s no-goal soak、逐机/fleet telemetry 与 final safety
全部通过。两机 frontier 分别收到 815/912 条，missing/stale 均为空；8/8 节点存活，
两机均无 crash/contact，最小机间距离 1.471 m。

现有证据仍没有 goal 后的 trajectory、PositionCommand、ACK、真实机体运动、completion、协同覆盖或
运动期安全语义；preflight 中两机三个 command channel 计数均为 0。因此一次 smoke 是必需的
下一门，不能以 preflight 直接宣称 fleet 功能验证通过。

### RT factor 风险判定

soak 中 10.00 sim s 消耗 32.7 wall s，RT factor 约 0.306。按同等负载，manifest 固定的
120 sim s smoke 约需 392 wall s；runner wall watchdog 为 1200 s，具有有界停止路径。该负载
可能使运动期 A*/callback 调度与 1 s wall ACK 合同发生冲突，但这正是 smoke 必须暴露的
运行风险。不得预先放宽 freshness/ACK、缩短 manifest 或修改单机参数。若 ACK 超时、关键
遥测/TF 过期、进程死亡、碰撞或 sim 无法在 1200 s wall 内推进，必须 fail-closed 停栈。

### 唯一允许的 smoke 与成功标准

保持 `experiments/manifests/2uav_smoke.yaml` 的 `duration_sim_s=120`、`repetitions=1`、seed、
冻结参数、50x50 公共环境、安全阈值和 source identity 不变。Sol 可签发一个
`stage: smoke`、`allowed_actions: [launch]`、`max_uses: 1` package，且只允许一次：

```text
python3 scripts/two_uav_runner.py launch --manifest experiments/manifests/2uav_smoke.yaml
```

启动后必须先通过内嵌 live checks 与 24 s no-goal soak，才能发布 goal。只有
`exit_reason=duration_complete`、final safety 通过、无 abort/crash/severe contact/process death/TF 或 owner
cross-talk、两机 command/ACK 合同通过，且逐机 completion/freeze/crash/contact/coverage/telemetry
与 fleet coverage/overlap/min-distance/map-consistency 都有原始证据，才可进入结果报告。

无论成功或失败，package 一经消费不得重试；必须停栈、保留 append-only runroot、记录
wall/sim 推进量和 RT factor，然后交回 lead 审核。不得扩展到第二次重复、长跑、参数搜索、
commit/push 或正式状态合并。

## 19. 2026-08-21 首次 2-UAV smoke 失败审计与最小闭环

### 审核结论

```text
runroot: results/RUN-20260821T083254Z-2uav-smoke
exit_reason: abort_requested
sim_interval: 12.39 -> 32.39 / 120 s
wall_elapsed: about 59 s
effective_rt_factor: about 0.339
consumed_smoke_package: 3986a46c53dd3c7cfae9dbc03eb388fe80327fc2d2f784b8506a01a8b3988038
new_approval_package: forbidden pending report, repair, and review
```

本轮不是 namespace、TF、topic owner、进程存活、ACK、碰撞或日志隔离失败。内嵌 preflight
通过 46/46，8/8 必需节点在 abort 时仍存活，两机均无 crash/contact/crosstalk。失败必须拆成
三个不能互相替代的事实：

1. **直接 abort 是 collector 合同误判。** uav0 在 sim 30.092 接受一条
   `start=28.610, duration=4.699 sim s` 的 B-spline，并从 sim 30.101 持续产生
   PositionCommand/ACK；abort 发生在 sim 32.39，早于该轨迹的计划结束约 sim 33.309。
   `/planning/bspline_1` 是事件型轨迹下发，不是 5 s wall
   心跳；RT factor 约 0.339 时，5 s wall 只推进约 1.7 sim s。因此将 `trajectory` 放入连续
   freshness 集合，必然可能在一条仍合法执行的轨迹中途触发
   `corrupted_telemetry:uav0:freshness`。这属于 collector contract mismatch，RT 低只是放大器。
2. **uav0 随后的规划失败是真实问题。** 日志中的 A* timeout/no path、failure memory 和
   `Plan fail` 不能因上述误 abort 被忽略；但它们不是本次 abort.request 的直接触发器，也
   不能通过提高全局 freshness 阈值处理。
3. **uav1 未接令是真实双机接入缺口。** uav1 在 goal 后 trajectory/PositionCommand/ACK
   始终为 0，规划器反复报告其当前坐标约 `[1.5, 0, 1.5]` 位于 inflated occupancy 内。
   50x50 world 的该起点附近没有静态墙体；结合 Gazebo Livox、共享 registered cloud/map
   链路，当前首要假设是另一架 iris 的机体回波被当成静态占据并进入共享地图，使停留中的
   uav1 自身位置被 peer-generated occupancy 覆盖。该项是证据支持的首要假设，不是已证明
   结论；必须用实际机体附近点计数/剔除证据确认，禁止直接移动出生点或调膨胀参数碰运气。

只修 `trajectory` 分类然后重跑并不足以宣称双机成功：现有 collector 对从未进入 command
阶段的 uav1 仍可给出 telemetry complete，而 manifest 没有把 freeze 列为即时 abort 条件。
因此下一次 smoke 前必须同时修正事件通道语义、消除或证伪 peer-body map contamination，
并增加“每机实际进入命令闭环”的最终有效性门。

### 阶段 A：Luna 只读结果复盘（必须，且不重复实验）

先交给 `result-reporting`，只读本 runroot，生成本轮结构化结果总结。报告至少应固定：

- goal、首次 B-spline、首次 PositionCommand、最后 trajectory event、abort 的 wall/sim 时间线；
- uav0/uav1 的 trajectory、PositionCommand、ACK、motion、freeze、completion、coverage；
- A* timeout/no path 与 uav1 `start inside inflated occupancy` 的逐机归属；
- RT factor 对 5 s wall freshness 的换算，明确“误 abort”与“真实规划失败”是并存问题；
- TF、owner、node liveness、contact/crash、最小机间距离和 fleet coverage 证据。

Luna 不得修改原始 runroot、源码、参数、approval/receipt 或正式状态文件。该报告用于固化本轮
证据，不替代 Terra 的源码修复，也不批准重试。

### 阶段 B：报告复审后的最小修复任务边界

Sol 复审 Luna 报告后，才可向 Terra 签发一个源码返工任务。建议允许范围仅为：

- `scripts/two_uav_collector.py` 的 channel 分类及 self-test；
- `scripts/two_uav_gt_mapper.py` 的多机机体回波诊断/剔除及纯函数 self-test；
- `scripts/two_uav_runner.py` 的 smoke 最终双机功能有效性门及 self-test；
- `config/2uav_source_hashes.sha256` 中对应 hash；
- `state/terra_implementation.md` 的审计证据。

具体要求：

1. `trajectory` 改为 command 阶段的 presence/event 证据：每机进入 command 阶段后必须至少
   收到一条，但不得再按 5 s wall 连续 freshness 监管。`pos_cmd`、`ack`、ACK 1 s、odom、
   cloud、health、occupancy 的连续 fail-closed 语义保持不变。
2. GT mapper 必须先输出可审计的 self/peer 机体邻域点计数，再只剔除由当前双机实时位姿和
   已冻结 iris 模型碰撞外形导出的紧致机体包络内点。禁止使用任意调大半径、清空起点周围
   地图、降低 inflation、扩大出生间距或删除真实静态障碍的做法。若离线/纯函数证据无法
   支持 peer-body 假设，Terra 必须停止在诊断实现并交回 lead，不得猜测性改变地图。
3. runner 的 smoke 最终有效性必须要求每架 UAV 均有 `trajectory>0`、`pos_cmd>0`、`ack>0`
   且无 ACK timeout；任一 UAV 从 goal 到结束始终未进入命令链时，必须结果失败，不能由
   `telemetry_complete=true` 掩盖。是否将 freeze 升为即时 abort 不在本次静默扩大；freeze
   继续逐机记录，并由最终结果审计结合 completion/command/motion 判定。
4. 不得修改单机/RACER 参数、`config/2uav_static.yaml`、manifest、launch/world、spawn、
   freshness/ACK 阈值、公共环境 baseline、旧 runroot、approval/receipt 或正式状态文件。
   不得现场调参，不得启动 ROS、Gazebo、preflight 或 smoke。

Terra 离线验收至少包括相关脚本 `py_compile`、全部相关 self-test、peer-body 几何正/负向
纯函数 probes、12/12 source hash、53/53 静态 preflight 和 `git diff --check`。完成后必须
交回 Sol 审核。

### 新 package 决策

当前不签发任何 package。已消费的
`3986a46c53dd3c7cfae9dbc03eb388fe80327fc2d2f784b8506a01a8b3988038` 永久禁止复用。
Luna 报告、Terra 最小修复和 Sol diff/验证复审全部合格后，应先签发新的单次
`stage: preflight` package，重新验证无 goal 接入与 watchdog；只有该 preflight 通过且
机体回波诊断/剔除证据成立，才另行决定是否签发新的单次 `stage: smoke` package。
任何一步失败都返回 lead，不允许同包重试或绕过 preflight。
