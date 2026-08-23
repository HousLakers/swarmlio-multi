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

## 26. 2026-08-22 final metrics 的 occupancy freshness 停栈边界修复

### 审核决定

```text
runroot: results/RUN-20260821T172635Z-2uav-preflight
approved_new_preflight_package: false
approved_smoke: false
decision: REJECTED_PENDING_FINAL_FRESHNESS_REFERENCE_FIX
consumed_package: 29fedcceda8b1d622c65909785e7dd86dc9e6b97756e679d61253942a298a799
```

本轮 static 53/53、live readiness、双机 payload/TF/参数/日志隔离、24 s watchdog soak 和
final metrics 均通过；仅 `final.safety` 失败。运行期 7 个 fleet telemetry 周期快照全部
`telemetry_completeness=true`，两机 occupancy 均持续增长，且无 abort/crash/contact/process
death。最终失败只发生在 runner 已开始停栈之后：collector 的 `finalize()` 重新以更晚的 wall
clock 调用 `snapshot()`，把 uav0 最后一条低频 occupancy 判为超过统一 5 s freshness。该证据不支持
把 occupancy 永久降级为 presence，也不支持放宽全局 5 s 合同；它证明 final metrics 不应把 teardown
耗时算入运行期通道 freshness。

### 目标与允许修改

目标：final metrics 的通道 freshness 使用“最后一次 active watchdog/report 的 wall-time reference”，
而计数、coverage、crash/contact、ACK timeout 和其他最终状态仍在 finalize 时重新采样；运行期 watchdog
的统一 5 s freshness、occupancy 连续通道分类和 fail-closed 行为保持不变。

Terra 只允许修改：

- `scripts/two_uav_collector.py`：保存最后一次 active report 的 freshness reference，并仅在
  `finalize()` 的 stale-channel 计算中复用该 reference；
- `config/2uav_source_hashes.sha256`：只更新 collector hash；
- `state/terra_implementation.md`：追加 diff、验证、identity 和残余风险。

不得修改 runner/preflight/mapper、manifest、static config、`freshness_s: 5.0`、occupancy/frontier/
trajectory 合同分类、readiness/soak 时长、RACER/单机参数、launch/world/baseline、approval package、
receipt、旧 runroot 或正式状态文件；不得启动 ROS、Gazebo、preflight、smoke，不得 commit/push。

### 最小实现与成功标准

1. `VehicleState.snapshot()` 可接受显式 freshness reference；只用它计算 continuous channel stale，
   ACK timeout、freeze、计数、coverage 和最终安全状态仍使用 finalize 当前时间/状态。
2. collector 每次 `report(active=True)` 在同一个 reference 下生成两机报告并记录该 reference；
   `report(active=False)` 只能在已有 active reference 时复用它。若从未形成 active report，不得伪造
   complete，仍须 fail-closed。
3. 运行期任何 occupancy 超过 5 s 仍触发既有 `corrupted_telemetry:<uav>:freshness`；不得通过缓存
   complete、跳过 occupancy 或修改阈值绕过 watchdog。
4. self-test 覆盖：active reference 内 occupancy complete；模拟 teardown 延迟超过 5 s 后 final
   freshness 仍等于最后 active 判断；active 时真实超过 5 s 仍 stale；无 active reference/从未收到
   occupancy 仍失败；finalize 当前时刻新增 ACK timeout 不得被旧 reference 掩盖。
5. 完成 collector py_compile/self-test、12/12 source hash、53/53 static preflight、
   `git diff --check`；manifest、static contract及所有冻结参数 hash 必须不变。

### 首次实现复审返工

首次实现将 `reference_wall_s` 直接赋给 `snapshot()` 的统一 `now`，导致 ACK timeout 和 freeze 也
冻结在最后 active report 时刻，不符合本节第 1 条；其“finalize 当前时刻新增 ACK timeout”测试实际把
pending command 设在 reference 之前，未覆盖 timeout 只在 teardown 延迟期间成熟的反例。另在没有
active report 时回退到 `started_wall_s`，会让启动后收到的样本产生负 age，不能证明 fail-closed。

返工必须使用两个明确时钟：`current_wall_s` 始终用于 ACK timeout、freeze 和最终状态；
`freshness_reference_wall_s` 只用于 continuous channel stale age。`report(active=False)` 若没有
`last_active_report_wall_s`，必须显式令 telemetry incomplete（或使用当前 wall clock 保持自然
fail-closed），禁止回退到 started time 伪造新鲜。负向测试必须让 pending command 在最后 active
reference 时尚未超时、到 finalize 当前时刻才超过阈值，并断言最终 ACK timeout 被检出；同时覆盖
no-active-reference 且启动后已有样本仍不得 complete。

完成后交回 lead 审核。只有 diff、负向测试、source identity 和静态门全部通过，Sol 才能签发新的
单次 `stage: preflight` package；不得直接 smoke。

### 交接指令

```text
handoff_status: BLOCKED
handoff_model: low-level-implementation
handoff_command:
严格执行 state/sol_plan.md 第 26 节；只修 two_uav_collector.py 的 final freshness reference：
final metrics 不计 teardown 延迟，但运行期 occupancy 连续 5 s freshness、ACK timeout 和全部
fail-closed 合同保持不变；更新 collector source hash 与 Terra 证据，完成规定离线验证。不要启动
ROS、Gazebo、preflight 或 smoke，不得创建 approval package。
```

## 24. 2026-08-22 diagnostic preflight readiness 复合失败最小返工

### 审核决定

```text
runroot: results/RUN-20260821T152941Z-2uav-preflight
approved_new_preflight_package: false
approved_smoke: false
decision: REJECTED_PENDING_SIM_TIME_READINESS_AND_NODE_PROBE_HARDENING
consumed_package: 6280f48317acda77b6c2659b12b397b186f85a8fd6ed23be93dab61c7e7ac5c1
```

本轮 static 53/53、stack 启动、mapper payload、bridge 节点初门均通过，但 frontier readiness
在 180 wall s 后失败。RACER 日志只从 sim 5.706 推进到约 6.757；sim 6.707 才首次出现
`no odom`、`wait for init` 和低空 sensor-outside-map，不能把不足约 1.1 sim s 的观察窗判成
确定性 FSM/算法故障。同一时段 bridge roslaunch 与心跳仍存活，而最终 3 s `rosnode list`
超时被转换为空集合并报告 bridge missing，属于探针分类错误。两者构成负载下的复合失败。

### 目标与允许修改

只加固 readiness，使 RACER frontier 门拥有明确的 simulated-time 初始化预算和独立 wall-time
fail-safe，并使 ROS node 探针 timeout/error 与真实 missing nodes 可区分。不得改变 RACER FSM、
launch 顺序、frontier 合同、冻结参数或实验范围。

Terra 只允许修改：

- `scripts/two_uav_runner.py`：readiness/node probe 及纯函数/self-test；
- `config/2uav_source_hashes.sha256`：只更新 runner hash；
- `state/terra_implementation.md`：追加 diff、验证、identity 与残余风险。

不得修改 mapper、collector、preflight、manifest、static config、launch/world、RACER/单机源码或
参数、approval package、receipt、旧 runroot和正式状态文件；不得启动 ROS、Gazebo、preflight、
smoke，不得 commit/push。

### 最小实现与成功标准

1. `ros_node_names()` 必须返回可区分的成功、timeout 和非零退出状态；timeout/error 不得降格成
   空集合或 `missing nodes`。readiness 只有在一次成功的当前采样中看到全部 required nodes 才能
   通过；探针失败保持 fail-closed，并在最终 detail 中明确 `node probe timeout/error`。
2. node probe 使用有界单次 timeout 和有限重试/退避；不得无限等待，不得用永久缓存的旧节点快照
   通过门。payload probe、所有已启动进程 liveness 和 teardown 检查保持不变。
3. frontier readiness 同时设置 simulated-time 初始化预算与独立 wall-time 上限：wall 慢但 `/clock`
   单调时不得在仅推进约 1 sim s 后失败；`/clock` 停滞、进程退出、probe 持续失败或 wall 上限到达
   必须 fail-closed。具体常量须集中命名并进入 self-test，不得修改 manifest duration 或 smoke 时长。
4. 增加确定性纯函数/self-test，覆盖：低 RT 下 wall 已超过旧 180 s但 sim 预算未耗尽时继续等待；
   sim 预算耗尽仍无 frontier；wall hard cap；clock stalled；node success/missing/timeout/error；当前
   bridge 节点齐全且 payload 出现才通过；任一进程退出立即失败。
5. 完成 runner py_compile/self-test、12/12 source hash、53/53 static preflight 和
   `git diff --check`。Terra 必须记录 frozen manifest hash 不变及旧 package 已消费。

返工完成后交回 lead 审核。只有 diff、identity 与离线证据再次通过，Sol 才能签发一张新的
`stage: preflight`、`allowed_actions: [preflight]`、`max_uses: 1` package；不得直接 smoke。

### 交接指令

