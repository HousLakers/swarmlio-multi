# Sol 复审决定：50×50 已静态切换，实验仍拒绝

- 日期：2026-08-20
- 审核输入：`state/sol_plan.md`、`state/terra_implementation.md`、当前 git diff、
  `experiments/manifests/2uav_smoke.yaml`
- manifest SHA-256：
  `1f7a4a3d3981582188813b51d04c0f9e4dea4149f9e5c400ef31fb5f0ee4b41a`
- active source hash manifest SHA-256：
  `06694c20f48d6d0ff6d8507c95061897312fc77bf3f962a6c327bf97592dd1b9`

```text
approved_preflight: false
approved: false
decision: REJECTED_MINIMAL_REWORK_REQUIRED
environment_switch: ACTIVE_STATIC_VALIDATED_RUNTIME_PENDING
allowed_next_action: TERRA_R1_TO_R4_STATIC_REWORK_ONLY
```

## 1. 审核结论

用户确认后，环境相关 map size 与 box bounds 已按边界解冻。50×50 室外场景已经先
登记到公共 `racer-platform` baseline，再由 multi 的 active contract、PX4 launch、
RACER launch 和唯一 manifest 引用。world、baseline、multi source 均有 SHA-256；SDF、
几何、launch 展开和静态 preflight 通过。20 m、水平全向、近场/A*、startup/ACK 与
guard 参数没有修改。

因此原 R5 的“场景未激活、尺寸/边界不匹配、无公共基线”已在静态层面解决。但 R1–R4
仍是阻断项，且 single 独立接入、live 参数回读、namespace/TF/telemetry/log 隔离均无
运行证据。本次不能批准 preflight，也不能批准 smoke。

## 2. 50×50 切换证据

- 公共 baseline：`racer_outdoor_50x50_v1`，manifest SHA-256
  `48d00fca6032c76f59ca26134ff39dba2d555a552c2d73f81e3ca51b4583dc44`；
- 公共 world 与 multi 审计副本 SHA-256：
  `28a306b646297011b564c5ce94ac97634281a5e9a34e337956c5f4a9227c320e`；
- 地面 50×50 m、4 个周界墙、4 个建筑块、8 个门洞隔墙、4 根柱，共 21 models；
- UAV0 `(0,0)`、UAV1 `(1.5,0)`，内部障碍净空至少 3 m；
- 两节点最终 launch 参数：`map_size_x/y=50.0`，x/y box bounds
  `[-24.5,24.5]`；`map_size_z=3.0`、z bounds 与冻结 planner 保持不变；
- `gz sdf -k` PASS；自定义几何校验 PASS；`sha256sum -c` 11/11；静态 preflight
  `passed=true`；`roslaunch --dump-params` 对两节点展开值一致；
- manifest 仍为 `blocked_pending_verified_launch_and_preflight`，runner launch gate
  实测拒绝并退出 2，未启动进程。

公共 baseline 文件当前是 `racer-platform` HEAD
`57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc` 上的未提交新增文件；它有内容 hash，但尚未
经过最终 Sol 收尾 commit。不能把 baseline_id 误解为已提交发布版本。

## 3. 继续拒绝的阻断项

### R1：严重接触语义未闭环

collector 仍可能把正常地面接触当作 severe contact。必须区分地面、障碍和机间碰撞，
定义力/穿透/持续时间或等价阈值，并提供“不误杀正常接触、严重接触必 abort”的 probe。

### R2：fleet 成功指标不完整

逐机 completion 没有真实事件来源；coverage 缺少有效区域分母；overlap 与 map
consistency 仍复用同一 Jaccard；ACK timeout 恢复后的成功/失败政策未定义。

### R3：运行期安全 watchdog 不完整

尚无持续 topic owner、TF parent、odometry/cloud/health/ACK freshness 检查，无法证明
namespace/TF 串线或 telemetry 停更会生成 append-only abort 并全局停止。

### R4：批准状态与 hash 迁移死锁

runner 要求修改已被 source hash 锁定的 manifest status，导致批准动作本身破坏签名。
必须采用独立、不可变 approval 包绑定 manifest SHA 与 source hash manifest SHA，并
覆盖 blocked、preflight-approved、smoke-approved、hash drift 四类 gate probe。

## 4. 最小返工事项

1. 仅修复 R1–R4，不再改 world、环境尺寸或冻结单机参数。
2. 更新 collector/watchdog/approval gate 及对应纯函数或静态 probe。
3. 更新 `state/terra_implementation.md` 和全部执行 hash，交 Sol 重新审核。
4. 下次审核至多决定是否允许一次 manifest 白名单 preflight，不自动批准 smoke。

## 5. 禁止动作

- 不得运行 preflight、Gazebo、2-UAV smoke 或长跑；
- 不得把 manifest 改为 approved；
- 不得修改 `project_state.md` 或 `state/SESSION_HANDOFF.md`；
- 不得 commit、push、切换分支或覆盖任何 runroot。