```text
handoff_status: REJECTED
handoff_model: low-level-implementation
handoff_command:
严格执行 state/sol_plan.md 第 24 节，只修改 runner readiness/node probe、对应 source hash 与
Terra 证据；实现 sim-time frontier 初始化预算、独立 wall hard cap，以及 node probe
success/missing/timeout/error 的 fail-closed 区分和负向 self-test。不得改 RACER/参数、mapper、
collector、preflight、manifest、launch 或 approval package；完成静态验证；不要启动实验。
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

## 20. 2026-08-21 下一轮：第 19 节最小修复任务包

### 签发决定与冻结身份

```text
task_id: TERRA-2UAV-S19-MINIMAL-REPAIR
handoff_model: low-level-implementation
experiment_approval: none
approved_preflight: false
approved_smoke: false
source_commit: 694a9c30aa9ee8f8f04b4f165866ded55a82aa0c
manifest: experiments/manifests/2uav_smoke.yaml
manifest_sha256: 75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46
static_config_sha256: 415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e
consumed_smoke_package: 3986a46c53dd3c7cfae9dbc03eb388fe80327fc2d2f784b8506a01a8b3988038
```

当前没有有效 approval package。上述已消费 package 和所有旧 runroot 均不得复用、覆盖或
补写。工作树中的历史 runroot 未跟踪文件属于 append-only 实验产物，不在本任务范围内。

### 唯一允许修改范围

- `scripts/two_uav_collector.py`：command 阶段 channel 分类、snapshot/watchdog 组合及
  self-test；
- `scripts/two_uav_gt_mapper.py`：双机机体邻域**诊断**、共享实时位姿账本、纯函数几何
  分类 helper 及 self-test；
- `scripts/two_uav_runner.py`：仅 smoke 最终双机 command-chain 有效性门及 self-test；
- `config/2uav_source_hashes.sha256`：只更新上述实际变更脚本的对应 SHA-256；
- `state/terra_implementation.md`：追加本任务 diff、身份、验证输出和残余风险。

不得修改单机/RACER 源码或参数、`config/2uav_static.yaml`、manifest、launch、world、spawn、
公共环境 baseline、PX4/Livox workspace、freshness/TF/ACK 阈值、preflight live gate、approval
package、receipt、旧 runroot、`project_state.md`、`state/current_summary.md` 或
`state/SESSION_HANDOFF.md`。不得 commit/push，不得启动 ROS、Gazebo、preflight 或 smoke。

### A. Collector：trajectory 事件语义

1. command 前保持当前合同：连续通道为 `odometry/cloud/health/occupancy`，`frontier` 为
   startup-presence；不得提前要求 command 通道。
2. 每机首次收到 PositionCommand 后且 completion 前：
   - `trajectory` 进入 presence/event 集合，必须累计至少一条；
   - `pos_cmd`、`ack` 进入 continuous freshness 集合并继续执行现有 wall 5 s 门；
   - pending command、ACK 1 s timeout、recovered ACK 证据和 abort 语义全部保持。
3. 一条旧 `trajectory` 不得因超过 5 s wall 被判 stale；但 command 后从未收到
   `trajectory` 必须进入 `telemetry_missing_channels` 并 fail-closed。不得把 presence 缺失混入
   stale，也不得豁免 owner、node liveness、TF、coverage 或其它连续通道。
4. completion 后沿用现有停止要求 command 通道 freshness 的语义，不得引入新的即时 freeze
   abort。
5. self-test 至少覆盖：command 前不要求 trajectory；command 后 trajectory 缺失失败；一条
   旧 trajectory 加新鲜 pos_cmd/ack 通过；pos_cmd 或 ack 过期失败；ACK timeout 仍失败；
   frontier 的第 17 节 presence 语义不回退。

### B. GT mapper：先建立证据，当前任务禁止删点

现有不可变 smoke 只证明 uav1 报告 `start inside inflated occupancy`，没有保存 self/peer 机体
包络内点的数量、来源和时序，尚不足以满足第 19 节“先输出证据，再剔除”的门。本任务因此
执行第 19 节明确的停止分支：只实现诊断，不得改变发布点云的点集合。

1. 以只读方式核对当前公共 baseline 所引用 iris 模型的 collision primitives，把实际尺寸、
   相对位姿、来源文件及 hash 记录到 `state/terra_implementation.md`。几何 helper 只能由这些
   冻结碰撞外形导出紧致的 body-local primitive/包络；不得采用经验半径、inflation 半径或
   任意放大框。
2. 两个 `VehicleMapper` 共享线程安全的最新 world pose 账本。每次同步 scan/odom 回调先更新
   source pose，再对已注册到 world 的点做**只读分类**：分别统计落入 source-self 和另一架
   peer 紧致机体包络的点。诊断至少逐 source UAV 累积并定期输出：输入/输出点数、self/peer
   candidate 数、两机 pose available/missing/stale 状态和采用的 geometry identity。
3. peer 位姿缺失、非有限、时间不可比较，或与 source scan stamp 的绝对差超过现有
   `SYNC_SLOP_S` 时，必须标记 unavailable，不能猜测分类；异常不得导致点被删除。诊断日志
   必须是稳定的单行 key/value 或 JSON 结构，能够由下一次 runroot 的
   `logs/gt_mapper.log` 审计并区分 uav0/uav1。
4. 本任务中 `registered_cloud` 的发布内容必须与加入诊断前完全等价：不得应用 candidate mask，
   不得清空起点邻域，不得删静态墙体。若实现中出现任何实际点剔除，视为越权返工。
5. 纯函数/self-test 至少覆盖：identity 与旋转姿态下的包络内/边界外点；self 与 peer 分类互不
   混淆；非有限 pose、缺 peer pose、stale peer pose fail-safe 保留；诊断关闭/无 candidate 时
   输出点逐点不变；双机 source 统计独立。

Terra 完成后必须明确写出 `peer_body_hypothesis_status: UNCONFIRMED_DIAGNOSTIC_ONLY`。Sol 复审
代码后，才可决定是否签发一次新的单次 **preflight 诊断门**；只有真实 runroot 证明 peer
candidate 与 uav1 占据问题在时空上相符，才会另发一个只实现紧致剔除的任务。该顺序不得被
一次性猜测过滤替代。

### C. Runner：仅 smoke 的最终双机功能门

1. 将通用 final safety 与 smoke functional validity 显式分开；preflight 无 goal，绝不能因
   command 计数为 0 而失败。
2. `action_launch` 的最终成功必须额外逐机检查：`telemetry.trajectory > 0`、
   `telemetry.pos_cmd > 0`、`telemetry.ack > 0`，且 `ack_timeout.count == 0`。字段缺失、类型错误
   或任一计数为 0 都 fail-closed，detail 必须指出 UAV 和缺失条件。
3. 该门只能收紧 `duration_complete` 后的 smoke 结果；不得把 freeze 静默升级为即时 abort，
   不得改 trigger、duration、monitor wall timeout、stop/collect 或 preflight 流程。
4. self-test 至少覆盖：两机均完整通过；uav0 任一 command 计数为 0 失败；uav1 从未接令失败；
   任一 ACK timeout 失败；同一无 command metrics 在 preflight safety 路径仍按原合同通过。

### 离线验证与交回门

Terra 只允许运行以下离线命令/probe：

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio_multi_s19_pycache python3 -m py_compile \
  scripts/two_uav_collector.py scripts/two_uav_gt_mapper.py scripts/two_uav_runner.py
python3 scripts/two_uav_collector.py --self-test
python3 scripts/two_uav_gt_mapper.py --self-test
python3 scripts/two_uav_runner.py --self-test
sha256sum -c config/2uav_source_hashes.sha256
python3 scripts/two_uav_preflight.py --mode static \
  --config config/2uav_static.yaml \
  --manifest experiments/manifests/2uav_smoke.yaml
git diff --check
```

并运行 A/B/C 指定的纯函数正负向 probes。验收要求为 py_compile 全通过、三个 self-test
全通过、几何与 command-chain 负向 probe 全通过、source hash 12/12、静态 preflight
53/53、`git diff --check` 通过。Terra 文档必须列出精确 diff 文件、变更前后 SHA、冻结模型
几何来源/hash、所有命令及原样结论，并确认未启动 ROS/Gazebo/实验、未删点、未改参数。

完成后只交回 `lead-planning` 审核；本任务不签发 preflight 或 smoke，不允许边改边跑。

### 交接指令

```text
handoff_status: BLOCKED
handoff_model: low-level-implementation
handoff_command:
$low-level-implementation

严格执行 state/sol_plan.md 第 20 节。只修改其中列出的三个脚本最小范围、相应纯函数/self-test、
config/2uav_source_hashes.sha256 和 state/terra_implementation.md。collector 修正 trajectory
event 语义；runner 只增加 smoke 最终逐机 command-chain 门；GT mapper 只增加由冻结 iris
collision geometry 导出的 self/peer 候选点诊断，当前不得删除或改变任何发布点。完成规定的
离线验证后交回 lead-planning 审核。不得启动 ROS、Gazebo、preflight 或 smoke，不得修改
参数、manifest、approval package、receipt、旧 runroot或正式状态文件。
```

## 21. 2026-08-21 第 20 节实现复审：最终门与诊断快照最小返工

### 复审结论

```text
decision: REJECTED_PENDING_MINIMAL_OFFLINE_REWORK
approved_preflight_package: false
approved_smoke: false
manifest_sha256: 75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46
source_hash_manifest_sha256: 3fd97d52d6e104758f8dee3253a63f4b0ae9188bf8052dcbd2546168b6c806b5
static_preflight: 53/53 PASS
source_hash_entries: 12/12 PASS
```

collector 的 trajectory presence/event 分类、冻结 iris collision geometry、只诊断不删点的
范围以及 preflight/smoke 分离方向均符合第 20 节；manifest、static config 和正式状态文件未被
修改。但现有实现有两个独立的 fail-closed/可审计缺口，不能据此签发诊断 preflight：

1. `smoke_command_chain_valid()` 接受任意 float；Python 中 `NaN <= 0` 为 false，导致
   `trajectory=NaN` 被当成 `>0` 并返回成功。纯 probe 同时证明空 `vehicles=[]` 也返回
   `smoke command chain complete`。这与 Terra 文档所称“错误类型或零计数均 fail-closed”不符，
   且函数没有封闭“恰好两架 UAV”的合同。
2. mapper `_diagnostics()` 只做 `dict(self._body_counts)` 浅拷贝；嵌套的
   `self_pose_status/peer_pose_status` 字典仍与 subscriber callback 共享。Timer 进行
   `json.dumps()` 时 callback 可同时新增/更新 key，快照不是不可变证据，存在混合计数甚至
   `dictionary changed size during iteration` 的风险。纯 probe 已证明 shallow snapshot 的嵌套
   dict 会随原计数变化。

### 唯一允许返工范围

只允许修改：

- `scripts/two_uav_runner.py` 的 `smoke_command_chain_valid()` 与 self-test；
- `scripts/two_uav_gt_mapper.py` 的 body diagnostic counter 锁/深快照 helper 与 self-test；
- `config/2uav_source_hashes.sha256` 中上述两个脚本的 hash；
- `state/terra_implementation.md`，追加返工 diff、验证和新 identity。

不得修改 collector、几何常量/包络、点分类结果、registered cloud 发布链、任何点过滤、
manifest、static config、参数/阈值、runner 其它流程、approval package、receipt、旧 runroot、
`project_state.md`、`state/current_summary.md` 或 `state/SESSION_HANDOFF.md`。不得 commit/push；
不得启动 ROS、Gazebo、preflight 或 smoke。

### 最小修复要求

1. command count 只接受非 bool 的整数且 `>0`；`None`、bool、string、float、`NaN`、`Inf`、
   0 和负数全部 fail-closed。`vehicles` 必须恰好包含 uav0/uav1 两份报告；空、单机或多于两机
   全部失败。ACK timeout 仍只接受非 bool 整数 `0`。失败 detail 必须指出 cardinality 或具体 UAV/
   字段。
2. mapper 为每个 `VehicleMapper` 的 `_body_counts` 增加独立锁。callback 的全部 body counter/
   nested status 更新必须在锁内；Timer 在同一锁内构造完全脱离原对象的深快照，释放锁后才
   `json.dumps()`/log。不得长期持锁做点分类或日志 I/O。
3. 将深快照拆成可离线测试的纯 helper，self-test 必须证明：快照后修改原始顶层计数或嵌套
   status 不会改变快照；两个 mapper/source 的快照互不共享。不得改变 geometry identity、
   candidate 数学或点云输出。
4. runner self-test 增加两机 cardinality 和上述每一种坏计数类型的负向 probe；原有正常两机、
   uav0/uav1 零计数、ACK timeout 与 preflight 无 command safety 路径测试全部保留。

### 离线验证与交回

Terra 只能运行：

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio_multi_s21_pycache python3 -m py_compile \
  scripts/two_uav_gt_mapper.py scripts/two_uav_runner.py
python3 scripts/two_uav_gt_mapper.py --self-test
python3 scripts/two_uav_runner.py --self-test
sha256sum -c config/2uav_source_hashes.sha256
python3 scripts/two_uav_preflight.py --mode static \
  --config config/2uav_static.yaml \
  --manifest experiments/manifests/2uav_smoke.yaml
git diff --check
```

要求 py_compile/self-test/负向 probes 全通过、12/12 source hash、53/53 static 和 diff check
全通过。完成后交回 lead 复审；修复前后均不得创建 approval package。

### 交接指令

```text
handoff_status: REJECTED
handoff_model: low-level-implementation
handoff_command:
$low-level-implementation