## 6. 2026-08-21 最新复审：拒绝签发新的 preflight package

审核输入为 `state/terra_implementation.md` 第 13 节、当前工作树、唯一 manifest、
source hash manifest、runner 与旧 package 消费 receipt。未启动 ROS、Gazebo 或实验。

```text
approved_preflight_retry: false
approved_smoke: false
decision: REJECTED_INCOMPLETE_ROS_CHILD_ENVIRONMENT_ISOLATION
```

已通过的证据：manifest SHA-256 为
`e366f943180cb1471742ab2a84e685d75e64442fd00c8bf75e14a00ee618a0f2`；source hash
manifest SHA-256 为
`9981436ce27c013065ae63fcce71dd814c7acee765b1b60e1c675b0e3ba7e098`；12/12 hash、
runner self-test、53/53 静态 preflight、py_compile 和 `git diff --check` 均通过。
`process_specs()` 的五个长期进程具有 runroot 专属 export，环境/argv 也会写入新 runroot。

拒绝原因：`wait_topic()`、`sim_time_s()` 和 smoke trigger 的 ROS CLI 子进程未显式绑定
runroot 的 `ROS_LOG_DIR`/`ROS_HOME`。独立执行 `monitor` 或 `collect` 时，新 runner 进程
通过 `load_active()` 恢复生命周期，但没有恢复该 runroot 的 ROS 环境，因此仍存在回落到
调用者 `~/.ros`、污染跨 runroot 状态的路径。该问题违反 `state/sol_plan.md` 第 8 节
“所有子进程”与“不得回落”的硬门。

旧 package SHA-256
`57a76ff0e3d1829684cac38b8a725e0d9b36df006be2f5e37cbd58fafd65b60f`
已存在消费 receipt；`state/2uav_approval.yaml` 保持旧内容，未签发新 package。最小返工
任务和边界见 `state/sol_plan.md` 第 9 节。smoke 继续禁止。

## 7. 2026-08-21 最新复审：批准一次 manifest 白名单 preflight

### 决定

```text
approved_preflight_retry: true
approved_smoke: false
decision: APPROVED_SINGLE_USE_PREFLIGHT_ONLY
```

本决定取代第 6 节的返工拒绝，但不批准 smoke。审核输入仅为 `AGENTS.md`、
`state/current_summary.md`、`state/terra_implementation.md` 第 14 节、当前工作树、唯一
manifest、source hash manifest、runner、approval 合同和旧消费 receipt；未启动 ROS、
Gazebo、preflight 或实验。

### 冻结输入与签发身份

- 唯一 manifest：`experiments/manifests/2uav_smoke.yaml`，SHA-256
  `e366f943180cb1471742ab2a84e685d75e64442fd00c8bf75e14a00ee618a0f2`；
- source hash manifest：`config/2uav_source_hashes.sha256`，SHA-256
  `05fada5472ec02436c6d12c0fef6e4fd766a57911a86ca8abb09bffc6ab077e4`；
- runner：SHA-256
  `d6313ef2c25b8fe39d9431a322de064de3bc8734c084e11b791299012c248a64`；
- 新 approval package：`state/2uav_approval.yaml`，SHA-256
  `3bf111dbe3d06e0f545ecc4a81cf4636e5a964b370af7dc0d1245b3403359e43`；
- package 合同：`stage: preflight`、`allowed_actions: [preflight]`、`issued_by: sol`、
  `max_uses: 1`。只绑定上述 manifest 和 source hash manifest；不允许 `launch`。

旧 package SHA-256
`57a76ff0e3d1829684cac38b8a725e0d9b36df006be2f5e37cbd58fafd65b60f`
已消费；新 package 摘要不同，且当前不存在对应消费 receipt。只读调用
`approval_guard("preflight", ...)` 已通过，未消费新包。

### 审核证据

- `Popen` 五个长期进程均显式传入 runroot 子进程环境，并保留 argv/export 落盘证据；
- `wait_topic()`、`sim_time_s()` 和 trigger 均通过 `ros_command_spec()` 显式传入相同
  `ROS_LOG_DIR`/`ROS_HOME`；
- `live_checks()` 在 runroot 环境作用域内运行，作用域退出后恢复调用环境；
- `load_active()` 由保存的 runroot 重建环境，不回落到新 runner 的 `~/.ros`；
- 不同 runroot、伪造共享环境、ACTIVE 恢复和三类 ROS CLI 均有纯函数/self-test；
- py_compile、runner self-test、12/12 source hash、53/53 静态 preflight、
  `git diff --check` 全部通过；manifest、20 m 水平全向参数、50×50 world、namespace、
  ID、端口、时长和 seed 未在本次返工中改变。

### 允许执行与成功标准

仅允许执行 manifest 白名单中的以下一条命令一次：

```text
python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml
```

执行器必须在启动前重新核对四项摘要、approval 字段、无新 package receipt、静态参数
快照和无 active lifecycle；必须使用允许 ROS 网络接口枚举的受批准执行环境。runner 创建
新 append-only runroot 后应立即消费 package，并把 approval、manifest、静态检查、
`runtime_environment.json` 和 `process_specs.json` 固化到 runroot。