严格执行 state/sol_plan.md 第 21 节。只修 runner 的两机 command-count fail-closed/cardinality
门和 GT mapper body diagnostic 的锁定深快照；更新对应 source hash 与 Terra 证据。不得修改
collector、几何/点分类或发布内容，不得启动 ROS、Gazebo、preflight 或 smoke，不得创建或修改
approval package。完成离线验证后交回 lead-planning 审核。
```

## 22. 2026-08-21 diagnostic preflight 归因与紧致 peer-body 过滤任务

### 审核结论

```text
runroot: results/RUN-20260821T091542Z-2uav-preflight
preflight: 48/48 PASS
consumed_package: aef23aefd98998693f57e4328010363bd849dfae794ab7691ff5b1b7baa57079
peer_body_hypothesis: SUPPORTED_BUT_DIRECTIONALLY_INCOMPLETE
approved_new_package: false
approved_smoke: false
decision: BLOCKED_PENDING_TIGHT_PEER_FILTER_AND_CROSS_UAV_POSE_TIMING_REPAIR
```

本轮静态 53/53、live 48/48、24 s no-goal soak、双机 payload/TF/owner/参数/日志、8/8
节点、逐机/fleet telemetry 和 final safety 全通过，无 abort；RT factor 约 0.333。该结果证明
第 20/21 节 collector/runner/诊断接入没有破坏 preflight，但不能直接进入 smoke。

诊断支持真实 peer-body 回波进入 registered cloud：source uav1 以 uav0 为 peer 时，两个累计
快照均有完整 peer pose（87/87、177/177），peer candidates 为 381/192978（0.197%）和
712/339868（0.210%），增量为 331/146890（0.225%）。同一 RACER 日志从 sim 9.29 起反复报告
两处出生坐标处于 inflated occupancy；按 start x 分类共计 uav0 约 100 次、uav1 约 134 次，
sim≥15 后仍为 uav0 3 次、uav1 51 次。50×50 world 两处 spawn 周围无静态墙，self candidate
为 0，且 candidate 与 start-inside 在 sim 10.7 附近共现，因此“动态 peer 机体回波进入地图”
已从纯假设提升为有运行证据支持的首要原因，但不能宣称是唯一原因。

证据仍有明确方向缺口：source uav0 以 uav1 为 peer 时，首快照 peer pose available 0/94，
次快照仅 2/187；其 peer_candidates=0 主要是 callback 顺序与只保存 latest scan-time pose 导致
的不可分类，不能证明 uav0 没有看到 uav1。该方向恰是解释 uav1 晚期持续 start-inside 所需的
直接证据。因此最小修复必须先把高频 MAVROS odom 纳入跨机 pose ledger，再只剔除已有冻结
collision geometry 精确命中的 peer 点；不得扩大包络或改地图参数。

### 唯一允许修改范围

- `scripts/two_uav_gt_mapper.py`：跨机 pose ledger 更新、紧致 peer candidate 过滤、诊断 counter
  及纯函数/self-test；
- `config/2uav_source_hashes.sha256`：只更新 GT mapper 对应 hash；
- `state/terra_implementation.md`：追加精确 diff、验证、identity 与残余风险。

不得修改 collector、runner、preflight、RACER/单机源码或参数、冻结 collision primitives/
geometry identity、`MIN_RANGE_M/MAX_RANGE_M/DOWNSAMPLE_STRIDE/SYNC_SLOP_S`、manifest、
`config/2uav_static.yaml`、launch/world/spawn、inflation/freshness/ACK 阈值、公共环境 baseline、
approval package、receipt、旧 runroot、`project_state.md`、`state/current_summary.md` 或
`state/SESSION_HANDOFF.md`。不得 commit/push；不得启动 ROS、Gazebo、preflight 或 smoke。

### 最小实现要求

1. 为每个 MAVROS odom 原始消息增加 pose-ledger 更新路径：使用 odom 自身 header stamp、当前
   orientation/position 与冻结 initial offset 形成 world pose。ledger 只能按 stamp 单调前进，
   晚到的旧消息不得覆盖较新的 peer pose。同步 scan/odom callback 继续负责 registration，但
   不得再用 callback 顺序产生的旧 scan stamp 覆盖高频 odom pose。
2. source scan 仍以自己的 scan stamp 查询 peer pose，且继续使用现有
   `SYNC_SLOP_S=0.05` 判 available/stale；缺失、非有限、uncomparable 或 stale 时必须完整保留
   点云，不得猜测过滤。不得通过放宽时间窗掩盖时序问题。
3. peer pose available 时，只对当前 `IRIS_COLLISION_PRIMITIVES` 并集内的 **peer** candidate
   应用 mask；self candidate 不删除，包络外点逐点保留。过滤发生在 world registration 后、
   `registered_cloud` 发布前；registered odom/pose/TF 的发布和 frame/timestamp 不变。即使过滤后
   点数为 0，也不得跳过 odom/pose/TF 或伪造点。
4. 诊断继续记录过滤前 `registered_points` 与 `peer_candidates`，新增至少
   `peer_removed_points`、`published_points`、`peer_preserved_unavailable_points`；累计恒等式
   必须可审核：available 分类中 removed=candidate，published=registered-removed。unavailable
   scan 的所有点计入 preserved，removed 必须为 0。两个 source 的 counter/锁/深快照保持独立。
5. 纯函数/self-test 至少覆盖：available peer 的包络内点被删且包络外逐点不变；stale/missing/
   nonfinite peer pose 全量保留；self 包络命中不触发 peer 删除；旋转 peer geometry；过滤后空点
   输出；ledger 拒绝旧 stamp 覆盖；uav0/uav1 高频 odom 更新后两方向可分类；诊断恒等式和深快照。
6. 不得以本轮证据删除任意半径、inflation 邻域、整帧 cloud 或静态墙；不得新增配置开关后默认
   绕过 fail-safe。过滤对象必须完全等于可审计 peer mask。

### 离线验证与下一门

Terra 只能运行：

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio_multi_s22_pycache python3 -m py_compile \
  scripts/two_uav_gt_mapper.py
python3 scripts/two_uav_gt_mapper.py --self-test
sha256sum -c config/2uav_source_hashes.sha256
python3 scripts/two_uav_preflight.py --mode static \
  --config config/2uav_static.yaml \
  --manifest experiments/manifests/2uav_smoke.yaml
git diff --check
```

并执行上述 pose/过滤/恒等式负向 probes。要求 mapper self-test、12/12 source hash、53/53 static
和 diff check 全通过，Terra 明确证明 geometry constants 未变且发布点只减少 exact peer mask。
完成后交回 lead 复审；当前不得创建 package。

只有修复审核通过，Sol 才可签发一张新的单次 diagnostic preflight。该 preflight 除 48/48 和
final safety 外，还必须证明：两个 source 的第二快照 peer pose available 占比均超过 50%；
两方向第二快照 pre-filter `peer_candidates > 0`；`peer_removed_points == peer_candidates` 且
`published_points == registered_points - peer_removed_points`；无 unavailable scan 被删点；
sim≥15 的出生点 `Astar vehicle start is inside inflated occupancy` 不再持续出现。任何一项不满足
都返回 lead，smoke 继续禁止。

### 交接指令

```text
handoff_status: BLOCKED
handoff_model: low-level-implementation
handoff_command:
$low-level-implementation

严格执行 state/sol_plan.md 第 22 节。只修改 two_uav_gt_mapper.py 的高频 odom pose ledger、
exact peer collision-mask 过滤、诊断 counter/self-test，更新对应 source hash 与 Terra 证据。
不得改 geometry、时间窗、collector/runner、manifest、参数或发布 frame；不得启动 ROS、Gazebo、
preflight 或 smoke，不得创建 approval package。完成规定离线验证后交回 lead-planning 审核。
```

## 23. 2026-08-21 第 22 节实现复审：消除 odom 输入别名的最小返工

### 审核结论

```text
approved_new_preflight_package: false
approved_smoke: false
decision: REJECTED_ODOM_INPUT_ALIAS_CAN_DOUBLE_APPLY_INITIAL_OFFSET
old_package: aef23aefd98998693f57e4328010363bd849dfae794ab7691ff5b1b7baa57079 CONSUMED
```

第 22 节的 exact peer mask、缺失/stale/non-finite fail-safe、累计恒等式、冻结 geometry、
12/12 source hash、53/53 static、mapper self-test 与 `git diff --check` 均通过；manifest、static
contract、单机参数、50×50 baseline、时间窗和发布 frame 未改变。但运行时还有一个会污染新
pose ledger 的确定性对象别名缺口，因此当前不得签发 diagnostic preflight。

`message_filters.SimpleFilter.signalMessage()` 按注册顺序把**同一消息对象**交给各 callback；当前
ApproximateTimeSynchronizer 先注册，`_odom_pose_cb` 后注册。同步 `_callback()` 内执行
`out_odom.pose = odom.pose` 后原地加 initial offset，会同步修改输入 `odom.pose`。若某条 uav1
odom 在到达时立即配成 scan pair，同一次 signal 链随后进入 `_odom_pose_cb` 时读取的 x 已加过
`1.5 m`，再加一次后 ledger 可记录 `3.0 m` 而非冻结 spawn `1.5 m`。离线 ROS message probe 已
证明该赋值发生输入 mutation。这样即使 self-test 的纯数组 mask 正确，运行时 peer pose/mask 仍
可能错位，违反“原始 MAVROS odom + 一次 initial offset”的要求。

### 目标与允许修改

目标：在不改变任何数值合同或发布内容的前提下，使 registered odom/pose 构造与输入 MAVROS odom
完全解耦，保证任意 callback 顺序下 ledger 都只观察未修改的原始 odom。

Terra 只允许修改：

- `scripts/two_uav_gt_mapper.py`：registered pose 的 detached/deep-copy 构造及回归 self-test；
- `config/2uav_source_hashes.sha256`：只更新 mapper 对应 hash；
- `state/terra_implementation.md`：追加本次 diff、验证、identity 和残余风险。

不得修改 collector、runner、preflight、manifest、static config、geometry identity/primitives、
`MIN_RANGE_M/MAX_RANGE_M/DOWNSAMPLE_STRIDE/SYNC_SLOP_S`、initial positions、registered cloud
过滤、odom/pose/TF frame 或 timestamp、RACER/单机参数、world/baseline、approval package、receipt、
旧 runroot、正式状态文件。不得 commit/push；不得启动 ROS、Gazebo、preflight 或 smoke。

### 最小实现与成功标准

1. `_callback()` 构造 `out_odom.pose` 时必须使用与 `odom.pose` 不共享可变对象的 detached copy，
   initial offset 只施加到该输出副本；禁止原地修改输入 odom。注册 odom/pose/TF 的数值与既有
   合同保持完全一致；不得用调整 callback 注册顺序作为唯一修复。
2. `_odom_pose_cb()` 继续从原始 odom header/pose 生成 world pose，一次且仅一次叠加冻结 initial
   offset；PoseLedger 单调 stamp、0.05 s 时间窗、peer-only exact mask 和诊断恒等式均不变。
3. 增加直接回归 probe/self-test：uav1 local x=0 经输出转换得到 world x=1.5，但输入 local x 仍为
   0；模拟“同步 callback 先、ledger callback 后”时 ledger 仍为 1.5；连续重复构造不得累加到 3.0。
   同时保留第 22 节所有 missing/stale/non-finite、rotated geometry、empty output、两方向可分类、
   旧 stamp 拒绝和深快照用例。
4. 完成 mapper py_compile/self-test、上述别名负向 probe、12/12 source hash、53/53 静态
   preflight 和 `git diff --check`；Terra 证据必须明确记录 input-not-mutated 恒等式。

修复完成后交回 lead 审核。只有再次审核通过，Sol 才能签发新的单次 `stage: preflight` package；
旧 package 已有 receipt，不得复用，smoke 继续禁止。

### 交接指令

```text
handoff_status: REJECTED
handoff_model: low-level-implementation
handoff_command:
$low-level-implementation

严格执行 state/sol_plan.md 第 23 节。只修 two_uav_gt_mapper.py 的 odom 输入别名：registered
pose 必须 detached，任意 callback 顺序下原始 MAVROS odom 不得被 initial offset 原地修改；增加
同步 callback 先于 ledger callback、重复构造不累加的回归 self-test，更新 mapper source hash 与
Terra 证据。不得改 geometry、时间窗、过滤、collector/runner、manifest、参数或发布 frame；
不得启动 ROS、Gazebo、preflight 或 smoke，不得创建 approval package。完成离线验证后交回
lead-planning 审核。
```

## 25. 2026-08-22 live rosparam flake 与深层停栈覆盖最小返工

### 审核决定

```text
runroot: results/RUN-20260821T162356Z-2uav-preflight
approved_new_preflight_package: false
approved_smoke: false
decision: REJECTED_PENDING_LIVE_CLI_RETRY_AND_DESCENDANT_TEARDOWN
consumed_package: 186c9159e90bb918b674f311d5f45bd4565e7305fb164a652fcf2de41c2dda98
```

本轮 readiness（含 frontier sim-budget）、双机 frontier、collector、telemetry completeness、TF fresh
和进程 liveness 均通过；live check 仅在第三条只读 `rosparam get` 的固定 15 s 窗超时。该失败应归类
为负载下 CLI sampling flake，不能据此改变冻结参数或跳过参数回读。另一方面，runner 停栈后仍遗留
rosmaster、gzserver、PX4 SITL、MAVROS 和 bridge 等 9 个深层后代，外部执行器代清理不能作为 runner
合同通过证据。

### 允许修改

- `scripts/two_uav_preflight.py`：只读 live CLI 的有界重试、错误分类与 self-test；
- `scripts/two_uav_runner.py`：严格限定到本 runroot/进程树的深层停栈与验证；
- `config/2uav_source_hashes.sha256`：只更新上述两个脚本 hash；
- `state/terra_implementation.md`：追加 diff、验证、identity 和残余风险。

不得修改 mapper、collector、manifest、static config、launch/world、RACER/单机源码或参数、readiness
预算、实验时长、approval package、receipt、旧 runroot或正式状态文件；不得启动 ROS、Gazebo、
preflight、smoke，不得 commit/push。

### 最小实现与成功标准

1. `rosparam get` 等只读 live CLI 使用集中定义的单次 timeout、有限 attempts、退避和总 wall cap。
   timeout 与非零退出必须分别记录；仅当前成功返回并通过既有精确值解析/比较才能通过。不得使用缓存值、
   默认值或跳过任一 UAV/参数；连续失败必须 fail-closed，并保留 argv/attempt/status 证据。
2. 重试逻辑应为可注入的纯 helper；self-test 覆盖首轮 timeout 后成功、非零后成功、全部 timeout、全部
   error、最终值不匹配及总 wall cap。不得把任意 shell 字符串引入参数名或扩大命令白名单。
3. runner 在发送顶层 SIGTERM 前先解析并冻结所有顶层 PID 的完整 descendant closure；停栈必须覆盖这些
   后代。为处理 reparent/race，只允许使用可审核的 `/proc` 父子关系与本 runroot 精确
   `ROS_HOME`/`ROS_LOG_DIR`/ROS master identity 再发现残留；禁止按进程名、用户或宽泛 pattern 杀进程。
4. TERM grace 后对仍存活且身份仍匹配的目标发送 KILL；最终重新扫描并在 `stop_result.json` 中记录顶层、
   descendants、TERM/KILL 和 survivors。任何匹配 survivor、ROS master 端口未释放或身份不可确认均
   fail-closed，不得报告 clean teardown。
5. runner self-test 使用伪 `/proc` 快照覆盖多层树、已 reparent 但 runroot env 匹配、无关 ROS 进程不被
   选择、PID reuse/env 不匹配不被杀、TERM 后消失、KILL 后 survivor fail。不得在 self-test 中实际杀进程。
6. 完成两个脚本 py_compile/self-test、12/12 source hash、53/53 static preflight 和
   `git diff --check`；manifest hash与冻结参数必须不变。

完成后交回 lead 审核。只有 diff、identity、负向测试与静态门全部通过，Sol 才能签发新的单次
`stage: preflight` package；smoke 继续禁止。

### 交接指令

```text
handoff_status: REJECTED
handoff_model: low-level-implementation
handoff_command:
严格执行 state/sol_plan.md 第 25 节；只加固 two_uav_preflight.py 的有界只读 CLI 重试，以及
two_uav_runner.py 对本 runroot 精确身份限定的 descendant teardown/最终 survivor 验证，更新对应
source hash 与 Terra 证据。不得改参数、readiness budget、mapper、collector、manifest、launch 或
approval package；完成静态验证；不要启动实验。
```

## 27. 2026-08-22 preflight 48/48 后的 uav1 起点占据阻断与 peer-ray 最小修复

### 审核决定

```text
runroot: results/RUN-20260821T173822Z-2uav-preflight
preflight_contract: PASS_48_OF_48
approved_smoke_package: false
decision: BLOCKED_BY_PERSISTENT_UAV1_START_INFLATED_OCCUPANCY
consumed_preflight_package: f1c7638e764e8dccad0e87e1b217c86561fc953dafdfec1c5912e13dcb5263c2
```

接入、安全与停栈合同已经通过，但功能风险未消除。sim 20 的 mapper 证据显示 uav0 source 对 uav1
的 peer pose 187/189 available，精确 collision-primitive mask 删除 1903 点且恒等式成立；然而过滤后的
published cloud 仍在 uav1 hover voxels 留下来自 uav0 的持续命中，recent sim time 到 19.882。RACER
随后在 sim 25.529 对实际 uav1 悬停起点连续报告 `Astar vehicle start is inside inflated occupancy`。
因此规划层是在读取真实残留占据，不能签 smoke；现有“只删除 endpoint 位于 peer primitive 内”的 mask
不足以覆盖落在表面外侧或 peer 后方的同一束动态遮挡回波。

### 目标与允许修改

目标：在不使用 inflation 球/盒、不删除真实近机环境的前提下，把 peer 动态遮挡归因从 endpoint-only
扩展为 source-ray 与冻结 peer collision primitives 的精确相交；只有射线段确实穿过 peer primitive 的
endpoint 才可作为 peer-occluded return 删除。

Terra 只允许修改：

- `scripts/two_uav_gt_mapper.py`：纯几何 segment-vs-peer-primitives helper、peer-ray mask、审计 counter
  与 self-test；
- `config/2uav_source_hashes.sha256`：只更新 mapper hash；
- `state/terra_implementation.md`：追加 diff、验证、identity 和残余风险。

不得修改 collision geometry、`obstacles_inflation: 0.35`、任何半径/时间窗/downsample、collector、
runner、preflight、manifest、static config、RACER/单机参数、launch/world/spawn/baseline、approval
package、receipt、旧 runroot 或正式状态文件；不得启动 ROS、Gazebo、preflight、smoke，不得 commit/push。

### 最小实现与成功标准

1. 每个 source scan 使用该 scan 已同步的 source world pose 作为射线起点；peer pose 必须按既有 ledger、
   stamp 和 `SYNC_SLOP_S` 判为 available。missing/stale/uncomparable/nonfinite 时保持全部点，不得猜测。
2. 保留既有 endpoint-in-peer exact mask，并新增闭区间 line segment 与冻结 peer collision primitives 的
   精确相交 mask；不得加入经验 epsilon、inflation margin、球形 hover 清空或按 voxel 批量删点。
3. 只删除 `endpoint_body_mask OR peer_ray_intersection_mask`。射线未穿过 peer 的近机静态点、地面、墙体
   必须逐点不变；source self geometry 不得触发 peer-ray 删除。
4. 诊断分别累计 endpoint candidates、ray candidates、union removed、published、unavailable preserved，
   并保持 `published = registered - union_removed`。下一次 preflight 仍须审计 hover voxel provenance。
5. self-test 至少覆盖：endpoint 在 body 内；endpoint 在 body 后且 segment 穿过 peer；endpoint 位于 peer
   邻域但 segment 绕开 peer；旋转 peer primitive；segment tangent/boundary；source 起点在 primitive 外；
   stale/missing/nonfinite 全量保留；两 mask 重叠不重复计数；输入/deep snapshot 不变。
6. 完成 mapper py_compile/self-test、12/12 source hash、53/53 static preflight 与 `git diff --check`。

### 首次实现复审返工：ray origin 必须与点云注册外参一致

首次实现把同步 odom 的 body world position 直接作为 ray origin，但 `register_points()` 对 LiDAR 点
使用了冻结 local sensor offset `[0, 0, 0.13]` 并随 source orientation 旋转后叠加。endpoint 与 origin
因此不在同一传感器几何模型中，可能让本应绕过 peer 的静态点误命中，或漏掉真实 peer 遮挡。

返工必须把该既有 sensor offset 提取为单一冻结常量/纯 helper，并由 `register_points()` 与
source-ray origin 共同使用；禁止复制第二份数值。ray origin 必须等于 source body world position 加
`R_source * sensor_offset`，stamp 仍为同步 scan stamp。新增非零 roll/pitch/yaw 的负向测试：同一 local
scan endpoint 经注册后的 world endpoint，与由同一外参导出的 ray origin 构成的 segment 判定正确；
同时证明 body-origin 版本会得到不同结果的构造用例现已被修正。不得用 epsilon 或扩大 primitive 掩盖。

实现复审通过后，只能再签一次 diagnostic preflight。该轮除 48/48 外必须证明：hover voxels 不再从
published cloud 累积，并且 sim>=15 后实际 uav1 悬停起点不再出现 inflated-occupancy；否则仍不得 smoke。

### 交接指令

```text
handoff_status: BLOCKED
handoff_model: low-level-implementation
handoff_command:
严格执行 state/sol_plan.md 第 27 节；只修改 two_uav_gt_mapper.py，实现 source-ray 与冻结 peer collision
primitives 的精确相交 mask，保留 unavailable fail-safe 与逐点审计恒等式；禁止 inflation/经验半径/起点
邻域清空。更新 mapper source hash 和 Terra 证据，完成规定离线验证；不要启动实验或创建 approval package。
```

## 28. 2026-08-22 uav0 OFFBOARD/arm 短窗口与 physical-hover 门交互修复

### 审核决定

```text
runroot: results/RUN-20260821T175600Z-2uav-preflight
approved_new_preflight_package: false
approved_smoke: false
decision: BLOCKED_BY_PX4_BRIDGE_FINITE_ARM_REQUEST_WINDOW
consumed_package: 0093e6f41f6fab1417f7e9444b88c6ea2731b36fab765c779cca6a7414a85779
```

本轮 static/readiness/live 均通过，但 uav0 从未升至 0.12 m 以上。PX4 输出在启动窗口反复出现
`Preflight Fail: no heading reference` 与 `Arming denied`，说明短窗口内 PX4 尚未持续 ready；现有 bridge
只在 30 次短循环中调用 OFFBOARD/arm，且吞掉 service 异常和响应。随后 45 s physical-hover readiness
循环只发布 setpoint，不再请求模式/解锁。uav0 因而保持地面，bridge 在 sim 23.293 按设计超时退出，
collector 随后因 owner/process death 正确 fail-closed。不能通过取消 bridge 崩溃、放宽高度或延长超时
掩盖此链路。

本轮 peer-ray 计数与发布恒等式成立，但 uav0 未升空使 sim>=15 的实际 start-inflated 证据落在 uav0
地面位置，不能作为 uav1 悬停占据门的有效判定；修复后必须重新跑 diagnostic preflight。

### 目标与允许修改

目标：在保持 hover setpoint 连续发布和 45 s fail-closed hard timeout 的同时，readiness 期间以有界频率
持续重试 OFFBOARD/arm，直到 MAVROS state 明确确认 `mode=OFFBOARD` 且 `armed=true`；每次 service
结果/异常和状态转换必须可审计。

Terra 只允许修改：

- `/home/houslakers/swarm_ws/src/Swarm-LIO2/swarm_lio/scripts/px4_bridge.py`：OFFBOARD/arm 请求状态机、
  结构化日志与纯 helper/self-test；
- `config/2uav_source_hashes.sha256`：新增或更新该运行时 bridge 的绝对路径 hash，并保持现有条目；
- `state/terra_implementation.md`：记录外部工作树精确文件 diff/hash、验证和残余风险。

不得修改 PX4 参数/固件、MAVROS 配置、hover 高度/速度/stable/timeout/odom-age 阈值、launch、manifest、
mapper/collector/runner/preflight、RACER/单机参数、world/spawn/baseline、approval package、receipt、旧
runroot 或正式状态文件；不得改动 Swarm-LIO2 工作树内任何其它现有 dirty 文件；不得启动 ROS、Gazebo、
preflight、smoke，不得 commit/push。

### 最小实现与成功标准

1. 将 mode/arm 请求抽为可测试 helper：分别返回 mode service 的 `mode_sent`、arming service 的
   `success` 或明确 exception；禁止裸 `except: pass`。
2. 预热后和整个 physical-hover readiness 期间持续发布既有 hover target；当 state 未确认 OFFBOARD
   或未 armed 时，以集中常量的有界频率（不得 20 Hz flood）重试对应 service。已确认的条件不得重复请求。
3. 保持原 45 s monotonic hard timeout及 `RuntimeError` fail-closed；不得把 timeout 改成无限等待、正常
   退出或仅 warning。成功仍须满足 OFFBOARD+armed、z>=1.20、|vz|<=0.20 连续 1 s。
4. 日志至少包含 drone id、attempt、当前 mode/armed、mode_sent、arm_success、exception class，并在状态
   首次转为 OFFBOARD/armed 和最终 hover ready 时落盘；不得记录无关敏感环境。
5. 纯测试覆盖：初次 health-not-ready/返回 false 后持续重试并最终成功；mode 成功但 arm 延迟；service
   exception 后恢复；已确认条件不重复调用；持续失败到 45 s 仍 fail-closed；两 drone 状态相互独立。
6. 完成 bridge py_compile/self-test、更新后的全部 source hash、static 53/53 与 `git diff --check`；记录
   bridge 绝对路径、SHA-256 及仅该文件的外部 diff。不得把外部仓库其它 dirty 状态纳入或清理。

实现复审通过后，Sol 才能签发新的单次 diagnostic preflight；smoke 继续禁止。

### 交接指令

```text
handoff_status: BLOCKED
handoff_model: low-level-implementation
handoff_command:
严格执行 state/sol_plan.md 第 28 节；只修改外部运行时 px4_bridge.py、source hash manifest 与 Terra
证据。在 physical-hover readiness 内有界持续重试 OFFBOARD/arm并记录 service 响应/状态转换，保持
45 s、高度/速度/stable 门和超时崩溃 fail-closed 不变；不得碰外部仓库其它 dirty 文件。完成规定离线
验证；不要启动实验或创建 approval package。
```

## 29. 2026-08-22 公共 overlay identity 同步任务包

### 审核决定

```text
approved_identity_sync_task: true
approved_preflight_package: false
approved_smoke: false
decision: PREPARE_NEW_COMMON_OVERLAY_IDENTITY_THEN_REVIEW
```

第 28 节 bridge 实现 hash 为
`5cce75ddb7b3d21476a2492f7769cedd43bbfbdd2430dfe69562443bd87becf3`，并已由 multi
`config/2uav_source_hashes.sha256` 精确锁定；其 13/13 校验通过。静态门唯一失败
`source.overlay_installed_21_of_21` 来自公共 overlay 清单仍要求旧 bridge hash
`9ad51e4a8122bea78401e33cc27452a3ae6f49581a9d277a5adf7bad5e553db0`。这是同一已批准
bridge 修复的 identity 漂移，不是新的算法或实验范围。