只有 `live_preflight.json.passed=true`，且 namespace/topic/TF/clock/逐机参数回读、日志隔离、
watchdog soak、逐机/fleet telemetry 与最终安全 metrics 全部通过，才算 preflight 成功。
成功或失败后都必须停止全部进程、保留原始 runroot，并交回 `lead-planning`；不得自动进入
smoke。

### 禁止动作

- 不得执行 manifest 的 `launch`、smoke、长跑、参数搜索或任何非白名单命令；
- 不得修改源码、manifest、冻结参数、approval package 或环境基线后继续使用本批准；
- 不得复用旧或新 package；不得删除/覆盖 receipt 与任何 runroot；
- 不得修改 `project_state.md`、`state/SESSION_HANDOFF.md`，不得 commit、push 或切换分支；
- 若网络权限、hash、参数快照、ROS 日志目录或 active lifecycle 任一门不满足，必须在创建
  新 runroot 前拒绝；若 runner 已消费 package，则只能保留失败证据并回 Sol 重新审核。

## 8. 2026-08-21 第二次 preflight 失败后的批准状态

```text
approved_new_preflight_package: false
approved_smoke: false
decision: BLOCKED_PENDING_RUNTIME_WIRING_AND_DETECTION_REWORK
```

第 7 节 package SHA-256
`3bf111dbe3d06e0f545ecc4a81cf4636e5a964b370af7dc0d1245b3403359e43`
已由 `RUN-20260821T060734Z-2uav-preflight` 消费，不得复用。该 run 的静态身份、参数回读、
日志隔离与 fail-closed 停栈通过，但 `live_preflight.json.passed=false`，首个 abort 为
`corrupted_telemetry:uav0:freshness`；因此第 7 节执行授权已终止，smoke 不获批准。

归因：首要为 runner 对两个非 chained catkin devel 空间的环境组合错误；workspace
baseline 是触发条件但本轮不要求修改。次要为 collector 在正常 teardown 的 liveness
误报；此外 GT mapper 的实际消息流和合同 TF 缺失、live TF 空集误通过均须在新 package
签发前修复。最小任务包、允许文件、成功标准与禁止动作见 `state/sol_plan.md` 第 10 节。

## 9. 2026-08-21 第 12 节复审：批准一次 manifest 白名单 preflight

### 决定

```text
approved_preflight_retry: true
approved_smoke: false
decision: APPROVED_SINGLE_USE_PREFLIGHT_ONLY
```

本决定仅批准一次新的 preflight，不批准 manifest 的 `launch`、smoke 或长跑。审核输入为
`state/sol_plan.md` 第 12 节、`state/terra_implementation.md` 第 17 节、当前工作树、唯一
manifest、source hash manifest、runner、approval contract 与旧消费 receipt；未启动 ROS、
Gazebo 或实验。

### 冻结身份与新批准包

- manifest：`experiments/manifests/2uav_smoke.yaml`，SHA-256
  `e366f943180cb1471742ab2a84e685d75e64442fd00c8bf75e14a00ee618a0f2`；
- source hash manifest：`config/2uav_source_hashes.sha256`，SHA-256
  `91c91c0cdb67b5603cc95ea3cda942440ffec8cd676c3dbcd6ed646add9d0d4e`；
- runner：SHA-256
  `06f2ae31c5514cbb2efeae3be266f1d77d188a1c695380183a8d532501a308de`；
- 新 approval package：`state/2uav_approval.yaml`，SHA-256
  `8b3b75309100f43e68808f6380bc44bbfc2cda5de2b766d9ad665eabb07a4937`；
- package 字段：`stage: preflight`、`allowed_actions: [preflight]`、
  `issued_by: sol`、`max_uses: 1`。

新 package 已通过只读 `approval_guard("preflight", ...)`，对应 receipt 当前不存在。
旧 package `3bf111dbe3d06e0f545ecc4a81cf4636e5a964b370af7dc0d1245b3403359e43`
的 receipt 仍存在，旧包不得复用。审核时不存在 active lifecycle。

### 审核证据

- 双 workspace 组合环境可同时解析 `swarm_lio`、`exploration_manager` 与
  `quadrotor_msgs.msg`，并绑定临时 runroot-local `ROS_HOME`/`ROS_LOG_DIR`；
- readiness gate 每次使用 payload probe 后的 bridge node 快照，再检查所有已启动 Popen；
  deadline 终态使用相同 sample，不硬编码失败 payload；
- runner self-test 直接覆盖 gate 成功、零 payload timeout、当前/此前 Popen 退出、缺 bridge
  node，以及 payload probe 期间 bridge node 消失；
- GT mapper 双机 TF、live empty/multi-parent/zero-payload、collector active/teardown liveness
  纯函数证据通过，freshness、TF、topic-owner 与 ACK 合同未放宽；