但只替换 `current_config.sha256` 的一行不构成合格修复：installer 会校验清单所指的 bundle source，且
修改 tracked 清单会使 single 仓库不再满足 `source.single_tracked_clean`。因此本任务只准备一个可由 Sol
后续单独审核并提交的新公共 overlay identity；Terra 不得 commit/push，也不得把 52/53 宣称为 53/53。

### 目标与允许写入

目标：为已审核 bridge 文件建立不可变 bundle source，更新公共 overlay 清单和 multi 的引用，使后续
Sol 提交该公共 identity 后，single HEAD/clean、bundle、installed target 和 multi 三者能锁定同一字节。

Terra 只允许修改或新增：

- `/home/houslakers/auto_tune_racer/swarmlio-single-v2/history/RUN-20260822T000000Z-px4-bridge-readiness-identity/px4_bridge.py`：
  从当前已审核运行时 bridge 逐字节复制的不可变 bundle source；目录名可改为实际 UTC identity 名，但
  必须唯一且不得覆盖既有 history；
- `/home/houslakers/auto_tune_racer/swarmlio-single-v2/platform_overlays/range20m_omnidirectional_v1/current_config.sha256`：
  仅将 bridge 条目的 hash/source_rel 更新到上述新 bundle，保持 mode、root、target 和其余 20 条不变；
- `config/2uav_static.yaml` 与 `experiments/manifests/2uav_smoke.yaml`：仅同步新的 overlay manifest SHA；
- `config/2uav_source_hashes.sha256`：同步上述 multi 文件 hash，并新增公共 overlay manifest、bundle source
  的绝对路径 hash；保留运行时 bridge 条目；
- `state/terra_implementation.md`：追加精确 diff、hash、验证结果和“等待 Sol 公共 identity commit”阻断。

不得修改 installer、bridge 运行时文件、preflight/runner/collector/mapper、launch、PX4/MAVROS/RACER 参数、
world、approval package、旧 runroot、正式状态文件或其它 single/Swarm-LIO2 dirty 文件；不得实验、commit、
push、覆盖 history 或执行 overlay `--apply`。

### 成功标准与阶段边界

1. 新 bundle source、运行时 bridge 和清单 bridge hash 三者 SHA-256 完全相同，mode 仍为 `0755`；清单仍为
   21 条且其它 20 条逐字节不变。
2. installer `--verify-bundle` 通过；installer 自身 hash 仍为
   `7e2280d5d0ba88ee501764ab5b5ccc3f3724d5b6abf39704badc7a8976349151`；禁止 `--apply`。
3. `sha256sum -c config/2uav_source_hashes.sha256`、bridge py_compile/self-test、multi `git diff --check`
   通过，并记录 single 精确 diff/status。
4. Terra 阶段允许 static preflight 因 `source.single_commit/tracked_clean` 仍 fail-closed；不得规避 clean 门。
   Terra 交回 Lead 后，由 Sol 审核并形成 single 公共 identity commit；随后再同步新 single commit 到 multi
   frozen identity，复跑 static 53/53。未完成这两步前不得创建 preflight approval package。

### 交接指令

```text
handoff_status: BLOCKED
handoff_model: low-level-implementation
handoff_command:
严格执行 state/sol_plan.md 第 29 节，只准备新的公共 overlay bundle/identity 与 multi hash 引用；不得修改
运行时 bridge、installer 或安全门，不得 commit/push、执行 overlay --apply、启动实验或创建 approval
package。完成 bundle、21 条恒等、13+ source hash、bridge 自测和精确 diff/status 证据后交回 lead 审核。
```

## 30. 2026-08-22 第 29 节复审：bridge 安装 mode 收敛

### 审核决定

第 29 节的内容 identity 合格：运行时 bridge、bundle source 和清单 hash 均为
`5cce75ddb7b3d21476a2492f7769cedd43bbfbdd2430dfe69562443bd87becf3`，overlay 为 21 条，
`--verify-bundle`、15/15 source hash 和 bridge self-test 均通过；single tracked diff 只有清单一行，另有
任务内新 bundle 文件。

但 Terra 证据称运行时 bridge mode 为 `0755`，实际 `stat` 为 `0775`；bundle 与 overlay 清单均为
`0755`。installer 在目标内容 hash 已相同时直接报告 CURRENT，不会修正 mode，因此不能把此偏差带入公共
identity commit。

### 唯一允许动作与成功标准

Terra 只允许：

- 将 `/home/houslakers/swarm_ws/src/Swarm-LIO2/swarm_lio/scripts/px4_bridge.py` 的文件 mode 从 `0775`
  收敛为 `0755`，不得改变任何字节；
- 追加修正 `state/terra_implementation.md`，明确此前 mode 记录错误并记录修正前后证据。

不得修改 bundle、overlay 清单、installer、multi config/manifest/source hashes、任何源码字节、安全门、
approval package、旧 runroot 或其它 dirty 文件；不得 commit/push、执行 overlay `--apply` 或启动实验。

成功标准：运行时 bridge 与 bundle 均 `0755` 且 SHA-256 仍为上述值；`--verify-bundle`、installer
`--check`、15/15 source hash、bridge self-test、single/multi `diff --check` 通过。完成后交回 Lead；Lead
复核通过后才能交给 Sol 以精确 pathspec 提交 single 公共 identity，绝不纳入 single 既有大量 untracked
history/results。

### 交接指令

```text
handoff_status: BLOCKED
handoff_model: low-level-implementation
handoff_command:
严格执行 state/sol_plan.md 第 30 节；仅把运行时 px4_bridge.py mode 从 0775 改为 0755，保证字节/hash
不变，并追加修正 Terra mode 证据。完成规定的只读/离线验证后交回 lead；不要 commit/push、apply overlay、
启动实验或创建 approval package。
```

## 31. 2026-08-22 single 公共 overlay identity 精确提交边界

Lead 复核第 29–30 节通过。Sol 下一步只审核并提交 single 公共 identity，不得把它与 multi 工作树、
实验执行或其它 single 未跟踪历史混合。

single 仓库基线：`main@c01f1f5af40ec25631aa11765a0f21e06834abc4`。允许加入 commit 的 pathspec
严格只有：

- `platform_overlays/range20m_omnidirectional_v1/current_config.sha256`；
- `history/RUN-20260822T000000Z-px4-bridge-readiness-identity/px4_bridge.py`。

提交前必须重验：清单 diff 仅 bridge 一行；21 条；bundle/runtime 均 mode `0755`、SHA-256
`5cce75ddb7b3d21476a2492f7769cedd43bbfbdd2430dfe69562443bd87becf3`；installer
`--verify-bundle` 与 `--check` 均通过；single `diff --check` 通过。必须用精确 pathspec 暂存并核对
`git diff --cached --name-status` 恰为上述两项。不得加入 single 既有任何其它 untracked history/results，
不得 push、不得修改/清理其它文件。

Sol commit 成功后记录新 single commit hash、branch 和 commit file list，交回 Lead；下一阶段再由 Terra 只同步
multi 的 `single_commit` frozen identity、相关 source hashes，并复跑 static 53/53。Sol 本步不得修改 multi、
不得创建 approval package或启动实验。

## 32. 2026-08-22 bridge bundle trailing-whitespace 同步清理

### 审核决定

不批准 `diff --check` 豁免。运行时 bridge 第 150、168、198、331 行均为只含空格的空白行，位于语句之间，
不改变 Python 语义；应在公共 identity commit 前机械清理并重新冻结 identity。single index 当前为空，HEAD
仍为 `c01f1f5af40ec25631aa11765a0f21e06834abc4`，尚无错误 commit。

### 目标与允许写入

Terra 只允许修改：

- `/home/houslakers/swarm_ws/src/Swarm-LIO2/swarm_lio/scripts/px4_bridge.py`：仅删除第 150、168、
  198、331 行的行尾空格，保留空白行、全部代码和 mode `0755`；
- `/home/houslakers/auto_tune_racer/swarmlio-single-v2/history/RUN-20260822T000000Z-px4-bridge-readiness-identity/px4_bridge.py`：
  做完全相同的四处机械清理，保持与运行时文件逐字节一致及 mode `0755`；
- `/home/houslakers/auto_tune_racer/swarmlio-single-v2/platform_overlays/range20m_omnidirectional_v1/current_config.sha256`：
  仅同步 bridge 条目的新 hash，source/mode/root/target 不变，其余 20 条不变；
- `config/2uav_static.yaml`、`experiments/manifests/2uav_smoke.yaml`：仅同步新的 overlay manifest SHA；
- `config/2uav_source_hashes.sha256`：同步运行时 bridge、bundle、overlay manifest、static config 和
  experiment manifest 的级联 hash；
- `state/terra_implementation.md`：追加清理前后 hash、精确四行范围和验证证据。

不得修改任何非空白代码、readiness 行为、参数、installer、安全门、mapper/collector/runner/preflight、launch、
approval package、旧 runroot、正式状态文件或其它外部 dirty 文件；不得 commit/push、apply overlay 或启动实验。

### 成功标准

1. 运行时 bridge 与 bundle `cmp` 相同、mode 均 `0755`、新 SHA-256 相同；与清理前版本的文本差异严格只有
   上述四个空白行的 trailing spaces。
2. bridge `py_compile` 与 `--self-test` 通过；针对两份 bridge 的 `diff --check`/no-index check 无输出。
3. overlay 清单仍 21 条且仅 bridge hash 相对第 29 节变化；installer `--verify-bundle`、`--check` 均通过。
4. `sha256sum -c config/2uav_source_hashes.sha256` 全部通过，multi/single `diff --check` 通过；single 精确
   task status 仍只有清单和 bundle，index 必须为空。
5. 完成后交回 Lead 复审；Sol 第 31 节提交边界不变，但必须使用本节新 identity。不得创建 approval package。

### 交接指令

```text
handoff_status: BLOCKED
handoff_model: low-level-implementation
handoff_command:
严格执行 state/sol_plan.md 第 32 节；只清理运行时 bridge 与 bundle 指定四个空白行的 trailing spaces，
同步 overlay/multi 全部级联 hash并追加 Terra 证据。禁止任何语义改动、commit/push、overlay apply、实验或
approval package；完成规定的精确 diff、self-test、21 条及 source-hash 验证后交回 lead。
```

## 33. 2026-08-22 multi frozen single identity 同步与 static 53/53

### 已审核输入

single 公共 identity 已由 Sol 以精确两文件 commit 落盘：

```text
repository: /home/houslakers/auto_tune_racer/swarmlio-single-v2
branch: main
old_commit: c01f1f5af40ec25631aa11765a0f21e06834abc4
new_commit: aea4b71cff10061f3211ffa1d2b21a6500caac78
commit_files:
  A history/RUN-20260822T000000Z-px4-bridge-readiness-identity/px4_bridge.py
  M platform_overlays/range20m_omnidirectional_v1/current_config.sha256
overlay_manifest_sha256: bc9864fc24741526548094d425cda877a84d27aabf0ab92cdef08b206fecd2d0
bridge_sha256: b673080c46916790431f257aea1a27fa8616adeb6b409fe22968e0316b57f34f
```

父提交为旧 frozen identity，single 当前 HEAD 正是新 commit 且 tracked-clean。此任务不改变算法、overlay
内容或公共环境，只同步 multi 对已提交公共 identity 的引用。

### 允许写入

Terra 只允许修改：

- `config/2uav_static.yaml`：仅将 `frozen.single_commit` 更新为完整新 commit；
- `experiments/manifests/2uav_smoke.yaml`：仅将顶层 `single_commit` 更新为同一完整 commit；
- `config/2uav_source_hashes.sha256`：仅同步上述两个文件的级联 hash，保留其余 13 条和值；
- `state/terra_implementation.md`：追加 identity 同步与静态验证证据。

不得修改任何源码、脚本、launch、参数、overlay/bundle/installer、approval package、旧 runroot、正式状态
文件或外部仓库；不得 commit/push、启动 ROS/Gazebo/live preflight/smoke。

### 成功标准

1. multi config 与 manifest 的 `single_commit` 均且仅为完整
   `aea4b71cff10061f3211ffa1d2b21a6500caac78`；platform/environment/overlay/installer identity 不变。
2. single `HEAD==aea4b71...`、tracked-clean；commit file list 恰为已审核两项；overlay installer
   `--verify-bundle` 与 `--check` 均 21/21 通过。