- 四脚本 py_compile/self-test、source hash 12/12、静态 preflight 53/53、
  `git diff --check` 全部通过；manifest、20 m 水平全向参数与 50×50 场景未改变。

### 唯一允许动作与执行门

只允许执行以下 manifest 白名单命令一次：

```text
python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml
```

执行器启动前必须重新核对上述四项 SHA-256、package 字段、receipt 不存在、无 active
lifecycle、静态参数快照，以及运行环境允许 ROS 网络接口枚举。runner 创建 append-only
runroot 后立即消费新 package。成功或失败都必须完整停栈、保存原始 runroot，并交回
`lead-planning`；不得自动进入 smoke。

### 成功标准与禁止动作

只有 `live_preflight.json.passed=true`，且双机 raw scan/MAVROS odom/registered
cloud+odom/frontier、bridge nodes、唯一动态 TF、参数回读、日志隔离、owner/ACK、watchdog
soak、逐机/fleet telemetry 与 final safety 全部通过，preflight 才算成功。

不得修改源码、manifest、参数、workspace、approval package、receipt 或旧 runroot后继续
使用本批准；不得执行 `launch`、smoke、长跑、参数搜索或非白名单命令；不得修改正式状态、
commit、push 或切换分支。任何 hash、环境、参数或 active gate 失败必须在创建新 runroot前
拒绝；若 package 已消费，则只能保留失败证据并回 Sol，不能重试或复用。

## 10. 2026-08-21 probe prefix 修复复审：批准一次 preflight

### 决定

```text
approved_preflight_retry: true
approved_smoke: false
decision: APPROVED_SINGLE_USE_PREFLIGHT_ONLY
```

本决定仅批准一次新的 manifest 白名单 preflight，不批准 `launch`、smoke 或长跑。审核输入为
`state/sol_plan.md` 第 13 节、`state/terra_implementation.md` 第 18 节、runner、source hash
manifest、冻结 manifest、approval contract、失败 runroot 摘要与旧 receipt；未启动 ROS、
Gazebo 或实验。

### 冻结身份与新 package

- manifest SHA-256：
  `e366f943180cb1471742ab2a84e685d75e64442fd00c8bf75e14a00ee618a0f2`；
- source hash manifest SHA-256：
  `f7939703b6fe232aeea7b7343e6538ae5baa2b32ad35d4bd4305fe5ce8f50c70`；
- runner SHA-256：
  `60bd1a8aa9455139cc4663b53408cc07b64777319a7b4f83b74417e9ebe4bd50`；
- 新 approval package SHA-256：
  `0944b9c08b0646efaaf82494cdca38c0263efa7f6dbc6f4a42ad0f05dd2ef79b`；
- package 字段：`stage: preflight`、`approved: true`、
  `allowed_actions: [preflight]`、`issued_by: sol`、`max_uses: 1`。

新 package 已通过只读 `approval_guard("preflight", ...)`，对应 receipt 不存在，审核时无
active lifecycle。失败 run 使用的 `8b3b75309100f43e68808f6380bc44bbfc2cda5de2b766d9ad665eabb07a4937`
已有 receipt，不得复用。

### 审核证据

- `ros_runtime_prefix()` 先 source Noetic，再重导出双 workspace package/prefix/Python/
  library 路径与 runroot-local ROS log/home；
- `process_specs()` 与 `workspace_probe_specs()` 共享该唯一 prefix；
- Sol 直接执行 runner 生成的三组实际 probe argv+env，`swarm_lio`、
  `exploration_manager`、`quadrotor_msgs.msg` 均 return code 0，stdout/stderr 符合预期；
- future `workspace_environment_probe.json` 包含 command、returncode、stdout、stderr，任一
  probe 失败仍 fail-closed；
- 四脚本 py_compile/self-test、source hash 12/12、静态 preflight 53/53、
  `git diff --check` 全部通过；manifest、workspace、冻结参数与旧 runroot 未修改。

### 唯一允许动作

执行器重新核对上述四项 SHA-256、package 字段、receipt 不存在、无 active lifecycle、静态
参数快照与 ROS 网络接口权限后，只允许执行一次：

```text
python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml
```

runner 创建新的 append-only runroot 后立即消费 package。成功或失败都必须完整停栈并保留
原始产物，然后交回 `lead-planning`；不得自动进入 smoke。

只有 live preflight、双机真实数据流、bridge nodes、唯一 TF、参数回读、日志隔离、owner/
ACK、watchdog soak、逐机/fleet telemetry 与 final safety 全部通过才算成功。不得修改源码、
manifest、参数、workspace、package、receipt 或旧 runroot后继续使用本批准；不得执行
`launch`、smoke、非白名单命令、commit、push、切换分支或修改正式状态。package 一经消费
不得重试或复用。

## 11. 2026-08-21 Livox headless baseline 修复复审：批准一次 preflight

### 决定

```text
approved_preflight_retry: true
approved_smoke: false
decision: APPROVED_SINGLE_USE_PREFLIGHT_ONLY
```

本决定只批准一次 manifest 白名单 preflight，用于验证 headless Gazebo 中双机 Livox raw
scan payload；不批准 `launch`、smoke、长跑或参数搜索。审核输入为 `state/sol_plan.md`
第 14、15 节、`state/terra_implementation.md` 第 19、20 节、当前工作树、公共环境 baseline、
唯一 manifest、source hash manifest、approval contract、旧失败 runroot 与 consumption
receipts；未启动 ROS、Gazebo 或实验。

### 冻结身份与新 package

- manifest SHA-256：
  `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`；
- source hash manifest SHA-256：
  `41fbe083ccc5cc7a25093985cd1ddf76cec4e852bf6b92a288a5f94e54a30bb0`；
- static contract SHA-256：
  `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`；
- runner SHA-256：
  `60bd1a8aa9455139cc4663b53408cc07b64777319a7b4f83b74417e9ebe4bd50`；
- 公共 baseline manifest SHA-256：
  `ce595cafba088955b38c4c9bd1d08f9af254dbfa0bf013481372a75e17980944`；
- PX4 iris model template SHA-256：
  `e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225`；
- `mid360.csv` SHA-256：
  `aa1fc08b6a4400608dbd6ee832b7ea3a9c3c37197e734f60f58fe5abf762269a`；
- Livox plugin binary SHA-256：
  `ad117f9290cc1ef091842023d30af0de89bff14724fc78192250f737442b90b6`；
- 新 approval package SHA-256：
  `1718c1cfda987f61650c8c39becddfc2d6ac6883938fdffd0bc4af860c2c3b10`。

新 package 字段为 `stage: preflight`、`approved: true`、
`allowed_actions: [preflight]`、`issued_by: sol`、`max_uses: 1`。Sol 已直接执行只读
`approval_guard("preflight", ...)`，结果通过；对应 receipt 当前不存在，审核时无 active
lifecycle。旧 package
`0944b9c08b0646efaaf82494cdca38c0263efa7f6dbc6f4a42ad0f05dd2ef79b`
已有 receipt，永久不得复用。

### 审核证据

- Livox ray sensor 直接包含 `always_on=true`；双机离线渲染得到唯一
  `laser_livox_0/1` 与 `uav0/1/laser_livox`；10 Hz、24000 samples、downsample、360 度
  水平视场、量程、噪声和相对 `livox/scan` 未改变；
- 公共 baseline、manifest 和 static contract 三层 identity 全部绑定同一 baseline SHA；
  baseline 内模型、双机渲染物、CSV、插件 source/dirty-diff/binary identity 均有证据；
- CSV 严格解析 800000/800000；空 EOF `cannot convert str:` 不再被错误归因为解析中断；
- `sha256sum -c config/2uav_source_hashes.sha256` 为 12/12；静态 preflight 为 53/53；
  preflight self-test、py_compile、multi 全量 diff check、iris model scoped diff check 和公共
  baseline no-index diff check 均通过；
- 冻结 20 m 水平全向单机参数、50x50 world、namespace/port/TF、日志隔离、readiness、owner/
  ACK、freshness 和 fail-closed 合同均未放宽。

PX4 Gazebo 子模块仍有本任务前已存在、且不在本次执行路径中的其它 dirty diff；本 package
通过公共 baseline 内的 model/plugin/CSV 完整 identity 和 multi source hash manifest 绑定实际
执行对象，不授权修改或清理这些旁支文件。

### 唯一允许动作、成功标准与禁止动作

执行器启动前必须重新核对上述 package、manifest、source hash manifest、runner、baseline、
model、CSV 和 plugin hash，确认新 receipt 不存在、无 active lifecycle、静态 preflight
53/53、workspace probe 与运行环境门可用。随后只允许执行一次：

```text
python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml
```

runner 创建新的 append-only runroot 后立即消费 package。只有 `live_preflight.json.passed=true`
且双机 raw scan、MAVROS odom、registered cloud/odom、frontier、bridge nodes、唯一动态 TF、
参数回读、日志隔离、owner/ACK、watchdog soak、逐机/fleet telemetry 和 final safety 全部通过，
preflight 才成功。

成功或失败都必须完整停栈、保存原始 runroot 和 execution result，并交回 `lead-planning`；不得
自动进入 smoke。不得修改源码、workspace、manifest、参数、package、receipt或旧 runroot 后
继续执行；不得运行 `launch`、smoke、长跑、commit、push、切换分支或修改正式状态。package
一经消费不得重试或复用。

## 12. 2026-08-21 live TF sampler 修复复审：批准一次 preflight

### 决定

```text
approved_preflight_retry: true
approved_smoke: false
decision: APPROVED_SINGLE_USE_PREFLIGHT_ONLY
```