3. `sha256sum -c config/2uav_source_hashes.sha256` 15/15 通过；manifest、static config 和 source-hash
   manifest 的最终 SHA-256 全部记录。
4. 运行 `two_uav_preflight.py --mode static`，必须真实得到 `passed: true`、53/53；保存输出到 `/tmp` 即可，
   不创建 runroot。runner/bridge/preflight 必要 self-test 与 `git diff --check` 通过。
5. 完成后交回 Lead 审核；本任务不授权生成或修改 approval package。静态 53/53 也不自动授权 preflight，
   更不得进入 smoke。

### 交接指令

```text
handoff_status: BLOCKED
handoff_model: low-level-implementation
handoff_command:
严格执行 state/sol_plan.md 第 33 节；仅同步 config 与 manifest 的 frozen single commit 到完整
aea4b71cff10061f3211ffa1d2b21a6500caac78，更新两项级联 source hash并追加 Terra 证据。完成 15/15、
single/overlay identity 与真实 static 53/53 验证；不要修改源码、commit/push、启动实验或创建 approval package。
```

## 34. 2026-08-22 smoke 失败：peer inflation-neighborhood endpoint mask

### 审核结论

```text
runroot: results/RUN-20260821T184138Z-2uav-smoke
decision: SMOKE_FAIL_PEER_ECHO_INFLATES_UAV1_START
approved_new_package: false
approved_smoke_retry: false
consumed_package: a798ca4a30cab5972bc652074433f471fd6bf85dc0f09d3a87e3f88f2bcb3874
```

uav0 command 链正常（trajectory 8、pos_cmd/ACK 2540/2540、移动 21.68 m）；uav1 trajectory/pos_cmd/ACK
均为 0、freeze=true。racer 共 1349 次 vehicle start inside inflated occupancy，末次 sim56.167 位于 uav1
悬停点 `(1.35293,0.171142,1.49432)`。mapper 累计 77 个 uav1 hover voxel、5549 hits，全部
`source_uav=uav0`；这是 peer 回波进入静态 occupancy 后被 planner `0.35 m` inflation 扩张到 uav1 起点的
运行期直接证据。随后 uav1 occupancy 停更超过 5 s 触发 freshness abort；该 abort 是后果且 fail-closed
正确，不得通过放宽 freshness 掩盖零 command 链。

不得清空/强制 free 起点地图，因为会删除真实静态障碍；不得移动 spawn、减小 planner inflation、放宽 A*、
修改 goal 或 freshness。现有 exact collision endpoint/ray mask 只删除 primitive 内或射线穿过 primitive 的点，
但没有删除落在 peer collision surface 外、却会被冻结 occupancy inflation 膨胀进 peer 起点的 endpoint。
`points_in_iris_inflation_neighborhood()` 已以 exact-distance 实现该冻结邻域，目前仅诊断不参与发布，故可在
不引入新半径/参数的情况下复用为最小发布 mask。

### 允许写入

Terra 只允许修改：

- `scripts/two_uav_gt_mapper.py`：将 available peer pose 下的 endpoint mask 定义为
  `exact_collision_endpoint OR exact_distance_to_collision<=OCCUPANCY_INFLATION_M`；现有 exact collision
  ray-intersection mask 保持不变；最终 removed 为三者 union；
- `config/2uav_source_hashes.sha256`：仅同步 mapper hash；
- `state/terra_implementation.md`：追加实现、精确公式、测试、hash 与风险。

不得修改 collector freshness、runner/preflight、manifest/config/launch、RACER/PX4/MAVROS、collision
primitives、`OCCUPANCY_INFLATION_M=0.35`、pose slop、ray mask、downsample/range、world/spawn/goal、approval
package、旧 runroot 或正式状态文件；不得清理地图、增加经验 epsilon/半径、commit/push 或启动实验。

### 实现合同与审计

1. 仅当 `peer_pose_status==available` 时计算 inflation-neighborhood endpoint mask；missing/stale/
   uncomparable/nonfinite 仍原数组全量保留，不得推测删除。
2. 使用现有 primitive exact-distance 函数与冻结 `0.35`，不得用 voxel 批量、轴对齐大盒、起点球或经验 margin。
   ray mask 仍只对原 collision primitives 做 closed-segment intersection，不对 inflation 体积做 ray 扩张。
3. 新增独立累计 `peer_inflation_endpoint_candidates`；保留 exact endpoint/ray 计数；
   `peer_removed_points` 必须等于三 mask union，不允许重复计数，且逐 scan/累计保持
   `published_points = registered_points - peer_removed_points`。
4. provenance 必须区分被新 mask 删除的 candidate 与 published hover voxels；available pose 不得进入
   unavailable counters。不得把诊断输入或原数组原地修改。

### 离线成功标准

- self-test 覆盖：primitive 内、primitive 外但 exact distance `<=0.35`、边界 tangent、刚好超出、rotated
  primitive、三 mask 重叠 union、真实环境远点保留、available/unavailable/nonfinite、输入不可变和计数恒等式；
- 基于本轮 uav1 悬停坐标/voxel 的合成回归证明旧 exact mask 会保留而新 endpoint mask 删除，但超出冻结
  inflation 邻域的点不删；不得声称离线测试已证明 runtime 问题消失；
- mapper py_compile/self-test、15/15 source hash、static 53/53、`git diff --check` 通过；manifest/static/
  collector/runner/preflight hash 必须不变。

实现交回 Lead 后，只能先决定是否签发一次新的 diagnostic preflight；不得直接 smoke。

### 交接指令

```text
handoff_status: BLOCKED
handoff_model: low-level-implementation
handoff_command:
严格执行 state/sol_plan.md 第 34 节；仅在 two_uav_gt_mapper.py 中把现有冻结 0.35 m exact-distance
peer inflation-neighborhood 用作 available-pose endpoint mask，保持 exact ray mask、unavailable 全保留与所有
参数不变；新增独立审计计数和规定 self-test，更新 mapper source hash与 Terra 证据。不要修改 freshness/
起点地图/manifest/package，不要启动实验、commit 或 push。
```

## 35. 2026-08-22 RUN-20260821T190032Z diagnostic preflight 审核

### 审核决定

```text
runroot: results/RUN-20260821T190032Z-2uav-preflight
decision: DIAGNOSTIC_PREFLIGHT_PASS
live_preflight: 48/48
approved_source_fix: false
approved_new_preflight: false
approved_smoke_in_this_turn: false
consumed_package: 6ce1ec44d6b71d78aac31e6e63e44a4da7e6460e7ca95f677c776e921e07e5b3
```

基础门全部通过：static 53/53、live 48/48、final safety、逐机 telemetry、8/8 process liveness 和 clean
teardown 均成立，无 abort/contact/crash，RT≈0.341。两机均到达约 z=1.49 的物理悬停状态。

`execution_result.md` 对 removed 口径的文字转录有误：`peer_removed_points` 严格是 peer pose available 时
`exact endpoint ∪ inflation-neighborhood endpoint ∪ exact ray` 的并集；
`peer_unavailable_body_candidates` 与 `peer_unavailable_inflation_candidates` 是 unavailable/stale 时基于已发布点
计算的反事实诊断，并未删除任何点，也不进入 removed。第二快照两方向发布恒等式成立；removed 小于三类
candidate 数量之和是 mask 重叠去重的预期结果，不是漏计。

`uav1_hover_voxels={}` 不是单次快照或记录窗口缺失。该字段从每次实际 published array 持续累计，以冻结
uav1 悬停世界坐标为中心、0.35 m 球邻域取样；本轮两次诊断快照均为空，而两方向 inflation endpoint mask
分别累计激活 6012/11711，说明该邻域发布残留在本轮被消除。unavailable 反事实计数仍被单独保留，故空值
不能由 unavailable scan 被静默删除解释。

RACER 仍记录 274 次 start-inflated，但末次为 sim17.580、uav1 z≈1.133、尚在上升；到最终悬停和
sim25.7 结束前未持续复发。与失败 smoke 中 1349 次持续至 sim56.167、悬停点仍被占据相比，运行证据支持
peer-body 回波污染根因及第 34 节 endpoint mask 修复有效。当前没有证据支持修改起点地图、planner、spawn、
inflation、goal 或放宽 occupancy freshness；这些改动均不批准。

### 下一 package 决策

不再重复 diagnostic preflight，也不签发额外源码修复任务。若后续另行授权继续，下一种有信息增益的 package
应是绑定当前冻结 identity、manifest 固定 120 sim s 的单次 smoke，并继续保留全部 fail-closed watchdog；
但遵照本轮“不得进入 smoke”的明确约束，本节不创建、不修改任何 approval package，也不授权 launch。

未来 smoke 的硬门必须逐机证明 trajectory/pos_cmd/ACK 非零、无 ACK timeout、无 freeze、无 occupancy
freshness abort，并报告 sim≥goal 后 start-inflated 次数/末次时间位置及 mapper hover-voxel provenance。
任一机零 command 链、最终悬停持续 start-inflated、hover voxel 复发、abort 或证据缺失均为 SMOKE_FAIL。

禁止复用已消费 package/runroot、修改原始 runroot、放宽安全/telemetry/freshness 合同、现场调参、再次
preflight、启动 smoke、commit/push 或在本阶段更新正式状态文件。

## 36. 2026-08-22 RUN-20260821T191146Z：occupancy 合同与算力诊断加固

### 审核结论

```text
decision: SMOKE_FAIL_OCCUPANCY_OBSERVER_BACKPRESSURE
both_uavs_engaged: true
approved_smoke_retry: false
approved_new_package_now: false
consumed_package: fdf91a8adbb310fccbf5d426043df05850eab84623d0a77de70d9e0d1a062eca
```

本轮不是 planner/bridge/process death：uav0/uav1 trajectory 6/5、pos_cmd/ACK 2062/2062 与
2273/2273、路径 11.69/9.33 m、freeze=false，8/8 节点存活且无 crash/contact/ACK timeout。peer endpoint
修复有效：start-inflated 229 次且末次 sim17.753，上升后不再复发。直接失败为 sim50.99 的
`corrupted_telemetry:uav1:freshness`。

`/sdf_map/occupancy_all_N` 不是轻量健康心跳，而是 RACER `MapROS::publishMapAll()` 每次遍历当前全地图并序列化
完整 PointCloud2 的可视化/coverage snapshot；当前由 0.2 sim s timer 触发。collector 又在 rospy callback 中同步
遍历每帧点云、订阅未限制为 latest-only。地图增长、RT≈0.324 时，发布重建、ROS 序列化和 Python coverage
遍历会产生反压；进程仍存活且 odom/cloud/health/pos_cmd/ACK 连续，只有 occupancy 超过 5 wall s，故不能将其
等同 corrupted telemetry。第五次同类触发说明继续增大 freshness 阈值不是可接受修复。

当前 runroot 没有逐进程 CPU/RSS、线程 CPU、topic byte rate 或 callback duration，因此不能声称已精确量化
Gazebo、RACER、mapper 和 collector 的占比。机器为 i7-13700H、20 logical CPUs、15 GiB RAM；RT≈0.3 并非
内存不足的直接证据，必须先补齐可审计 profile。

### 第一阶段：最小 blocker 修复与 profile（本任务）

Terra 只允许修改：

- `scripts/two_uav_collector.py`：将 occupancy 从 continuous freshness 改为 startup presence + coverage
  snapshot；仍要求启动宽限期内至少一帧且解析异常立即 abort。occupancy subscriber 必须 `queue_size=1`，只保留
  最新帧；覆盖率解析按冻结的 sim-time 周期 coalesce（建议 2.0 sim s），跳过中间重帧但记录 received、processed、
  dropped/coalesced、callback wall duration、last message/processed sim+wall age。不得改变 odom/cloud/health、
  pos_cmd/ACK、TF、owner、process death 和 ACK timeout 的 continuous/fail-closed 合同；
- `scripts/two_uav_runner.py`：为 preflight/smoke 增加只读资源采样器，按 1 wall s 记录 `/proc` process-tree 的
  per-role CPU time/delta、RSS、线程数、系统 load/memory、wall/sim/RT 到 runroot-local append-only
  `resource_usage.jsonl`，并在 execution result 中汇总 p50/p95/max 与 top consumers；采样失败只标记证据缺失，
  不得影响控制时序或用 shell/ROS CLI 高频探针；
- `config/2uav_static.yaml`：显式冻结 occupancy `startup_presence`、coverage coalesce sim period 和资源采样 wall
  period；`freshness_s=5.0` 保留给真正 continuous channels，不得全局调大；