本决定只批准一次 manifest 白名单 preflight，用于验证修复后的独立 `/tf` CLI sampler；不批准
`launch`、smoke、长跑或参数搜索。审核输入为 `state/sol_plan.md` 第 16 节、
`state/terra_implementation.md` 第 21 节、`scripts/two_uav_preflight.py`、当前 source hash
manifest、冻结 manifest/static contract、runner、approval contract、失败 runroot
`RUN-20260821T074112Z-2uav-preflight` 与旧 receipt；未启动 ROS、Gazebo 或实验。

### 冻结身份与新 package

- manifest SHA-256：
  `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`；
- source hash manifest SHA-256：
  `3ef1ce50b80fa3742462acf49f2312e34188673a3b56e824c7e6be16c8a39640`；
- `two_uav_preflight.py` SHA-256：
  `afa8b3821b2c8f3e2dfda2f5f65e5d960145ee1bf277d10c220157bde231a567`；
- static contract SHA-256：
  `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`；
- runner SHA-256：
  `60bd1a8aa9455139cc4663b53408cc07b64777319a7b4f83b74417e9ebe4bd50`；
- 新 approval package SHA-256：
  `bc75e406c7f9d94d4514abfd57588d23b7791f7af7216667ea6a5cb08a70713b`。

package 字段保持 `stage: preflight`、`approved: true`、
`allowed_actions: [preflight]`、`issued_by: sol`、`max_uses: 1`。Sol 已直接执行只读
`approval_guard("preflight", ...)`，结果通过；新 receipt 不存在，审核时无 active
lifecycle。旧 package
`1718c1cfda987f61650c8c39becddfc2d6ac6883938fdffd0bc4af860c2c3b10`
已有 receipt，永久不得复用。

### 审核证据

- `tf_echo_argv()` 为 `rostopic echo -n 10 /tf`，只从 TF sampler 移除了会排除
  `transforms[]` 的 `--noarr`；5 s timeout、有限消息数与 partial stdout 解析保留；
- `parse_tf_parent_sets()` 是独立纯函数，累计同一 child 的全部 parent；未过滤错 parent 或
  多 parent，也未读取 collector metrics；
- self-test 使用 TFMessage YAML fixture 覆盖双机正确边、空输出、缺 child、错 parent、同 child
  多 parent，并证明 exact-set contract 继续 fail-closed；
- 普通 `topic_has_payload()` 的 `--noarr` 未改变，点云 readiness 性能语义未扩大；
- py_compile、self-test、source hash 12/12、静态 preflight 53/53 与 multi
  `git diff --check` 全部通过；manifest、baseline、参数与 runner 均未改变；
- 上一 run 的 collector 独立观测到两条新鲜且唯一的 `world→uavN/base_link`，说明本次重试只需
  验证 CLI sampler，不需要修改 GT mapper 或 TF 合同。

### 唯一允许动作与成功标准

执行器启动前必须重新核对 package、manifest、source hash manifest、preflight 脚本、runner、
baseline/model/CSV/plugin identity，确认新 receipt 不存在、无 active lifecycle、静态
preflight 53/53 与 workspace 环境门可用。随后只允许执行一次：

```text
python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml
```

runner 创建新的 append-only runroot 后立即消费 package。只有 live TF CLI gate 与 collector
独立证据均显示两个 expected child 各自只有 parent `world`，并且上一轮已经通过的双机数据流、
参数回读、日志隔离、owner/ACK、watchdog soak、逐机/fleet telemetry、final metrics 与 final
safety 继续全部通过，preflight 才算成功。

成功或失败都必须完整停栈、保留原始 runroot 和 execution result，再交回 `lead-planning`；
不得自动进入 smoke。不得修改源码、workspace、manifest、参数、package、receipt或旧 runroot
后继续使用批准；不得执行 `launch`、smoke、长跑、commit、push、切换分支或修改正式状态。
package 一经消费不得重试或复用。

## 15. 当前有效授权索引（取代已消费的第 13 节 preflight 授权）

当前唯一有效 package 是第 14 节签发的 smoke package
`3986a46c53dd3c7cfae9dbc03eb388fe80327fc2d2f784b8506a01a8b3988038`：
`stage: smoke`、`allowed_actions: [launch]`、`max_uses: 1`。第 13 节 package
`57a21fa5fb90400fafb589df8beeaaecebc0f0e50084240b6905db6afe8b9fa4` 已消费，其“不得 launch”
约束只适用于当时的 preflight package，不覆盖第 14 节在审核 preflight PASS 后签发的新 smoke
授权。除 manifest 白名单的一次 `launch` 外，所有其它实验动作仍禁止。

## 14. 2026-08-21 preflight 通过复审：批准一次 120 sim-second smoke

### 决定

```text
reviewed_runroot: results/RUN-20260821T082048Z-2uav-preflight
preflight_result: PASS 48/48
approved_smoke: true
decision: APPROVED_SINGLE_USE_SMOKE_ONLY
```

本决定只批准一次冻结 manifest 的 `launch` 动作，运行 120 sim s、单次重复的 2-UAV smoke；
不批准第二次重复、长跑、参数搜索或扩大 UAV 数量。审核输入为该 runroot 的
`live_preflight.json`、fleet/逐机 metrics 与 telemetry、`execution_result.md`、当前 manifest、
source hash manifest、runner、static/approval contract 和 consumption receipts；未启动实验。