- `scripts/two_uav_preflight.py`：静态核对上述分类/周期，live/final 要求 occupancy presence、coverage available、
  profile 文件 schema 完整，但不得要求 occupancy 每 5 wall s 发布；
- `config/2uav_source_hashes.sha256`：仅同步上述级联 hash；
- `state/terra_implementation.md`：追加实现 diff、测试、hash 与风险证据。

不得修改 RACER/PX4/Gazebo/mapper/bridge、manifest duration/seed、LiDAR range/FOV/rate、world/spawn、planner
参数、安全 abort 列表、旧 runroot、approval package 或正式状态文件；不得 commit/push 或启动实验。

### 第一阶段成功标准

1. collector self-test 证明 occupancy 有首帧即满足 presence，超过 5 wall s 不进入 stale；零帧、解析异常仍
   fail-closed；其余 continuous channel 超时仍 abort；queue/coalesce 不丢失累计 coverage union 的已处理帧。
2. 合成高频大消息调度测试证明同时到达时只处理 latest frame，received/processed/coalesced 与 callback latency
   可审计；不得启动 ROS/Gazebo 做验证。
3. resource sampler 纯函数/临时假进程测试覆盖 PID 消失、子进程聚合、CPU delta、RSS、sim stall 和输出 schema；
   采样周期不得生成 subprocess 风暴。
4. collector/runner/preflight py_compile+self-test、source hash 全通过、static preflight 全通过、
   `git diff --check` 无输出；manifest 与 mapper hash 不变。
5. 完成后回 Lead 审核。合格后只签发一次 diagnostic preflight package，先验证新 telemetry contract 与 profile
   开销；不得直接重签 smoke。

### 面向 4-UAV 的后续算力方案（不属于本次写入授权）

第一阶段 profile 后按证据处理 top consumer。已知最优先候选是将 RACER 全图可视化发布从硬编码 0.2 sim s
改为显式低频 snapshot（初始建议 2.0 sim s）或增量/局部 coverage feed，使每机全图扫描从 5 Hz 降至 0.5 Hz；
该变化涉及公共 RACER/single overlay identity，必须单独任务、单一公共 commit、2-UAV A/B preflight 后才能用于
3/4-UAV，不能在本任务静默修改。保持规划地图更新、ESDF、控制、odom/registered cloud 频率不变，只削减
可视化/指标复制开销。

扩展顺序必须为 2→3→4 UAV，每级先做固定 30 sim s profile preflight，再做 smoke；记录每机与总 CPU/RSS、
topic MB/s、callback p95、RT factor。若降低全图 snapshot 后 Gazebo/LiDAR 成为 top consumer，再单独评估 headless
sensor update/点数预算；不得先降 planner 安全分辨率、LiDAR 20 m/360°语义或 PX4 控制频率。目标不是用更宽
freshness 掩盖 RT，而是让观测负载近似线性扩展，并以 profile 证明 4 机不会因全图 O(N×map-volume) 复制失控。

### 交接指令

```text
handoff_status: BLOCKED
handoff_model: low-level-implementation
handoff_command:
严格执行 state/sol_plan.md 第 36 节；只修改 collector/runner/preflight/static/source-hash 与 Terra 证据。
将 occupancy 改为 startup presence + latest-only/coalesced coverage snapshot，保留其它 fail-closed 门；增加低开销
runroot-local per-process resource profiler。完成全部离线验证后交回 lead。不得修改 RACER/mapper/manifest/package，
不得启动实验、commit 或 push。
```

## 37. 2026-08-22 第 36 节复审：修复 coalescing 饥饿与 profile 证据缺口

### 复审决定

```text
implementation_review: REJECTED_NEEDS_MINIMAL_CORRECTION
approved_preflight_package: false
approved_smoke: false
```

总体边界合规，但存在阻断性竞态：`_process_occupancy_snapshots()` 在锁外解析 captured pending；解析期间若 callback
写入新帧，当前代码因 `state.pending_occupancy is not pending` 而丢弃已经成功解析的旧帧。在持续大消息流下，
每次处理都可能被新帧替换，造成 `samples["occupancy"]==0`、startup presence/coverage 永久饥饿。这正是本任务
必须避免的反压模式，现有 self-test 未覆盖。

资源 profile 另有两个证据缺口：profiler 在全部 start-stack readiness 完成后才创建，遗漏既往最容易触发负载
问题的 PX4/Gazebo/RACER 启动阶段；preflight soak 调用 `sample()` 未传 sim time，因此 diagnostic preflight 无法
形成 wall/sim/RT 序列。当前 summary 只累计 raw CPU ticks 和 RSS percentiles，没有按 wall interval/CLK_TCK
归一化的 role CPU-core utilization p50/p95/max，不能充分回答 RT≈0.3 的算力归因。

### 最小修正授权

Terra 只允许继续修改：

- `scripts/two_uav_collector.py`：成功解析 captured frame 后必须提交其 coverage/presence，即使 pending 已被更新；
  若 pending 仍是 captured 才清空，否则保留 newer frame 给下一周期。不得覆盖或清空 newer frame。拆分 callback
  与 processing duration，并在 snapshot 中给出 received/processed/coalesced、last wall/sim 和基于当前 reference
  计算的 message/processed age；
- `scripts/two_uav_runner.py`：让 1 wall s profiler 覆盖 stack 启动/readiness、preflight soak 和 smoke monitor；
  每个有效样本记录 sim time（取不到时显式 evidence_missing，不伪造），记录 wall delta，并按系统 CLK_TCK 输出
  每 role `cpu_cores`，summary 提供 CPU p50/p95/max、RSS p50/p95/max、top consumers 与有效 RT 样本；
- `scripts/two_uav_preflight.py`：仅同步 profile schema/static/live 验证与 self-test；
- `config/2uav_source_hashes.sha256` 与 `state/terra_implementation.md`：同步 hash 和修正证据。

`config/2uav_static.yaml` 当前三个冻结值不得再改；manifest/mapper/RACER/approval package/旧 runroot/正式状态文件
不得修改。不得启动实验、commit 或 push。

### 修正成功标准

1. 确定性并发测试模拟 parse 期间 A 被 B 替换：A 必须成功计入 coverage/presence，B 保持 pending 并在下一次
   处理；无新帧时 captured 才清空。连续替换不得导致 processed 永远为零。
2. startup 零帧和解析异常仍 abort；occupancy 不进入 5 s stale；其它 continuous/fail-closed 门保持原测试。
3. profiler fake `/proc`/fake clock 测试覆盖启动阶段动态 role、wall delta、CLK_TCK 归一化、sim missing、RT、PID
   消失与 CPU/RSS percentiles；不得用 subprocess 高频采样。
4. py_compile/self-tests、source hash、static 53/53、`git diff --check` 全通过，manifest/mapper/static hash保持
   当前审核值不变。修正后回 Lead；仍不得自行创建 package。

### 交接指令

```text
handoff_status: BLOCKED
handoff_model: low-level-implementation
handoff_command:
严格执行 state/sol_plan.md 第 37 节；修复 occupancy captured-frame 提交竞态，确保 newer pending 不被覆盖并补齐
确定性并发测试；让 resource profiler 覆盖启动/readiness/soak/monitor，补齐 sim/RT 与归一化 CPU p50/p95/max。
只修改规定文件并完成离线验证。不得改 static 冻结值、manifest/mapper/RACER/package，不得启动实验、commit/push。
```

## 38. 2026-08-22 RUN-20260821T194922Z：公共 4-UAV compute baseline 准备

### 审核结论

```text
decision: PREFLIGHT_PASS_RESOURCE_CAPACITY_FAIL_FOR_4UAV
occupancy_contract: PASS
approved_next_package: false
approved_smoke: false
consumed_package: 3b30d6591f22be886e188607875aea569fe4e8e0ec88a30a0cb1959f463db33f
```

本轮 static 53/53、live 49/49、final safety 和 clean teardown 全通过。两机 occupancy received/processed/
coalesced 为 35/7/28、46/7/38，processed 均持续前进、coverage available、最终 age<1 s，无 freshness abort；
因此 occupancy 从 5 wall s continuous freshness 解耦为 startup presence + coalesced snapshot 的合同适配成立。

资源门不满足 4-UAV 扩展：MemAvailable 从约 13 GiB 降至最低 1.25 GiB、结束约 1.29 GiB；RACER 进程树
RSS max 7.25 GiB，Gazebo/PX4 进程树 5.17 GiB。RSS 含共享页重复计数，不能与系统使用量直接相加，但
MemAvailable 是系统级硬证据。CPU 主要集中在 racer p95≈2.18 cores、gazebo p95≈1.50 cores，20 logical CPUs
并未整体饱和；RT≈0.342 更符合少数串行热点和重地图操作，而非总核数不足。

冻结 `sdf_map/resolution=0.05` 在 50×50×3 m 上每机约 6000 万 voxel。SDFMap 为每 voxel 分配多组 double、short
和 flag buffer，理论常驻量与实测每机约 3.6 GiB 同量级。改为 0.10 m 可将 voxel 数和主要地图 buffer 降至
约 1/8，是在 16 GiB 主机上尝试 4 机的必要 baseline 变更；只降低 `occupancy_all` 发布频率不能解决常驻内存。

Resource profiler 的瞬时 RT 在 0/≈1.98 间交替是 collector 2 sim s flush 与 1 wall s sample 的混叠，不能用其
p50=0 作为性能门；整体 RT 必须用连续 `/clock` 首末 sim delta / wall delta，profile 保留用于 role CPU/RSS。

### 本任务目标与允许写入

Terra 只准备新的公共 compute overlay，不提交、不 apply、不启动实验：

- 运行时 RACER `swarm_exploration/exploration_manager/launch/single_drone_planner.xml`：仅将
  `sdf_map/resolution` 从 0.05 改为 0.10，并新增/设置 `map_ros/all_map_publish_period` 为 2.0 sim s；其它 planner、
  inflation、range/FOV、box/world 与安全参数不变；
- 运行时 RACER `swarm_exploration/plan_env/src/map_ros.cpp`：读取正数参数
  `map_ros/all_map_publish_period`（默认 0.2 保持向后兼容），`show_all_map` 时按 ROS/sim elapsed period 发布
  `occupancy_all`；local map、ESDF、地图融合、规划和控制 timer 不变。拒绝非有限/非正配置并 fail-fast；
- single 新建一个明确命名的 immutable history bundle，逐字节保存上述 XML 与 C++ 两文件；更新
  `platform_overlays/range20m_omnidirectional_v1/current_config.sha256` 中恰好对应两项 source/hash，保持 21 条、
  root/target/mode 与其它 19 条不变；
- multi `config/2uav_static.yaml`、`experiments/manifests/2uav_smoke.yaml`：仅同步新 overlay manifest identity，并
  冻结/readback `sdf_map/resolution=0.10`、`map_ros/all_map_publish_period=2.0`；
- multi `scripts/two_uav_preflight.py`：静态/live readback 新两值；
- multi `scripts/two_uav_runner.py` 与 static contract：增加负载门，但不得改变实验时长或控制合同：启动前
  `MemAvailable>=8 GiB` 且 load1<10；stack-ready/soak 期间 `MemAvailable>=3 GiB`、无新增 swap-in/out，并记录
  连续 `/clock` 区间整体 RT。资源不足必须 fail-closed，不得通过增大 freshness 掩盖；
- `config/2uav_source_hashes.sha256` 与 `state/terra_implementation.md`：同步完整 identity/验证证据。

公共 single identity 未经 Sol 精确 pathspec commit 前，multi 的 `single_commit` 不得伪造更新；static 必须保持
fail-closed 或明确为 prepared-not-committed。不得修改 mapper/collector/bridge/PX4/Gazebo sensor、A*/ESDF
分辨率、20 m/360° LiDAR、obstacles inflation、goal/seed/duration、旧 runroot、approval package 或正式状态文件；
不得 commit/push、apply overlay 或启动 ROS/Gazebo/preflight/smoke。

### 离线成功标准

1. XML diff 仅包含 resolution 0.05→0.10 与 all-map period 2.0；C++ self-contained test/helper 覆盖默认 0.2、
   配置 2.0、sim elapsed、时间回退与非法值，证明仅 full-map visualization cadence 改变。
2. 按 50×50×3 计算 voxel 6000万→750万，列出各 SDF buffer 理论字节与 2/4-UAV projected resident lower bound；
   不得声称 RSS 精确等于理论值。
3. RACER 相关 package Release build 通过；bundle 与 runtime 两文件逐字节一致，overlay verify-bundle/check 21/21，
   single index 为空。