### preflight 审核结论

- live checks 48/48、静态 53/53、workspace probe 全通过；无 abort，final safety 通过；
- 双机 raw/registered cloud、MAVROS/registered odom、frontier、health、occupancy 都有真实数据；
- 唯一动态 TF 为 `world→uav0/base_link` 与 `world→uav1/base_link`；topic owner 无缺失、重复或漂移；
- 8/8 必需节点存活，`never_seen=[]`、`lost_after_seen=[]`；无 crash/contact；
- uav0/uav1 telemetry complete，missing/stale 均为空；frontier 分别 815/912；
- fleet coverage ratio 0.01334、map consistency 0.7996、overlap 0.9193、最小机间距离 1.471 m；
- preflight 无 goal，trajectory/pos_cmd/ack 均为 0，completion=false、freeze=true 属该阶段预期，
  同时说明 command/ACK、运动与协同任务语义尚未验证，必须由 smoke 覆盖。

### RT 风险与冻结身份

RT factor 约 0.306：10.00 sim s 用时 32.7 wall s，推算 120 sim s 约需 392 wall s。runner
具有 1200 s wall watchdog；collector 继续使用 5 s wall freshness、1 s wall ACK timeout、TF、
owner、process death、contact/crash fail-closed 门。本批准不放宽这些阈值，也不修改冻结单机参数。
低 RT 可能导致 ACK 或规划 callback 超时；若发生，应作为真实 smoke 失败保留，而不是现场调参重试。

冻结 identity：

- manifest：`75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`；
- source hash manifest：`0970f2e4b29aad999753270adb2cd8535d53826b4b0b651bced887e559657596`；
- collector：`efb27ff4335863f86e319a27ce8a06d8ad24ab90b3cf5eccac655d13c2540004`；
- static contract：`415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`；
- runner：`60bd1a8aa9455139cc4663b53408cc07b64777319a7b4f83b74417e9ebe4bd50`；
- 新 smoke approval package：
  `3986a46c53dd3c7cfae9dbc03eb388fe80327fc2d2f784b8506a01a8b3988038`。

新 package 字段为 `stage: smoke`、`approved: true`、`allowed_actions: [launch]`、
`issued_by: sol`、`max_uses: 1`。Sol 已执行只读 `approval_guard("launch", ...)`，验证通过；
新 receipt 不存在且无 active lifecycle。preflight package
`57a21fa5fb90400fafb589df8beeaaecebc0f0e50084240b6905db6afe8b9fa4` 已有 receipt，永久不得复用。

### 唯一允许动作与成功标准

执行器启动前必须重新核对 package、manifest、12/12 source hashes、53/53 static preflight、
workspace/environment identity、receipt 不存在及无 active lifecycle。随后只允许一次：

```text
python3 scripts/two_uav_runner.py launch --manifest experiments/manifests/2uav_smoke.yaml
```

runner 必须先通过内嵌 live checks 与 24 s no-goal soak 才能发布 goal。成功要求：
`exit_reason=duration_complete`、final safety 通过、无 abort/crash/severe contact/process death/
TF 或 owner cross-talk、两机 command/ACK 合同通过，并完整生成逐机 completion/freeze/crash/
contact/coverage/telemetry 和 fleet coverage/overlap/min-distance/map-consistency 证据。

无论成功或失败，都必须完整停栈，保留 append-only runroot、execution result、wall/sim 推进量和
RT factor，然后交回 `lead-planning`。package 一经消费不得重试或复用；不得现场修改源码、
workspace、manifest、参数、package、receipt 或旧 runroot；不得 commit/push、切换分支或更新
正式状态。

## 13. 2026-08-21 frontier channel 分类修复复审：批准一次 preflight

### 决定

```text
approved_preflight_retry: true
approved_smoke: false
decision: APPROVED_SINGLE_USE_PREFLIGHT_ONLY
```

本决定只批准一次 manifest 白名单 preflight，用于验证无 goal soak 中 frontier
startup-presence/continuous-freshness 分类；不批准 `launch`、smoke、长跑或参数搜索。审核输入为
`state/sol_plan.md` 第 17 节、`state/terra_implementation.md` 第 22 节、
`scripts/two_uav_collector.py`、当前 source hash manifest、冻结 manifest/static contract、
runner、approval contract、失败 runroot `RUN-20260821T075253Z-2uav-preflight` 与旧 receipt；
未启动 ROS、Gazebo 或实验。

### 冻结身份与新 package

- manifest SHA-256：
  `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`；
- source hash manifest SHA-256：
  `0970f2e4b29aad999753270adb2cd8535d53826b4b0b651bced887e559657596`；
- `two_uav_collector.py` SHA-256：
  `efb27ff4335863f86e319a27ce8a06d8ad24ab90b3cf5eccac655d13c2540004`；
- static contract SHA-256：
  `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`；
- runner SHA-256：
  `60bd1a8aa9455139cc4663b53408cc07b64777319a7b4f83b74417e9ebe4bd50`；
- 新 approval package SHA-256：
  `57a21fa5fb90400fafb589df8beeaaecebc0f0e50084240b6905db6afe8b9fa4`。

package 字段为 `stage: preflight`、`approved: true`、
`allowed_actions: [preflight]`、`issued_by: sol`、`max_uses: 1`，并绑定上述 manifest/source-hash
manifest。Sol 已用 runner 的只读 `approval_guard("preflight", ...)` 验证通过；对应 receipt
不存在，`/tmp/swarmlio_multi_2uav_active.json` 不存在。旧 package
`bc75e406c7f9d94d4514abfd57588d23b7791f7af7216667ea6a5cb08a70713b`
已有 receipt，永久不得复用。

### 审核证据

- `telemetry_channel_contract()` 保持 `odometry/cloud/health/occupancy` 为 5 s wall 连续
  freshness 通道；首次 PositionCommand 后且 completion 前，原样加入
  `trajectory/pos_cmd/ack`；ACK 1 s 合同未改变；
- frontier 在 completion 前必须至少出现一次，从未出现会进入
  `telemetry_missing_channels` 并 fail-closed；出现后不再把 visualization Marker 静默误判为
  5 s freshness 故障；
- frontier subscriber、逐机计数、readiness payload、topic-owner cardinality/drift 与
  `/exploration_node_1/2` 活动期 liveness 均保留；TF、coverage、crash、contact 和 process-death
  合同未放宽；
- self-test 覆盖 missing frontier、旧 frontier、过期 continuous channel、command 通道缺失与
  completion 语义；既有 ACK timeout 负向检查仍通过；
- Sol 复跑 py_compile、collector self-test、source hash 12/12、静态 preflight 53/53 和
  `git diff --check`，全部通过；manifest、static 参数、runner、单机/RACER 与环境 baseline
  未由本修复改变。

RT 约 0.33 仍是 smoke 前独立负载风险；本批准没有提高 `freshness_s`、缩放 wall-time 门或修改
单机参数。新 preflight 必须记录 wall/sim 推进量和实际 RT factor；即使 preflight 通过，也必须
先交回 lead 审核，不能自动进入 smoke。

### 唯一允许动作与成功标准

执行器启动前必须重新核对 package、manifest、source hash manifest、collector、runner、
baseline/model/CSV/plugin identity，确认 package receipt 不存在、无 active lifecycle、静态
preflight 53/53 与 workspace 环境门可用。随后只允许执行一次：

```text
python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml
```

runner 创建新的 append-only runroot 后立即消费 package。只有全部 live checks、双机真实
payload、唯一 TF、参数回读、日志隔离、24 s no-goal watchdog soak、topic owner、节点存活、
逐机/fleet telemetry、final metrics 与 final safety 全部通过，且两机 frontier 均至少观测一次，
preflight 才成功。执行结果必须记录 wall/sim 推进量和 RT factor。

成功或失败都必须完整停栈、保留原始 runroot 和 execution result，再交回 `lead-planning`；
不得自动进入 smoke。不得修改源码、workspace、manifest、参数、package、receipt或旧 runroot 后
继续使用本批准；不得执行 `launch`、smoke、长跑、commit、push、切换分支或修改正式状态。
package 一经消费不得重试或复用。

## 16. 当前有效授权（最终索引）

第 13 节 preflight 已由 `RUN-20260821T082048Z-2uav-preflight` 成功消费并完成 48/48；其
“不得 launch”限制不再是当前执行阶段。审核该 PASS 后，第 14 节签发了当前唯一有效 package：

```text
package_sha256: 3986a46c53dd3c7cfae9dbc03eb388fe80327fc2d2f784b8506a01a8b3988038
stage: smoke
allowed_actions: [launch]
max_uses: 1
approved_smoke: true
```

当前只允许执行一次 manifest 白名单 `launch`；不得复用已消费的 preflight package，不得进行
第二次重复、参数修改、长跑或其它实验动作。第 14 节的成功标准和禁止动作全部适用。

## 17. 2026-08-21 smoke 后授权终止（取代第 15/16 节索引）

`3986a46c53dd3c7cfae9dbc03eb388fe80327fc2d2f784b8506a01a8b3988038` 已由
`results/RUN-20260821T083254Z-2uav-smoke/` 消费，运行以 `abort_requested` 失败结束。
第 15/16 节关于“当前有效 smoke 授权”的描述已失效。

```text
active_approval_package: none
approved_preflight: false
approved_smoke: false
decision: BLOCKED_PENDING_MINIMAL_REPAIR_AND_NEW_PREFLIGHT_REVIEW
```

当前不得复用任何历史 package，不得现场调参或直接重试。后续只有完成
`state/sol_plan.md` 第 19 节最小修复、离线验证和 Sol 审核后，才可另行签发新的单次
`stage: preflight` package；不得直接签发 smoke。