4. load-gate 纯测试覆盖 8/3 GiB 边界、load1、swap delta、缺失证据和连续 clock RT aggregate；不得用瞬时混叠
   RT 作为 gate。当前阶段不要求 static 53/53，因为公共 identity 尚未提交。
5. multi py_compile/self-tests、source hashes（允许 prepared identity）、`git diff --check` 通过；完成后交回 Lead，
   由 Sol 审核并形成唯一公共 single identity commit。提交和 multi frozen identity 同步完成后才可复跑 static，
   再决定一次 diagnostic preflight；不得直接 smoke。

### 后续 3/4-UAV 门

2-UAV 新 baseline diagnostic preflight 必须达到 MemAvailable min≥3 GiB、无 swap activity、overall RT≥0.5，并
证明 full-map publish 实际约 0.5 Hz sim。之后才能按 2→3→4 每级单次 30 sim s resource preflight 扩展；每级
启动前仍保留至少 8 GiB，运行中至少 3 GiB。若 0.10 m baseline 在 4-UAV 仍不满足内存门，则本机禁止 4-UAV
full-fidelity，需升级到至少 32 GiB（建议 64 GiB）或另立 shared/sparse map 架构任务，不得继续降安全/感知语义。

### 交接指令

```text
handoff_status: BLOCKED
handoff_model: low-level-implementation
handoff_command:
严格执行 state/sol_plan.md 第 38 节；准备公共 compute overlay：SDF resolution 0.10 m、仅 full-map visualization
period 2.0 sim s，并加入 8/3 GiB、load/swap 与 overall RT 负载门。只修改授权文件和新 immutable bundle，完成
build/离线验证后交回 lead。不得 apply、commit/push、启动实验、创建 package，或修改 mapper/collector/PX4/
LiDAR/planner 安全语义。
```

## 39. 2026-08-22 compute overlay 审核与 single 公共 identity 收尾授权

### Lead 审核结论

```text
decision: IMPLEMENTATION_PREPARATION_PASS
static_preflight: FAIL_CLOSED_52_OF_53
failed_check: source.single_tracked_clean
approved_preflight_package: false
approved_smoke_package: false
```

第 38 节实现边界与证据通过审核：运行时 XML 与新 bundle 逐字节一致，运行时 `map_ros.cpp` 与新 bundle
逐字节一致；两者 SHA256 分别为 `9c0ce4b2a489e019aee01cfcf124a11d66cdcc7bc10cdc5b82b69cdc3aa73721`
和 `fc23045c16e2f81aa9110a0ede8b2161e50805303a3a361bccfd1609f51e70ae`。overlay manifest 仍为
21 项且只替换上述两项。runner/preflight self-test 均通过，multi source hashes 15/15 一致，multi 与 single
`git diff --check` 无错误。

当前 static 52/53，唯一失败为 single 的
`platform_overlays/range20m_omnidirectional_v1/current_config.sha256` 尚未提交；因此不得创建 approval package，
不得运行 preflight/smoke。当前 frozen `single_commit=aea4b71...` 只是旧公共 identity，不能代表新 compute overlay。

### Sol 唯一允许动作

在 single 仓库仅以精确 pathspec 暂存并提交以下三项：

1. `platform_overlays/range20m_omnidirectional_v1/current_config.sha256`
2. `history/RUN-20260822T201500Z-compute-overlay-prepared/map_ros.cpp`
3. `history/RUN-20260822T201500Z-compute-overlay-prepared/single_drone_planner.xml`

提交前必须确认 `git diff --cached --name-status` 恰为这三项，且 `git diff --cached --check` 无输出；不得纳入
single 中其它 untracked history/results。提交后记录完整 commit、branch 和三文件列表并交回 lead。不得修改 multi、
不得 push、apply overlay、启动实验或创建 approval package。

新 single commit 形成后，lead 再签发独立 low-level 任务：只同步 multi frozen single identity 及关联 source hash，
复跑 static 53/53。只有该门通过后，才重新决定一次性 diagnostic preflight package；不得直接 smoke。

### 交接指令

```text
handoff_status: READY
handoff_model: sol-finalize-sync
handoff_command:
严格执行 state/sol_plan.md 第 39 节。仅以精确 pathspec 暂存并提交 single 公共 compute overlay 的
current_config.sha256、map_ros.cpp bundle、single_drone_planner.xml bundle 三文件；提交前确认 cached file list
恰为三项且 diff --cached --check 无输出。记录新 commit、branch、文件列表后交回 lead。不得纳入其它 untracked
history/results，不得修改 multi、push、apply overlay、启动实验或创建 approval package。
```

## 40. 2026-08-22 compute XML 历史空白的最小字节清理

### Lead 决定

```text
decision: CLEAN_EXACT_WHITESPACE_NO_EXEMPTION
known_findings: 10 trailing-whitespace lines
approved_commit: false
approved_experiment_package: false
```

10 处 trailing whitespace 均可在旧公共 XML 中找到，属于历史继承而非本轮 resolution/full-map period 改动新增。
但新 bundle 是新增文件，`git diff --cached --check` 会正确检查整文件。公共 compute identity 尚未提交，当前正是
清理这些无语义字节的最低风险窗口；不批准永久豁免。

### Terra 唯一允许动作

1. 在 single 仓库先用精确 pathspec 将第 39 节的三项从 index 取消暂存，必须保留工作树内容，不得使用会丢弃
   工作树的 reset/checkout；确认 index 为空。
2. 只删除运行时
   `/home/houslakers/racer_ws/src/RACER/swarm_exploration/exploration_manager/launch/single_drone_planner.xml`
   中当前 `git diff --cached --check` 所列的 10 处行尾空白；不得重排、格式化或改变 XML 值。
3. 将清理后的 XML 逐字节同步到 single
   `history/RUN-20260822T201500Z-compute-overlay-prepared/single_drone_planner.xml`；不得修改 bundle `map_ros.cpp`。
4. 只更新 single `platform_overlays/range20m_omnidirectional_v1/current_config.sha256` 中 XML bundle 的 SHA256。
5. 在 multi 只同步该新 XML SHA 派生的 overlay manifest SHA：更新 `config/2uav_static.yaml`、
   `experiments/manifests/2uav_smoke.yaml`、必要的 `config/2uav_source_hashes.sha256`，并在
   `state/terra_implementation.md` 追加证据。`single_commit` 仍保持现有已提交 identity，不得伪造未来 commit。

### 成功标准

- XML runtime 与 bundle `cmp` 相同，XML 解析通过；语义 diff 相对清理前只含 10 处行尾空白删除；resolution 仍为
  0.10，all-map period 仍为 2.0；`map_ros.cpp` SHA 保持
  `fc23045c16e2f81aa9110a0ede8b2161e50805303a3a361bccfd1609f51e70ae`。
- overlay manifest 保持 21 项，除 XML hash 外无新变化；verify-bundle/check 21/21。
- single index 为空，single/multi `git diff --check` 无输出；不得重新暂存或提交。
- multi py_compile/self-tests、source hashes 15/15 通过；static 允许且预期仅因 single tracked dirty 保持 52/53，
  不得据此创建 package。

### 禁止动作

不得修改 C++、planner/感知/安全参数、mapper/collector/runner/preflight 逻辑、world/launch、旧 runroot、正式状态文件
或 approval package；不得 apply overlay、commit/push、启动 ROS/Gazebo/preflight/smoke，也不得暂存其它 single 文件。

### 交接指令

```text
handoff_status: READY
handoff_model: low-level-implementation
handoff_command:
严格执行 state/sol_plan.md 第 40 节。先安全取消 single 三个精确 pathspec 的暂存且保留工作树；只清理 runtime 与
bundle XML 的 10 处历史行尾空白，更新 single overlay manifest 和 multi 关联 identity/hash，完成规定静态验证并
交回 lead。不得修改语义、commit/push、apply overlay、启动实验或创建 approval package。
```

## 41. 2026-08-22 清洁 compute overlay 的 single identity 提交授权

### Lead 审核结论

```text
decision: WHITESPACE_CLEANUP_PASS
static_preflight: FAIL_CLOSED_54_OF_55
failed_check: source.single_tracked_clean
approved_preflight_package: false
approved_smoke_package: false
```

runtime/bundle XML 均为 `6739a77cc56bcf91a9525a0ea4b6932b40c1994cb485e437cbed9e587072d227`，
逐字节一致、无 trailing whitespace，resolution=0.10、all-map period=2.0。`map_ros.cpp` 未变，仍为
`fc23045c16e2f81aa9110a0ede8b2161e50805303a3a361bccfd1609f51e70ae`。overlay manifest 为
`68ceb54faa24f4cc97396634bfc3d611f8e40a6db89999d3cbabc112092ccf62`，verify-bundle/check 均 21/21；
multi source hashes 15/15、runner/preflight self-test 和 multi/single diff-check 均通过。

static 54/55 的唯一失败是 single overlay manifest 尚未提交，故此时不得创建 approval package或启动实验。

### Sol 唯一允许动作

在 single 仓库仅以精确 pathspec 暂存并提交：

1. `platform_overlays/range20m_omnidirectional_v1/current_config.sha256`
2. `history/RUN-20260822T201500Z-compute-overlay-prepared/map_ros.cpp`
3. `history/RUN-20260822T201500Z-compute-overlay-prepared/single_drone_planner.xml`

提交前必须确认 cached name-status 恰为上述三项、`git diff --cached --check` 无输出，并复核 XML/map_ros SHA 与
本节一致。提交后记录完整 commit、branch、三文件列表；不得纳入其它 untracked history/results，不得修改 multi、
push、apply overlay、启动实验或创建 approval package。

提交完成后交回 lead，另行签发只同步 multi frozen single identity 与关联 hash、复跑 static 55/55 的任务。

### 交接指令

```text
handoff_status: READY
handoff_model: sol-finalize-sync
handoff_command:
严格执行 state/sol_plan.md 第 41 节。仅精确暂存并提交 single 的 current_config.sha256、compute map_ros.cpp bundle、
clean XML bundle 三文件；cached 列表必须恰为三项且 diff --cached --check 无输出。记录 commit/branch/文件列表后
交回 lead。不得纳入其它文件、修改 multi、push、apply overlay、启动实验或创建 approval package。
```

## 42. 2026-08-22 multi frozen single identity 同步

### Lead 审核结论

single commit `8c8ddf2add3f7b3ce4f9943583fd945f16b1bd91` 的父提交为
`aea4b71cff10061f3211ffa1d2b21a6500caac78`，branch `main`，tracked tree 干净；commit 文件列表恰为
compute `map_ros.cpp` bundle、clean XML bundle 与 overlay manifest 三项，commit diff-check 无输出。对应 SHA
仍分别为 `fc23045c...70ae`、`6739a77c...2d227`、`68ceb54f...cf62`。公共 single identity 合格。

### 唯一允许修改

Terra 只允许：

1. 将 `config/2uav_static.yaml` 的 `frozen.single_commit` 从 `aea4b71...` 更新为完整
   `8c8ddf2add3f7b3ce4f9943583fd945f16b1bd91`；
2. 将 `experiments/manifests/2uav_smoke.yaml` 的 `single_commit` 同步为同一完整 commit；
3. 仅更新 `config/2uav_source_hashes.sha256` 中受上述两文件变化影响的 hash；
4. 在 `state/terra_implementation.md` 追加 identity 与验证证据。

不得改变 overlay SHA、resolution/full-map period、资源门、任何算法/安全/实验参数或其他代码。

### 成功标准与禁止动作

- 两个 frozen single commit 均精确等于 `8c8ddf2add3f7b3ce4f9943583fd945f16b1bd91`，overlay manifest SHA
  保持 `68ceb54faa24f4cc97396634bfc3d611f8e40a6db89999d3cbabc112092ccf62`；
- source hashes 15/15、static 55/55、multi/single `git diff --check`、runner/preflight self-test 全通过；
- single tracked tree/index 保持干净，runtime/bundle identity 不变；
- 不得修改正式状态文件、approval package、旧 runroot，不得 commit/push、apply overlay、启动实验。

static 55/55 只恢复可审核身份，不自动授权 preflight。完成后必须交回 lead 单独决定 package，smoke 仍禁止。

### 交接指令

```text
handoff_status: READY
handoff_model: low-level-implementation
handoff_command:
严格执行 state/sol_plan.md 第 42 节。仅将 multi static/manifest 的 frozen single identity 更新为
8c8ddf2add3f7b3ce4f9943583fd945f16b1bd91，更新两项派生 source hash 并追加 Terra 验证；复跑 static 55/55。
不得改其它参数/代码、commit/push、启动实验或创建 approval package。完成后交回 lead。
```
