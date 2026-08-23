# Terra 实现记录：2-UAV 静态接入与 preflight 入口

- 日期：2026-08-20
- 任务来源：`state/sol_plan.md`
- 唯一 manifest：`experiments/manifests/2uav_smoke.yaml`
- 实现结论：`STATIC_INTEGRATION_IMPLEMENTED / RUNTIME_PREFLIGHT_NOT_RUN`
- 实验决定：`approved: false`

## 1. 根因定位

multi 仓库原先只有声明性 manifest，没有可执行的 2-UAV launch、preflight、collector
或 abort 接线。冻结工作区内虽存在多机骨架，但不能直接满足本轮合同：

- PX4 `multi_uav_mavros_sitl.launch` 的 UAV1 段被注释；
- Swarm-LIO 多机 launch 的 UAV1 段被注释；
- `swarm_exploration_multi.launch` 固定为 3 UAV，不符合固定 2-UAV 范围；
- 单机 GT mapper 把 UAV0 输入与 RACER ID 1 输出写死；
- 原 multi manifest 的 launch 是占位符，命令白名单为空；
- 没有逐机参数回读、日志隔离、ACK、fleet 指标或 fail-closed approval gate。

为避免修改冻结的 platform/single 源码，本实现只在 multi 仓库增加纯接线适配，并从
冻结 `single_drone_exploration.xml`/`single_drone_planner.xml` 继承全部算法参数。

## 2. 修改文件与行为

### 静态身份合同

- `config/2uav_static.yaml`
  - 固定 UAV0/UAV1 namespace、RACER ID、MAVLink system ID、初始位姿；
  - 固定 FCU/MAVLink/TCP/GST/camera 端口；
  - 固定 topic、world/child frame、逐机日志目录；
  - 显式使用本机冻结仓库 `swarmlio-single-v2`，不隐式解析旧的非 Git
    `swarmlio-single` 目录；
  - 固定 GT registration、20 m、水平 omnidirectional、0.35 和三个 guard=false。
- `config/2uav_source_hashes.sha256`
  - 锁定所有会被 manifest/runner 使用的 multi 配置、launch、脚本和 manifest；
  - runner 要求 Sol approval 同时绑定 manifest SHA 和本 hash manifest SHA。

### ROS 接线

- `launch/2uav_px4_sitl.launch`
  - 只启动 UAV0/UAV1；system ID 为 1/2；所有端口唯一；
  - Gazebo 是唯一 `/clock` 来源；禁用两架 MAVROS TF 发布。
- `launch/2uav_bridges.launch`
  - 两个独立 bridge node，绑定 `/uav0`、`/uav1` 和 RACER ID 1、2；
  - ACK、pos_cmd 和 odometry relay 由 ID 唯一化。
- `launch/2uav_racer.launch`
  - 两次 include 冻结的单机 exploration XML；`drone_num=2`；
  - 不覆盖或重写单机算法参数。

### GT registration、preflight 与采集

- `scripts/two_uav_gt_mapper.py`
  - 复用冻结单机 GT 同步注册语义；分别同步 UAV0/UAV1 scan 与 MAVROS odom；
  - 输出 `/cloud_registered_1/2`、`/lidar_slam/odom_1/2`、pose 1/2；
  - 应用各自初始偏移，child frame 为 `uav0/base_link`、`uav1/base_link`；
  - 固定 0.5–20.0 m 过滤、0.05 s sync slop 和 stride 3。
- `scripts/two_uav_preflight.py`
  - 静态检查三仓库身份、两个 overlay SHA、已安装 overlay 21/21、冻结参数、
    namespace/ID/端口/topic/TF child/log 目录、launch 接线、白名单及源码 hash；
  - live 模式检查 required topics、单一 `/clock`、`use_sim_time`、双机 ROS 参数回读、
    TF child-parent 串线和逐机/fleet 目录。
- `scripts/two_uav_collector.py`
  - UAV0/UAV1 独立追加 `telemetry.jsonl`，停机时独占创建最终 `metrics.json`；
  - 分别记录 completion observation、freeze、crash、contact、coverage voxels、
    telemetry、trajectory ACK timeout/recovery 和运动路径；
  - fleet 记录 union coverage、overlap、minimum distance、contact、map Jaccard、
    task-state、clock、telemetry completeness 和 process liveness；
  - crash、严重 contact、损坏 telemetry 和已出现节点的 process death 生成一次性
    `fleet/abort.request`，不覆盖原始记录。
- `scripts/two_uav_runner.py`
  - 只接受唯一 manifest 的五个固定 lifecycle 动作；
  - preflight/smoke 分别要求 manifest status 和 Sol approval，且 approval 必须绑定当前
    manifest 与源码 hash manifest；
  - blocked 状态 fail-closed，实测 launch 请求退出码 2，未启动任何进程；
  - 创建全新 append-only runroot 和 UAV0/UAV1/fleet 独立目录；
  - live preflight 失败时不触发规划，并自动清理全部进程；
  - smoke 启动后由 120 simulated-second watchdog 控制，abort、process death 或 wall
    watchdog 均会全局停机并保留 runroot。

### Manifest

- `experiments/manifests/2uav_smoke.yaml`
  - launch 占位符已替换为 approval-gated runner；
  - 白名单精确列出 preflight、launch、monitor、stop、collect 五条命令；
  - 增加唯一时钟和逐机 runtime parameter readback 硬门；
  - `approval_status` 保持 `blocked_pending_verified_launch_and_preflight`。

## 3. 冻结身份与参数证据

- platform：`57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`，tracked clean；
- single：`c01f1f5af40ec25631aa11765a0f21e06834abc4`，tracked clean；
- overlay manifest SHA-256：
  `80d0d06a5a9b3722804c28d3efc6ace9a71d5955b26f8124e12bf3579e0d9529`；
- overlay installer SHA-256：
  `7e2280d5d0ba88ee501764ab5b5ccc3f3724d5b6abf39704badc7a8976349151`；
- overlay probe：`OVERLAY_BUNDLE_READY files=21 base=57c1f34`；
- installed overlay probe：`OVERLAY_CHECK_OK files=21 base=57c1f34`；
- ROS launch 离线参数展开确认 exploration node 1/2 均为：
  `max_ray_length=20.0`、`depth_filter_maxdist=20.5`、
  `obstacles_inflation=0.35`、`horizontal_model=omnidirectional`、
  `perception_utils/max_dist=20.0`、三个冻结 guard=false。

## 4. 最终源码 SHA-256

| 文件 | SHA-256 |
|---|---|
| `config/2uav_source_hashes.sha256` | `b9aebebf10fc51680da21e02fdb4887a5436cfae72013f1d3768eabb8e4f62ec` |
| `config/2uav_static.yaml` | `b05cd6c7468429cb461e2bc08c1d068d0c97d3123e4c48941014c3a14e3ff3d1` |
| `launch/2uav_px4_sitl.launch` | `c49a327b6e79c3359d3a6e8ab178bb1f96dce26b125f96a9a6df151758c5d0d5` |
| `launch/2uav_bridges.launch` | `867e18dc99728cf7a4937b13d7712b848c10903993cdd5fe702a58990fb187a2` |
| `launch/2uav_racer.launch` | `b5b2ffb399b7a04c299e63007eb0f30ed70faccaf1626529e13521d29c09e4bc` |
| `scripts/two_uav_gt_mapper.py` | `92d376fd30a00171db8e460e871b24b08fd1bf41d8fd3439bc8d69b936f73dcc` |
| `scripts/two_uav_preflight.py` | `61492012480f1d680ba99824589c9330ed5a1ef548db63669ae45bd18ca67478` |
| `scripts/two_uav_collector.py` | `be3f1d2f124c703313fa692017f4f2171716ad6e8ce4733efb9877bebbeef074` |
| `scripts/two_uav_runner.py` | `3cca22f77601d080b6f1bf50015af0631299c42bda30df55b522cb6bd8002049` |
| `experiments/manifests/2uav_smoke.yaml` | `14a1d891ddabfa6a9618ccc695942c486397b78bfa8fb8b81ad7b3e324ec2a94` |

## 5. 验证命令与结果

以下均为静态或纯函数 probe，没有启动 ROS master、Gazebo、preflight 或实验：

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio_multi_pycache python3 -m py_compile ...
PASS

python3 scripts/two_uav_gt_mapper.py --self-test
two_uav_gt_mapper self-test: PASS

python3 scripts/two_uav_collector.py --self-test
two_uav_collector self-test: PASS

sha256sum -c config/2uav_source_hashes.sha256
9/9 OK

python3 scripts/two_uav_preflight.py --mode static \
  --config config/2uav_static.yaml \
  --manifest experiments/manifests/2uav_smoke.yaml \
  --output /tmp/2uav_static_preflight_final.json
passed: true

roslaunch --files launch/2uav_px4_sitl.launch
roslaunch --files launch/2uav_bridges.launch
roslaunch --files launch/2uav_racer.launch
PASS: all includes resolved; no nodes launched

roslaunch --nodes launch/2uav_racer.launch
PASS: unique exploration/traj/TSP/ACVRP nodes for IDs 1 and 2

roslaunch --nodes launch/2uav_bridges.launch
PASS: /px4_bridge_1 and /px4_bridge_2

python3 scripts/two_uav_runner.py launch \
  --manifest experiments/manifests/2uav_smoke.yaml
exit 2: REFUSED because approval_status is blocked

git diff --check
PASS
```

`roslaunch-check` 不存在（exit 127），已用 ROS 自带的 `roslaunch --files`、
`--nodes` 和 `--dump-params` 只解析检查替代。没有 C++ 或冻结工作区源码修改，因此未做
catkin rebuild；运行二进制是否与当前源码匹配仍属于 preflight 门。

## 6. 残余风险与交接决定

以下证据只有真实 2-UAV preflight 才能生成，本轮按计划未运行，因此不得批准实验：

1. `/clock` 唯一、单调和两节点共同 sim time 的 live 证据；
2. ROS graph 中全部 required topic 的双机归属和持续 telemetry；
3. live TF 树、跨 UAV parent 串线及持续 extrapolation 日志；
4. 双机 runtime ROS parameter readback；
5. UAV0/UAV1 独立 `telemetry.jsonl`、最终 metrics 与停止隔离的实测证据；
6. crash/contact/corrupted telemetry/process death abort 的运行时保全证据；
7. PX4/Gazebo、bridge、mapper、RACER 二进制与当前源码/环境的实际兼容性；
8. completion 没有专用 ROS 事件时记录为 `not observed`，smoke 有效性需依靠逐机实体
   运动或 Sol 预先认可的完成判据；
9. coverage 使用 0.25 m occupancy voxel union，overlap/map consistency 使用 Jaccard；
   Sol 必须在批准前确认这些 fleet 指标定义；
10. ACK collector 会逐机记录 1.0 s timeout 与恢复 ID，但“恢复后是否仍允许通过”尚未
    由 Sol 定义。

建议下一状态仍为：

```text
approved: false
allowed_next_action: SOL_REVIEW_TERRA_DIFF_AND_STATIC_EVIDENCE
```

本实现未修改 `project_state.md` 或 `state/SESSION_HANDOFF.md`，未 commit、未 push，
未创建任何 `results/RUN-*`。

## 7. 追加范围：50×50 m 室外 Gazebo 场景候选

用户随后要求从原 20×20 m 场景迁移到 50×50 m 室外障碍场景。由于该变更扩大了
冻结环境范围，本轮只生成候选和静态证据，未修改 active manifest、runner、
`config/2uav_static.yaml` 或 launch 默认 world：

- `worlds/2uav_outdoor_50x50_v1.world`
  - 50×50×0.1 m 静态地面；
  - 四面 3 m 高封闭周界墙；
  - 四个 4–5 m 高建筑块；
  - 八段带门洞的 3 m 高隔墙；
  - 四个柱状障碍；
  - UAV0 `(0,0)`、UAV1 `(1.5,0)` 起飞点到内部障碍的净空均不少于 3 m。
- `scripts/validate_2uav_outdoor_world.py`
  - 检查 SDF/XML、唯一模型名、50×50 地面、闭合周界、静态碰撞体、障碍数量、
    边界和双机起飞净空。
- `worlds/2uav_outdoor_50x50_v1.sha256`
  - world SHA-256：
    `28a306b646297011b564c5ce94ac97634281a5e9a34e337956c5f4a9227c320e`；
  - validator SHA-256：
    `ee7e1aa83a19a204edfe2277f4accb0a61a279477f4d4b057ef12314a7984c06`。

静态验证：

```text
python3 scripts/validate_2uav_outdoor_world.py \
  worlds/2uav_outdoor_50x50_v1.world
PASS: world=50x50m models=21 spawn_clearance>=3.0m perimeter=closed

xmllint --noout worlds/2uav_outdoor_50x50_v1.world
PASS

gz sdf -k worlds/2uav_outdoor_50x50_v1.world
Check complete
```

尚未激活的原因：当前冻结 planner 的 `sdf_map/box_min/max_x/y` 仍为约 ±9.7 m，
`launch/2uav_racer.launch` 的 map size 仍为 26×26 m。直接切换 world 会导致 50×50
场景的大部分区域位于可探索边界外；同时 single/multi 尚无共同的 50×50 公共环境
基线版本。激活至少需要 Lead 明确允许环境相关 map size/box bounds 解冻，公共环境
清单形成新版本，single 与 multi 分别做静态和 runtime 验证。

## 8. 用户确认后的 50×50 公共环境激活

用户已明确允许只解冻环境相关的 map size 与 box bounds，并要求切换场景。该确认不
解冻 20 m 视距、水平全向模型、near-field、A*、startup/ACK 或任何单机算法参数。

公共环境先登记于 `racer-platform`：

- baseline：`environment/baselines/racer_outdoor_50x50_v1.yaml`，SHA-256
  `48d00fca6032c76f59ca26134ff39dba2d555a552c2d73f81e3ca51b4583dc44`；
- world：`environment/worlds/2uav_outdoor_50x50_v1.world`，SHA-256
  `28a306b646297011b564c5ce94ac97634281a5e9a34e337956c5f4a9227c320e`；
- 公共 platform HEAD 仍为 `57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`；上述两项为
  未提交的新 baseline 文件，等待本轮最终收尾，不伪称已进入 commit。

multi 侧已将 `config/2uav_static.yaml`、`launch/2uav_px4_sitl.launch` 和唯一 manifest
切换到公共 world；`launch/2uav_racer.launch` 对两节点设置 `map_size_x/y=50.0`，并仅
覆盖 x/y box bounds 为 `[-24.5, 24.5]`。z 范围和所有冻结算法参数未变。
`two_uav_preflight.py` 现同时校验公共 baseline/world 哈希、active world、两节点 map
size/bounds 和冻结参数，并在 live 模式要求逐机回读这些环境参数。

切换后的静态证据：

```text
custom world validator: PASS (50x50, 21 models, closed perimeter, spawn clearance >=3m)
xmllint --noout: PASS
gz sdf -k: Check complete
sha256sum -c config/2uav_source_hashes.sha256: 11/11 OK
two_uav_preflight.py --mode static: passed=true
roslaunch --files launch/2uav_racer.launch: PASS
roslaunch --dump-params launch/2uav_racer.launch:
  node 1/2 map_size_x/y=50.0, box_min_x/y=-24.5, box_max_x/y=24.5
  node 1/2 max_ray_length=20.0, max_dist=20.0, horizontal_model=omnidirectional
runner launch gate probe: exit 2 / REFUSED while manifest remains blocked
```

切换后关键 hash：source hash manifest
`06694c20f48d6d0ff6d8507c95061897312fc77bf3f962a6c327bf97592dd1b9`；manifest
`1f7a4a3d3981582188813b51d04c0f9e4dea4149f9e5c400ef31fb5f0ee4b41a`；preflight
`b15247e8aa13b6f65da88ee6800d71652cc6e81553462617cbb38a80d9afab0e`。

本节只证明公共环境登记和 multi 静态激活。single 的独立场景接入、两侧 runtime
参数回读及 2-UAV live preflight 均未运行；R1–R4 安全语义缺口也未因本次环境切换而
消失。因此 manifest 保持 blocked，未创建 runroot，未更新正式项目状态。

## 9. Sol R1–R4 最小返工实现（仅静态与纯函数 probe）

依据 `state/sol_approval.md`，本节只修改 multi 的 collector、runner、preflight、静态
合同和 source hash；未改 world、环境尺寸、冻结单机参数、`project_state.md` 或
`state/SESSION_HANDOFF.md`，未启动 ROS、Gazebo、live preflight、smoke 或长跑。

### R1：接触严重度合同

`two_uav_collector.py` 现在将涉及 UAV 的 Gazebo contact 分类为 `ground`、`obstacle`、
`inter_uav`。地面接触只记录；障碍或机间接触仅在合力 >= 8 N 或同一连续接触持续
>= 0.25 s 时写 `severe_contact:<category>` 的 append-only abort。间断接触会重新计时。
阈值和动作固定在 `config/2uav_static.yaml` 的 `safety_contract.contact`。

### R2：逐机完成与独立指标口径

- completion 改为订阅 `/rosout`，仅当对应 `/exploration_node_1/2` 发出冻结 RACER FSM
  的 `finish exploration.` 日志时，逐机记录 `observed: true`；
- fleet coverage 明确为每 0.25 m observed occupancy voxel 在 planner box 体积中的比例；
  分母由 `[-24.5,-24.5,1.15]` 至 `[24.5,24.5,2.7]` 固定计算；
- overlap 改为 `intersection / min(|UAV0|, |UAV1|)`，而 map consistency 保留
  `intersection / union` Jaccard，二者不再复用；
- ACK timeout 政策固定为 fail-closed：即便之后收到 ACK，也保留 timeout 证据并触发
  `corrupted_telemetry:<uav>:ack_timeout` abort。

这些定义同时写入 manifest 的 `metric_contract` 与 config 的 `safety_contract.metrics`。

### R3：持续运行期 watchdog

collector 每 2 秒检查：启动宽限 20 s 后的 odometry/cloud/frontier/trajectory/health
freshness（命令发出后还检查 pos_cmd/ACK）、ROS master 中逐 topic publisher owner 的
缺失或漂移、每个预期 TF child 是否为唯一 `world` parent，以及已出现节点的死亡。任一
条件失败均写 append-only abort；metrics 同时记录 topic owners、TF parent 与 stale
channels，供后续 live preflight 审核。

### R4：不可变批准包

新增 `config/2uav_approval_contract.yaml`。manifest 状态永久保持
`blocked_pending_verified_launch_and_preflight`，不再作为批准迁移载体。runner 仅接受
Sol 后续单独创建的 `state/2uav_approval.yaml`，该文件必须含 stage、allowed_actions、
`approved: true`、当前 manifest SHA-256 和当前 source hash manifest SHA-256。缺失、
malformed、stage/action 不匹配或任一 hash drift 均 fail-closed。runroot 只复制已验证的
独立 approval package，避免修改 manifest 导致签署死锁。

### 返工验证与 hash

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio_multi_pycache python3 -m py_compile \
  scripts/two_uav_collector.py scripts/two_uav_runner.py scripts/two_uav_preflight.py
PASS

python3 scripts/two_uav_collector.py --self-test
PASS: normal ground contact does not abort; obstacle/inter-UAV threshold contact aborts;
      coverage voxel denominator and distinct overlap/Jaccard formulas checked

python3 scripts/two_uav_runner.py --self-test
PASS: blocked/missing package rejected; preflight package accepted; smoke package accepted;
      source-hash drift rejected

python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml
python3 scripts/two_uav_runner.py launch --manifest experiments/manifests/2uav_smoke.yaml
both exit 2 before runroot/process creation: missing immutable state/2uav_approval.yaml

sha256sum -c config/2uav_source_hashes.sha256
12/12 OK

python3 scripts/two_uav_preflight.py --mode static ...
PASS: 52 checks

git diff --check
PASS
```

最终关键 SHA-256：`config/2uav_source_hashes.sha256`
`6b72c7c8d0f722e878111154c95771d28ea9698d09261135c280f075b96dc663`；
`config/2uav_static.yaml` `aa2f508c73aa78511d89d15bc3ee9e48ad8b9a90a2470af729c585eae77ea4aa`；
`config/2uav_approval_contract.yaml`
`f437c64f136ea080936eae3a4c787c40343fb41ce4ea99d3e219035d2099d41e`；
`scripts/two_uav_collector.py`
`0f85366ef9a659c7eab45353069611e316956c06490cf969618b9cb4f1e49ace`；
`scripts/two_uav_runner.py`
`22fbde5f43468376ee0003e7140021f30dde3b7e11428b389f7c97b2054b998d`；
`scripts/two_uav_preflight.py`
`fa4bf4902cb52b4eed41377b682583b516fb38f1d4ab9b36b6cee52e75a32cf3`；
manifest `ec5ab812abb7ba4dac831d4a7e27329f0c093167df540ff2e04b2b0906916e91`。

残余风险：上述为实现和纯函数/静态证据，尚不能代替真实 ROS graph、message type、
`/rosout` FINISH、contact wrench、TF、owner/freshness 与 abort 运行证据。首次 Sol
复审仍应只决定是否可创建独立 preflight approval package，不自动批准 smoke。

## 10. 审核后最小安全返工

针对 Sol 审核发现的 watchdog、晚到 abort、coverage 缺失和多次授权问题，作如下最小
修正；未改 world、地图边界、冻结单机参数、`project_state.md` 或
`state/SESSION_HANDOFF.md`，未运行 ROS/Gazebo/live preflight/smoke。

- preflight 与 launch 都在一次性静态/live 参数检查后执行 24 s watchdog soak（大于
  20 s 启动宽限），读取 UAV0/UAV1/fleet 的 JSONL 证据；`abort.request`、不完整
  telemetry、缺失 owner/TF/coverage 均阻断启动或 preflight 成功。
- collector 将 occupancy 纳入逐机 freshness，显式输出逐机 coverage
  `available/observed_voxels/denominator_voxels/ratio`；启动宽限后缺失 occupancy abort。
  RACER FINISH 后不再把停止的 frontier/trajectory/pos_cmd/ACK 误认为 freshness 故障，
  但仍持续要求 odometry/cloud/health/occupancy。
- TF 记录每个预期 child 的最后更新时间，缺失或超过 5 s 停更均 abort；ROS master
  topic-owner 查询异常改为 fail-closed abort，不能静默跳过。
- crash 在 fleet report 构造前进入 abort 原因；runner 停机后等待最终 metrics，并检查
  abort 文件、fleet abort reasons、逐机 crash/telemetry/coverage，不能再仅因三个文件
  存在而返回成功。
- approval package 增加 `issued_by: sol` 与 `max_uses: 1`，runner 对 package bytes 计算
  digest，并在 `results/approval-consumption/` 用独占创建 receipt；同一 package 的第二次
  preflight/launch 请求 fail-closed。manifest 仍保持 blocked，不发生 hash 死锁。

验证（均为编译、纯函数或静态 gate；未创建 runroot）：

```text
py_compile collector/runner/preflight: PASS
two_uav_collector.py --self-test: PASS
  ground contact non-severe; obstacle/inter-UAV threshold severe;
  missing coverage is explicit; FINISH-aware freshness is checked
two_uav_runner.py --self-test: PASS
  preflight/smoke approval, hash drift, multi-use approval and final-metric safety checked
sha256sum -c config/2uav_source_hashes.sha256: 12/12 OK
two_uav_preflight.py --mode static: PASS (53 checks)
runner preflight/launch without approval package: exit 2 before runroot/process creation
git diff --check: PASS
```

替换前第 9 节中记录的 source-hash-manifest SHA 已失效；本节为唯一有效 hash 证据：

- `config/2uav_source_hashes.sha256`:
  `5366b6f4ccd0e99a802b2e898eba234b5087fd94fc37760ea3e0e226fcc8d3ba`;
- `config/2uav_static.yaml`:
  `fa3be02954ea86280c19c8b41c1ca194e7d565351857051e9c0f8536e0d7e8d6`;
- `config/2uav_approval_contract.yaml`:
  `00c62de7bc1f10891924c609e900f7361906a8275106af9a84bfeb7d11122a61`;
- `scripts/two_uav_preflight.py`:
  `6bad51059c2dd26a7d2b10b81401b69548df5fef5254ee959f7429f1e25e609c`;
- `scripts/two_uav_collector.py`:
  `37ec70c9c7ef94a481c9cd903939016c859892d661fc13ed147ad3cac80ee937`;
- `scripts/two_uav_runner.py`:
  `5ef684109fe98a527ed52cf7664300df335e86d687fb2a3c645dea72da26b76a`;
- manifest: `e366f943180cb1471742ab2a84e685d75e64442fd00c8bf75e14a00ee618a0f2`.

残余风险仍为运行时兼容性：真实 ROS message/topic owner、TF 更新频率、FINISH rosout、
  contact wrench、occupancy 初始发布和 abort 停机路径必须由一次受批准的 live preflight
  验证；本返工不自动批准该 preflight 或 smoke。

## 11. Sol 复审后的最小安全返工（无实验）

本节仅修复 Sol 最新复审指出的 preflight 安全语义；未修改 world、环境尺寸、冻结单机
参数、`project_state.md` 或 `state/SESSION_HANDOFF.md`，未执行 ROS、Gazebo、live
preflight、smoke 或长跑，也未创建 runroot。

- `two_uav_collector.py`：RACER 在 `WAIT_TRIGGER` 阶段不发布逐机
  `/planning/bspline_N`。因此未完成的 UAV 始终要求 odometry/cloud/frontier/health/
  occupancy freshness，但仅在首次 `PositionCommand` 出现后才要求 trajectory、pos_cmd
  与 ACK；触发后的执行期约束不被放宽。
- ACK recovered 判定改为使用合同的
  `safety_contract.telemetry.command_ack_timeout_s`，不再硬编码 1.0 s。
- `two_uav_runner.py`：preflight 不再在停栈前决定成功退出码。它停止 active stack 后等待
  三份最终 metrics，检查 append-only abort 与最终安全语义，并将结果写入
  `live_preflight.json` 后才返回。launch 的 `live_preflight.json` 也显式追加 24 s
  watchdog soak 结果。
- watchdog evidence 现在要求完整且精确的逐机 topic-owner 集合、两个预期 TF child
  (`uav0/base_link`、`uav1/base_link`) 及数值 timestamp；空或部分结构 fail-closed。

验证（仅编译、纯函数和静态 gate）：

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio_multi_pycache python3 -m py_compile \
  scripts/two_uav_collector.py scripts/two_uav_runner.py scripts/two_uav_preflight.py
PASS

python3 scripts/two_uav_collector.py --self-test
PASS: WAIT_TRIGGER 不要求 trajectory；命令出现后 trajectory/pos_cmd/ACK 缺失被拒绝

python3 scripts/two_uav_runner.py --self-test
PASS: malformed TF evidence fail-closed，完整 owner/TF/coverage evidence 通过

sha256sum -c config/2uav_source_hashes.sha256
12/12 OK

python3 scripts/two_uav_preflight.py --mode static \
  --manifest experiments/manifests/2uav_smoke.yaml
PASS: 53 checks

git diff --check
PASS
```

本节唯一有效 hash：

- `config/2uav_source_hashes.sha256`:
  `3e87951cbd84b263a7f5cf4ff5f9c0e5b0311213a287df7b125c390bdd8fd8b2`；
- `scripts/two_uav_collector.py`:
  `0983dd5b26a6b9c3ae8095e57a7587d870866319c270b8cc5e41d6729c249362`；
- `scripts/two_uav_runner.py`:
  `71414ef9bcd73cc33de65686215a28eef6861b65c96a6e9a7041043b000bd13a`；
- manifest 保持未改动：
  `e366f943180cb1471742ab2a84e685d75e64442fd00c8bf75e14a00ee618a0f2`。

残余风险：本次仅证明静态/纯函数语义。真实 ROS graph 中的 owner/TF 更新、occupancy
首次发布、FINISH rosout、collector 收到 SIGTERM 后的 metrics 落盘，以及 preflight
停栈路径仍须由 Sol 单独批准的一次 manifest 白名单 live preflight 验证。工作树中既有
正式状态文件 diff 未由本节修改，仍须在 Sol 收尾时分离和审计。

## 12. Sol owner-cardinality 返工（无实验）

针对 Sol 复审指出“初始双 publisher 可绕过 owner drift 检查”的问题，只修改
`two_uav_collector.py`、`two_uav_runner.py` 与 source hash 清单；未修改 world、冻结单机
参数、manifest、`project_state.md` 或 `state/SESSION_HANDOFF.md`，未运行 ROS、Gazebo、
live preflight、smoke 或长跑，也未创建 runroot。

- collector 对每个合同 topic 的 ROS master publisher 集合要求恰好一个非空节点；缺失仍为
  `corrupted_telemetry:topic_owner_missing`，两个或更多 publisher 立即写
  `namespace_or_tf_cross_talk:topic_owner_cardinality:<topic>` append-only abort，不能以首次
  观测值为基线而静默接受。
- runner 的 watchdog evidence 对 JSON 中每个 topic owner 要求恰好一个非空字符串；多
  owner、空 owner 或类型损坏均在 trigger 前 fail-closed。
- collector 自检覆盖单 owner、空 owner、双 owner；runner 自检覆盖完整 evidence 通过、双
  owner 拒绝和空 TF evidence 拒绝。

验证（仅编译、纯函数和静态 gate）：

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio_multi_owner_audit_pycache python3 -m py_compile \
  scripts/two_uav_collector.py scripts/two_uav_runner.py scripts/two_uav_preflight.py
PASS

python3 scripts/two_uav_collector.py --self-test
PASS

python3 scripts/two_uav_runner.py --self-test
PASS: complete owner evidence accepted; duplicate owner and empty TF evidence rejected

sha256sum -c config/2uav_source_hashes.sha256
12/12 OK

python3 scripts/two_uav_preflight.py --mode static \
  --manifest experiments/manifests/2uav_smoke.yaml
PASS: 53 checks

git diff --check
PASS
```

本节唯一有效 hash：

- `config/2uav_source_hashes.sha256`:
  `9dbc2b5ac181f86c786ff7b5d549daf101902abdf911440a400cb53092d209af`；
- `scripts/two_uav_collector.py`:
  `608da4789baac33bfa31cc4affb39daf0433e1bdd15b8c0e1cc5b7d6793ca66d`；
- `scripts/two_uav_runner.py`:
  `e86fc03b708ac61d0b1716de13cd7cac3195400201181d0f5c4ee68cf48be9ca`；
- manifest 不变：
  `e366f943180cb1471742ab2a84e685d75e64442fd00c8bf75e14a00ee618a0f2`。

残余风险：上述只证明 owner-cardinality 的静态/纯函数语义。真实 ROS master 的 publisher
列表、TF/occupancy 更新、FINISH rosout、SIGTERM 后 metrics 落盘与 abort 停机路径仍须由
Sol 单独批准的一次 manifest 白名单 live preflight 验证。

## 13. Runroot ROS 日志隔离最小返工（无实验）

按 `state/sol_plan.md` 第 8 节，仅修改 `scripts/two_uav_runner.py`、
`config/2uav_source_hashes.sha256` 与本记录。未修改 manifest、world、launch、冻结单机
参数、approval package、消费 receipt、既有 runroot、`project_state.md` 或
`state/SESSION_HANDOFF.md`；未启动 ROS、Gazebo、live preflight、smoke 或长跑。

- 新增纯函数 `runroot_ros_environment()`，固定返回本轮 runroot 下
  `logs/ros`（`ROS_LOG_DIR`）和 `logs/ros-home`（`ROS_HOME`）。
- `make_runroot()` 在任何子进程启动前创建这两个目录，并写入
  `runtime_environment.json`；该文件是本轮实际 ROS 环境目录的机器可读快照。
- `process_specs(runroot)` 在三个 ROS setup 脚本之后、各进程 `exec` 之前显式导出
  `ROS_LOG_DIR` 与 `ROS_HOME`。Gazebo、GT mapper、bridges、RACER、collector 都从相同
  `env_prefix` 继承该导出；命令串不含 `~/.ros`。
- `start_stack()` 在启动前把实际 `argv` 以 `process_specs.json` 追加写入新 runroot，和
  `runtime_environment.json` 对照即可审计五个子进程的导出路径。
- runner self-test 新增负向隔离 probe：分别建立两个临时 runroot，断言其 ROS log/home
  路径不同且目录存在；再断言五个 process spec 都包含第一个 runroot 的两个 export，且
  不含 `~/.ros`。这是纯函数/临时目录测试，不会启动子进程。

验证（均为编译、纯函数或静态 gate）：

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio_multi_pycache python3 -m py_compile \
  scripts/two_uav_runner.py
PASS

python3 scripts/two_uav_runner.py --self-test
PASS: two distinct runroots have distinct ROS_LOG_DIR/ROS_HOME; all five child
      specs export the runroot-local paths; no spec contains ~/.ros

sha256sum -c config/2uav_source_hashes.sha256
12/12 OK

python3 scripts/two_uav_preflight.py --mode static \
  --config config/2uav_static.yaml \
  --manifest experiments/manifests/2uav_smoke.yaml
PASS: 53/53 checks

git diff --check
PASS
```

本节唯一有效 hash：

- `config/2uav_source_hashes.sha256`:
  `9981436ce27c013065ae63fcce71dd814c7acee765b1b60e1c675b0e3ba7e098`；
- `scripts/two_uav_runner.py`:
  `9f922fd3b5b737d390138423e379b9bcf90d0dfa20e6d3da2a5510d66ba5d61a`；
- manifest 未修改：
  `e366f943180cb1471742ab2a84e685d75e64442fd00c8bf75e14a00ee618a0f2`。

残余风险：此返工消除了 runner 对共享 `~/.ros` 的默认回落，并提供静态可审计证据；它
不解决执行沙箱对 `netifaces.interfaces()` 的权限拒绝。新的、一次性 `stage: preflight`
approval package 只能由 Sol 在复审新 source-hash manifest 后签发；实际 preflight 仍须在
获得 ROS 网络接口枚举权限的受批准执行环境中运行。旧 package 已消费，smoke 继续禁止。

## 14. 全部 runner ROS 子进程环境继承返工（无实验）

按 `state/sol_plan.md` 第 9 节，仅修改 `scripts/two_uav_runner.py`、
`config/2uav_source_hashes.sha256` 与本记录。未修改 manifest、world、launch、冻结参数、
approval package、消费 receipt、既有 runroot、`project_state.md` 或
`state/SESSION_HANDOFF.md`；未启动 ROS、Gazebo、live preflight、smoke 或长跑。

- 新增 `ros_subprocess_environment(runroot)`，从调用环境复制非 ROS 状态变量后，强制覆盖
  `ROS_LOG_DIR`/`ROS_HOME` 为该 runroot 的 `logs/ros`/`logs/ros-home`；外部调用者即使传入
  共享路径也不能覆盖这两个值。
- 长生命周期 Gazebo、GT mapper、bridges、RACER、collector 的 `Popen` 明确使用
  `env=ros_subprocess_environment(runroot)`；保留命令串中的 export，使 `process_specs.json`
  仍可审计。
- `wait_topic()`、`sim_time_s()` 与 smoke trigger 全部改为通过纯函数
  `ros_command_spec()` 获得 `argv + env`，并以显式 `env=` 启动 `rostopic` 子进程。
- `live_checks()` 不修改其源码：preflight 与 smoke 的调用均包在
  `runroot_ros_environment_scope()` 中，因此其内部 `subprocess.run()` 继承当前 runroot
  的两个 ROS 路径；该作用域退出后恢复调用者原有环境，避免跨 runroot 污染。
- 新增 `active_ros_environment()`；`load_active()` 从 `ACTIVE` 恢复后重新从保存的 runroot
  构造同一子进程环境，而不是依赖新 runner 进程的默认 `~/.ros`。新 ACTIVE 记录同时包含
  可审计的两个 ROS 路径快照。
- self-test 现覆盖两个 runroot 的路径不共享、外部伪造 ROS 路径被覆盖、ACTIVE 恢复路径、
  三类短生命周期 ROS CLI（list/clock/trigger）的 `argv + env` 规格，以及 live-check
  作用域进入/退出的环境恢复。所有 probe 只操作临时目录和进程内环境，不启动子进程。

验证（仅编译、纯函数和静态 gate）：

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio_multi_pycache python3 -m py_compile \
  scripts/two_uav_runner.py
PASS

python3 scripts/two_uav_runner.py --self-test
PASS: Popen and all runner ROS CLI specs bind runroot-local ROS_LOG_DIR/ROS_HOME;
      two runroots remain isolated; ACTIVE recovery reconstructs the original paths

sha256sum -c config/2uav_source_hashes.sha256
12/12 OK

python3 scripts/two_uav_preflight.py --mode static \
  --config config/2uav_static.yaml \
  --manifest experiments/manifests/2uav_smoke.yaml
PASS: 53/53 checks

git diff --check
PASS
```

本节唯一有效 hash：

- `config/2uav_source_hashes.sha256`:
  `05fada5472ec02436c6d12c0fef6e4fd766a57911a86ca8abb09bffc6ab077e4`；
- `scripts/two_uav_runner.py`:
  `d6313ef2c25b8fe39d9431a322de064de3bc8734c084e11b791299012c248a64`；
- manifest 未修改：
  `e366f943180cb1471742ab2a84e685d75e64442fd00c8bf75e14a00ee618a0f2`；
- 已消费 approval package 未修改：
  `57a76ff0e3d1829684cac38b8a725e0d9b36df006be2f5e37cbd58fafd65b60f`。

残余风险：本返工证明 runner 内全部 ROS 子进程的环境绑定与环境恢复语义，但不证明真实
ROS graph、Gazebo、`netifaces.interfaces()` 权限、TF/topic/parameter readback 或 SIGTERM
后的最终 metrics。新的单次 preflight package 仍必须由 Sol 独立复审新的 source hash 后
签发；smoke 继续禁止。

## 15. 第 10 节运行期 wiring 与检测返工（无实验）

按 `state/sol_plan.md` 第 10 节，仅修改 `scripts/two_uav_runner.py`、
`scripts/two_uav_preflight.py`、`scripts/two_uav_gt_mapper.py`、
`scripts/two_uav_collector.py`、`config/2uav_source_hashes.sha256` 与本记录。未修改
manifest、launch、world、`config/2uav_static.yaml`、workspace、approval package、receipt、
既有 runroot、`project_state.md` 或 `state/SESSION_HANDOFF.md`；未启动 ROS、Gazebo、
preflight、smoke 或长跑。

- runner 不再依赖两个 catkin `setup.bash` 的 source 顺序：显式、稳定地合成两个 workspace
  的 `ROS_PACKAGE_PATH`、`CMAKE_PREFIX_PATH`、Python、library、bin 与 pkg-config 路径，并在
  每个 ROS 子进程环境中保留 runroot-local `ROS_LOG_DIR`/`ROS_HOME`。启动栈前写入可审计的
  `workspace_environment_probe.json`，三项 probe（`swarm_lio`、`exploration_manager`、
  `quadrotor_msgs.msg`）任一失败即 fail-closed。
- runner readiness 改为 `rostopic echo -n 1` 的真实 payload gate，并在每个阶段检查进程仍
  存活：clock、各机 raw scan、MAVROS odom、registered cloud、registered odom、frontier
  都必须实际有消息；单纯 topic 注册不能通过。
- GT mapper 为每架机发布唯一、带同步 scan 时间戳的动态 `world -> uavN/base_link` TF；其
  诊断记录 scan/odom 输入、同步 pair、空 scan、空过滤结果及成功输出数量。纯函数测试锁定
  parent、child、timestamp 与 transform payload。
- live preflight 新增真实 payload 检查，并以 exact-set TF 合同拒绝空 TF、缺 child、错误
  parent 或多 parent；不会将“无交叉”误判为成功。
- collector 将活动期 liveness 和正常 teardown 分离：超过启动宽限后 expected node 从未出现
  或已出现后消失都会 append-only `process_death`；finalize 使用最后一个活动期快照，不会因
  runner 的有序 SIGTERM 新增伪 process death。纯函数测试覆盖 never-seen、lost-after-seen 与
  teardown 三种情形；freshness、TF、topic-owner、ACK 合同未放宽。

验证（均为离线、编译、纯函数或静态 gate）：

```text
python3 -m py_compile scripts/two_uav_runner.py scripts/two_uav_preflight.py \
  scripts/two_uav_gt_mapper.py scripts/two_uav_collector.py
PASS

python3 scripts/two_uav_runner.py --self-test
python3 scripts/two_uav_preflight.py --self-test
python3 scripts/two_uav_gt_mapper.py --self-test
python3 scripts/two_uav_collector.py --self-test
PASS (all four)

offline composed-workspace probe with a temporary runroot-local ROS_HOME:
rospack find swarm_lio
  /home/houslakers/swarm_ws/src/Swarm-LIO2/swarm_lio
rospack find exploration_manager
  /home/houslakers/racer_ws/src/RACER/swarm_exploration/exploration_manager
python3 -c 'import quadrotor_msgs.msg'
  PASS

source hash verification: 12/12
static preflight: PASS 53/53
git diff --check: PASS
```

本节有效 hash：

- `config/2uav_source_hashes.sha256`:
  `21bd9d5838316db6999654f98d6216d86a5f67d943ab669dcceeca9300ba568c`；
- `scripts/two_uav_runner.py`:
  `832818538064049bd22106c3149924ac5bd83898ea74684af27635db72115025`；
- `scripts/two_uav_preflight.py`:
  `9bdc77d1bc0f08e447e02f1b10456c31e021af096e15cd2484c19f706a0b6af7`；
- `scripts/two_uav_gt_mapper.py`:
  `c87f4d61cfc5b990f4798681023e18b56e2aceed9fd4a74cc266d00ecd261424`；
- `scripts/two_uav_collector.py`:
  `18545c3b55d1edce26cbab387875220d2394320ccc0d8b650569d0f059c55936`；
- frozen manifest unchanged:
  `e366f943180cb1471742ab2a84e685d75e64442fd00c8bf75e14a00ee618a0f2`。

残余风险：本次只证明 deterministic env、fail-closed gate 与纯函数语义。需要 Sol 复审
source hashes、diff、manifest 与此记录后，才可签发新的、一次性 preflight package；该包不得
复用此前已消费的 package。真实 ROS graph 的 payload、GT TF、owner、collector 活动期
liveness、SIGTERM teardown 和 sandbox `netifaces` 权限仍只能由获批的 manifest 白名单
preflight 验证；smoke 继续禁止。

## 16. 第 11 节 readiness 监视最小返工（无实验）

按 `state/sol_plan.md` 第 11 节，仅修改 `scripts/two_uav_runner.py`、
`scripts/two_uav_preflight.py`、`scripts/two_uav_gt_mapper.py`、
`scripts/two_uav_collector.py`、`config/2uav_source_hashes.sha256` 与本记录。未修改
manifest、launch、world、`config/2uav_static.yaml`、workspace、approval package、receipt、
既有 runroot、`project_state.md`、`state/current_summary.md` 或
`state/SESSION_HANDOFF.md`；未启动 ROS、Gazebo、preflight、smoke 或长跑。

- runner 新增纯函数 `readiness_state()` / `process_exit_reason()`：每个 0.25 秒 readiness
  短轮询都检查全部已启动 Popen，任一已退出立即生成唯一
  `readiness process exited: <name> code=<code>`，不会等到 topic 的 120/180 秒总超时。
  每次 `rostopic echo` probe 本身最多 3 秒，probe 返回后立即重新检查所有 Popen。
- GT mapper 的 raw scan、MAVROS odom、registered cloud/odom gate 和 RACER frontier gate
  均改用这一共同 gate，因此会持续监视先前的 Gazebo、GT mapper 与 bridges。bridges 另有
  独立 gate，必须同时看见 `/px4_bridge_1`、`/px4_bridge_2`；后续 frontier 等待也持续要求
  这两个 node 存在。ACK owner 与 timeout 合同没有放宽。
- runner self-test 用 fake Popen 覆盖 payload 成功、零 payload、当前进程退出、先前进程退出
  与缺失一个 bridge node；所有 probe 为纯函数，不启动 ROS。
- GT mapper self-test 现同时构造 UAV0/UAV1 的 transform，断言两个 child 唯一、parent 均为
  `world`、timestamp 一致，以及各自 translation/rotation 未串线。
- preflight 将 payload 结果抽为纯函数 `payload_observed()`；测试 echo 成功但 stdout 为空时
  仍 fail-closed，并增加空 TF 与同 child 双 parent 的拒绝测试。
- collector 的 `liveness_state()` 先形成 `updated_seen`，再导出 `never_seen` / `lost_after_seen`；
  首次已 live 的 node 不再被错误记录为 never-seen。自测覆盖首次 live、活动期 missing 和
  teardown 不新增 process death。

验证（均为离线、编译、纯函数或静态 gate）：

```text
python3 -m py_compile scripts/two_uav_runner.py scripts/two_uav_preflight.py \
  scripts/two_uav_gt_mapper.py scripts/two_uav_collector.py
PASS

python3 scripts/two_uav_runner.py --self-test
python3 scripts/two_uav_preflight.py --self-test
python3 scripts/two_uav_gt_mapper.py --self-test
python3 scripts/two_uav_collector.py --self-test
PASS (all four)

offline composed-workspace probe under a temporary runroot-local ROS_HOME:
rospack find swarm_lio
  /home/houslakers/swarm_ws/src/Swarm-LIO2/swarm_lio
rospack find exploration_manager
  /home/houslakers/racer_ws/src/RACER/swarm_exploration/exploration_manager
python3 -c 'import quadrotor_msgs.msg'
  PASS

sha256sum -c config/2uav_source_hashes.sha256
12/12 OK

static preflight: PASS 53/53
git diff --check: PASS
```

本节有效 hash：

- `config/2uav_source_hashes.sha256`:
  `c7ba1e6d272b5679661fb5a172b35610daf42fddca58ad302844a0801188c361`；
- `scripts/two_uav_runner.py`:
  `498de379632283ab859b94867554ee514df58c16b4a9d97a186bcc194635d819`；
- `scripts/two_uav_preflight.py`:
  `ef1718effcb7b257cb2d55c84661e9ec812833df2a180ea0c67ffe56ed395b0f`；
- `scripts/two_uav_gt_mapper.py`:
  `19adb1f72cf95c3c98602088e1d949bcac646de7db45677d21fc33e3acd3ad12`；
- `scripts/two_uav_collector.py`:
  `84fea9ad9edc8510b7925609483da5d5ce4de5ed84ffd4335a7e4e6fb144093f`；
- frozen manifest unchanged:
  `e366f943180cb1471742ab2a84e685d75e64442fd00c8bf75e14a00ee618a0f2`。

残余风险：静态测试不能证明真实 roslaunch 的子节点在 3 秒 CLI probe 内退出的调度细节，也
不能证明 Gazebo scan、MAVROS odom、GT TF、bridge node、frontier、owner/ACK 或 collector
teardown 在真实 graph 中全部满足合同。必须由 Sol 复审本 diff 与 hashes 后才可签发新的单次
preflight package；此前已消费 package 不得复用，smoke 继续禁止。

## 17. 第 12 节 runner gate 终态与时序最小返工（无实验）

按 `state/sol_plan.md` 第 12 节，仅修改 `scripts/two_uav_runner.py`、
`config/2uav_source_hashes.sha256` 与本记录。未修改其余源码、manifest、launch、world、静态
参数、workspace、approval package、receipt、既有 runroot、`project_state.md`、
`state/current_summary.md` 或 `state/SESSION_HANDOFF.md`；未启动 ROS、Gazebo、preflight、
smoke 或长跑。

- `wait_readiness()` 的每次 sample 现严格按 payload probe、**probe 后** node probe、
  `readiness_state()` 顺序执行；因此 bridge 在 payload probe 期间消失不能使用旧快照通过。
  每次判定仍在最后检查全部 Popen，退出优先给出包含 name/exit code 的唯一错误。
- deadline 后执行同一 `sample()`，不再硬编码 `payload=False`；最终 sample 若成功即通过，若
  process 已退出仍优先 process-exit，其他未就绪情况固定为
  `readiness timeout: <label>: <detail>`。
- 为 gate 增加 `node_probe`、`monotonic`、`sleep` 注入点，仅供纯函数/自测使用。runner
  self-test 现在直接调用 `wait_readiness()`，覆盖：payload 成功、零 payload timeout、当前
  Popen 退出、此前 Popen 退出、bridge 缺一个 node timeout，以及 payload probe 将完整 bridge
  集合变成缺失集合时 frontier gate 必须 timeout。自测不启动 ROS。

验证（均为离线、编译、纯函数或静态 gate）：

```text
python3 -m py_compile scripts/two_uav_runner.py scripts/two_uav_preflight.py \
  scripts/two_uav_gt_mapper.py scripts/two_uav_collector.py
PASS

python3 scripts/two_uav_runner.py --self-test
python3 scripts/two_uav_preflight.py --self-test
python3 scripts/two_uav_gt_mapper.py --self-test
python3 scripts/two_uav_collector.py --self-test
PASS (all four; runner directly covers gate timeout/exit/node-race paths)

offline composed-workspace probe under a temporary runroot-local ROS_HOME:
rospack find swarm_lio
  /home/houslakers/swarm_ws/src/Swarm-LIO2/swarm_lio
rospack find exploration_manager
  /home/houslakers/racer_ws/src/RACER/swarm_exploration/exploration_manager
python3 -c 'import quadrotor_msgs.msg'
  PASS

sha256sum -c config/2uav_source_hashes.sha256
12/12 OK

static preflight: PASS 53/53
git diff --check: PASS
```

本节有效 hash：

- `config/2uav_source_hashes.sha256`:
  `91c91c0cdb67b5603cc95ea3cda942440ffec8cd676c3dbcd6ed646add9d0d4e`；
- `scripts/two_uav_runner.py`:
  `06f2ae31c5514cbb2efeae3be266f1d77d188a1c695380183a8d532501a308de`；
- frozen manifest unchanged:
  `e366f943180cb1471742ab2a84e685d75e64442fd00c8bf75e14a00ee618a0f2`。

残余风险：本次只证明 gate 的纯函数与离线 subprocess 环境；真实 ROS CLI 每轮最多 3 秒的
probe 调度、Gazebo/MAVROS/GT TF/bridge/frontier 的真实数据流、collector owner/ACK 与正常
teardown 仍需新的、经 Sol 独立审核的一次性 manifest 白名单 preflight 验证。旧 approval
package 已消费，不得复用；smoke 继续禁止。

## 18. 第 13 节 workspace probe 前缀统一（无实验）

按 `state/sol_plan.md` 第 13 节，仅修改 `scripts/two_uav_runner.py`、
`config/2uav_source_hashes.sha256` 与本记录。未修改其余源码、manifest、launch、world、静态
参数、workspace、approval package、receipt、既有 runroot、`project_state.md`、
`state/current_summary.md` 或 `state/SESSION_HANDOFF.md`；未启动 ROS、Gazebo、preflight、
smoke 或长跑。

- 新增唯一 `ros_runtime_prefix(runroot)`：先 source Noetic，随后导出
  `workspace_environment_exports(runroot)` 的组合 package/prefix/Python/library 路径以及
  runroot-local `ROS_LOG_DIR`/`ROS_HOME`。Noetic 对路径变量的重置因此不会丢失 swarm_ws 或
  racer_ws。
- `process_specs()` 和新的 `workspace_probe_specs()` 共同使用该 helper。
  `verify_workspace_environment()` 逐项执行后者生成的实际 `argv + env`，并将 command、
  returncode、stdout、stderr 写入未来 runroot 的 `workspace_environment_probe.json`；任一
  失败仍照旧 fail-closed。
- runner self-test 检查 Noetic source 位于全部关键 export 前，五个 process spec 和三项
  probe spec 共用完全相同 prefix，且 probe 仍绑定各 runroot 专属 ROS log/home、不含
  `~/.ros`。

验证（均为离线、编译、纯函数或静态 gate）：

```text
python3 -m py_compile scripts/two_uav_runner.py scripts/two_uav_preflight.py \
  scripts/two_uav_gt_mapper.py scripts/two_uav_collector.py
PASS

python3 scripts/two_uav_runner.py --self-test
python3 scripts/two_uav_preflight.py --self-test
python3 scripts/two_uav_gt_mapper.py --self-test
python3 scripts/two_uav_collector.py --self-test
PASS (all four)

runner.workspace_probe_specs(temp_runroot) generated argv+env execution:
swarm_lio: returncode=0
  /home/houslakers/swarm_ws/src/Swarm-LIO2/swarm_lio
exploration_manager: returncode=0
  /home/houslakers/racer_ws/src/RACER/swarm_exploration/exploration_manager
quadrotor_msgs: returncode=0
  import succeeded (stdout/stderr empty)

sha256sum -c config/2uav_source_hashes.sha256
12/12 OK

static preflight: PASS 53/53
git diff --check: PASS
```

本节有效 hash：

- `config/2uav_source_hashes.sha256`:
  `f7939703b6fe232aeea7b7343e6538ae5baa2b32ad35d4bd4305fe5ce8f50c70`；
- `scripts/two_uav_runner.py`:
  `60bd1a8aa9455139cc4663b53408cc07b64777319a7b4f83b74417e9ebe4bd50`；
- frozen manifest unchanged:
  `e366f943180cb1471742ab2a84e685d75e64442fd00c8bf75e14a00ee618a0f2`。

残余风险：该修复直接消除了第三次 run 在任何 Popen 前发生的 probe prefix 漂移，但不能证明
真实 ROS graph 的 Gazebo、MAVROS、GT TF、bridge、frontier、owner/ACK 或 collector teardown。
旧 package `8b3b7530…a4937` 已消费且未修改；必须由 Sol 复审新的 source-hash manifest 后
签发新的单次 preflight package，smoke 继续禁止。

## 19. 第 14 节 Livox headless 激活合同（环境 baseline 第一阶段，无实验）

按 `state/sol_plan.md` 第 14 节，只做了共享 PX4 iris 模型的一项功能修复：在
`models/iris/iris.sdf.jinja` 的 Livox `sensor type="ray"` 的直接子项中插入
`<always_on>true</always_on>`。未修改 `update_rate=10`、24000 samples、downsample、视场/量程/噪声、
frame、相对 `livox/scan` topic、50x50 world、单机参数、CSV、插件源码或 multi 的
manifest/config/launch/runner。未启动 ROS、Gazebo、preflight 或 smoke；未修改 approval package、receipt、
旧 runroot、`project_state.md`、`state/current_summary.md` 或 `state/SESSION_HANDOFF.md`。

公共环境清单
`/home/houslakers/auto_tune_racer/racer-platform/environment/baselines/racer_outdoor_50x50_v1.yaml`
仍是未发布的 untracked baseline；已增加 `livox_headless_contract`，钉住修复后模板、
mavlink ID 1/2 渲染 SDF、CSV、插件二进制、插件源 commit/dirty-diff 以及 headless
sensor 合同。没有原位修改已发布身份，也没有触碰 `mid360.csv` 或已存在的
livox workspace diff。

离线验证（均不启动 ROS/Gazebo）：

```text
python3 .../jinja_gen.py .../iris.sdf.jinja .../sitl_gazebo-classic \
  --mavlink_id 1 --output-file /tmp/iris-livox-uav0.sdf
python3 .../jinja_gen.py .../iris.sdf.jinja .../sitl_gazebo-classic \
  --mavlink_id 2 --output-file /tmp/iris-livox-uav1.sdf
PASS

gz sdf -k /tmp/iris-livox-uav0.sdf
gz sdf -k /tmp/iris-livox-uav1.sdf
exit=0 for both; host sandbox emitted `error in getifaddrs: Unknown error -1`,
but did not reject either SDF.

XML contract probe (both rendered files): PASS
uav0: laser_livox_0, always_on=true, update_rate=10,
      samples=24000, downsample=1, topic=livox/scan, frame=uav0/laser_livox
uav1: laser_livox_1, always_on=true, update_rate=10,
      samples=24000, downsample=1, topic=livox/scan, frame=uav1/laser_livox

CSV strict parse: PASS
header=[Time/s, Azimuth/deg, Zenith/deg]
row_count=800000; every post-header row has exactly three non-empty finite numbers.

PyYAML public-baseline contract probe: PASS
always_on=true; valid_rows=800000; plugin library identity present.
```

身份 hash：

```text
iris.sdf.jinja:              844f02ce6afa4b4113b1271ebf9bd4b873564d702e65c5808d371ea52dca274c
rendered iris (mavlink ID 1): 4bf880932588c2db7148f7ed94cda66cb80619ecda244813b7b57f62ec884db0
rendered iris (mavlink ID 2): 066bfd3720313ee51fd448d2764edf1a610d622b9ca0379ce123a711896e783f
mid360.csv:                  aa1fc08b6a4400608dbd6ee832b7ea3a9c3c37197e734f60f58fe5abf762269a
liblivox_laser_simulation.so: ad117f9290cc1ef091842023d30af0de89bff14724fc78192250f737442b90b6
livox source commit:          1cce1073633a062b92e30243a4c2920e45551bb5
livox dirty diff:             85dca418fe4eeee2482a100b6af04a14323fcd3990cbba375cc984c269e7df76
public baseline manifest:     654346f749fdf7a5f313fb72688e10a0f83315081851747d122637945f3fd114
PX4 Gazebo submodule HEAD:    f835e077d06eaf09a57d5152fcfb85244b53b77a
racer-platform HEAD:          57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc
multi HEAD:                   41879e8ccea783895965831f75646ac2a6a43ed7
```

已保存的 livox workspace dirty inventory（本次未触碰）：`CMakeLists.txt`、
`include/livox_laser_simulation/livox_ode_multiray_shape.h`、
`src/livox_ode_multiray_shape.cpp`、`src/livox_points_plugin.cpp`、
`urdf/livox_mid360.xacro` 以及 `urdf/livox_mid360 (copy).xacro`。

diff 检查结果：新增 baseline 清单的 no-index `git diff --check` 通过，模型中本次
`always_on` 行无空白问题。但 PX4 Gazebo 子模块在本次之前已含大量未提交的
iris 改动，其中第 661 、664 行存在 trailing whitespace；multi 工作树也早已在
`launch/multi_uav_mavros_sitl.launch` 报多处 trailing whitespace。全工作树 `git diff --check`
因这些不在任务允许范围内的既有改动而失败；未擅自清理或覆盖。

残余风险：本次只证明了 headless 模型合同与离线生成物，还没有直接的
headless raw-scan payload 运行证据。此外，multi 仍指向修改前的 baseline SHA；必须先由 Sol
复审环境改动并明确处置已有 diff-check 失败，然后才可以授权只更新
`experiments/manifests/2uav_smoke.yaml`、`config/2uav_static.yaml` 与 source-hash 引用。旧
approval package `0944b9c0…ef79b` 已消费且不得复用；在此之前不得签发新
preflight package，smoke 继续禁止。

## 20. 第 15 节 baseline identity 重绑与 scoped diff 闭环（无实验）

按 `state/sol_plan.md` 第 15 节，只做了以下机械性变更：

1. PX4 Gazebo 子模块 `models/iris/iris.sdf.jinja` 的 Livox 块两条空白行去除尾随空格；
   `always_on=true` 和任何 XML 值均未变。
2. 公共 `racer_outdoor_50x50_v1` baseline 更新修改后模板与 mavlink ID 1/2 渲染 SDF hash。
3. 只在 `experiments/manifests/2uav_smoke.yaml` 和 `config/2uav_static.yaml` 重绑同一
   baseline manifest SHA；仅更新 `config/2uav_source_hashes.sha256` 中这两个受影响的 hash。

未修改 CSV、CSV reader、插件源码/二进制、world、其他 launch、runner/preflight/
collector/GT mapper、冻结 20 m 水平全向参数、approval package、receipt、旧 runroot或正式状态
文件；未 commit/push；未启动 ROS、Gazebo、preflight 或 smoke。

最终 identity：

```text
iris.sdf.jinja:                 e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225
rendered iris (mavlink ID 1):  e74845b04194dd5421b687c2206fd6fddb03a397932e45a685355a00debdf584
rendered iris (mavlink ID 2):  c2af67e88d901c901671b729b0e7b87e65da017308a3d26d390ed24636a58a42
public baseline manifest:      ce595cafba088955b38c4c9bd1d08f9af254dbfa0bf013481372a75e17980944
config/2uav_static.yaml:       415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e
2uav_smoke.yaml:               75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46
source-hash manifest:          41fbe083ccc5cc7a25093985cd1ddf76cec4e852bf6b92a288a5f94e54a30bb0

mid360.csv:                    aa1fc08b6a4400608dbd6ee832b7ea3a9c3c37197e734f60f58fe5abf762269a
liblivox_laser_simulation.so:  ad117f9290cc1ef091842023d30af0de89bff14724fc78192250f737442b90b6
livox source commit:           1cce1073633a062b92e30243a4c2920e45551bb5
livox dirty diff:              85dca418fe4eeee2482a100b6af04a14323fcd3990cbba375cc984c269e7df76
```

离线验证：

```text
jinja_gen.py (mavlink ID 1, 2) -> /tmp/iris-livox-uav0.sdf,
                                      /tmp/iris-livox-uav1.sdf: PASS
gz sdf -k on both rendered files: exit 0 (host getifaddrs warning only)
XML contract: PASS
  laser_livox_0/1 each has exactly one direct always_on=true;
  update_rate=10, samples=24000, downsample=1, topic=livox/scan,
  frame=uav0/laser_livox and uav1/laser_livox respectively.
CSV strict parse: PASS, 800000/800000 finite three-column records.
Plugin identity: PASS, source commit/dirty-diff/binary match the public baseline.
PyYAML three-layer identity probe: PASS
  baseline == manifest.environment_baseline.manifest_sha256
           == static.environment.baseline_manifest_sha256
  and all model/render/CSV/plugin hashes match their files.

PYTHONPYCACHEPREFIX=/tmp/swarmlio_multi_pycache python3 -m py_compile \
  scripts/two_uav_preflight.py scripts/two_uav_runner.py: PASS
python3 scripts/two_uav_preflight.py --self-test: PASS
sha256sum -c config/2uav_source_hashes.sha256: PASS, 12/12
python3 scripts/two_uav_preflight.py --mode static ...: PASS, 53/53
```

`git diff --check` 结果：本 multi 仓库全量通过；PX4
`models/iris/iris.sdf.jinja` scoped 通过；公共 baseline 的 no-index diff check 通过。PX4
Gazebo 子模块仍有本任务前已存在的其它 dirty diff/空白债务（包括
`launch/multi_uav_mavros_sitl.launch`），未过度清理、未纳入本次修复或 package identity。

残余风险：静态证据已闭合新的共享 baseline identity，但仍无 headless
Gazebo 真实 raw-scan payload 运行证据；只能在 Sol 复审通过后由新建、一次性的
preflight package 验伪。旧 package `0944b9c0…ef79b` 已消费，不得复用；在批准前 smoke 继续禁止。

## 21. 第 16 节 live TF CLI sampler 修复（无实验）

按 `state/sol_plan.md` 第 16 节，只修改 `scripts/two_uav_preflight.py`、
`config/2uav_source_hashes.sha256` 与本记录。未修改 runner、collector、GT mapper、manifest、
static contract、launch、world、公共 baseline、PX4/Livox workspace、CSV、插件、冻结 20 m
水平全向参数、approval package、receipt、旧 runroot 或正式状态文件；未 commit/push；未启动
ROS、Gazebo、preflight 或 smoke。

变更：

- 新增纯函数 `tf_echo_argv()`，固定为
  `rostopic echo -n 10 /tf`。TFMessage 的 `transforms[]` 是必需载荷，故只在该 TF 采样路径
  移除 `--noarr`；仍保留有限采样、5 s timeout 和 timeout 时对 partial stdout 的解析。
- 新增纯函数 `parse_tf_parent_sets(output)`，从完整 rostopic YAML 累积
  `{child: {all_observed_parents}}`；保留完整 frame 名，未过滤错 parent 或多 parent。
- `tf_parent_sets()` 仅负责 CLI 调用与 timeout，再委托纯解析函数；未引用 collector metrics。
- self-test 使用真实 `transforms:` 数组结构 fixture，覆盖双机 `world→uavN/base_link` 成功、
  空输出、缺 child、错 parent、同 child 多 parent，以及 argv 含 `/tf` 且不含 `--noarr`。
  `expected_tf_contract()` exact-set fail-closed 语义未变。
- `topic_has_payload()` 对普通消息的 `--noarr` 保持完全不变。

验证（均为离线或纯函数）：

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio_multi_pycache python3 -m py_compile \
  scripts/two_uav_preflight.py
PASS

python3 scripts/two_uav_preflight.py --self-test
two_uav_preflight self-test: PASS

tf_echo_argv(): ['rostopic', 'echo', '-n', '10', '/tf']
fixture parse: {'uav0/base_link': {'world'}, 'uav1/base_link': {'world'}}
empty/missing/wrong-parent/multi-parent: all fail closed
topic_has_payload --noarr path unchanged

sha256sum -c config/2uav_source_hashes.sha256
PASS: 12/12

python3 scripts/two_uav_preflight.py --mode static ...
PASS: 53/53

git diff --check
PASS
```

本节有效 identity：

```text
scripts/two_uav_preflight.py: afa8b3821b2c8f3e2dfda2f5f65e5d960145ee1bf277d10c220157bde231a567
config/2uav_source_hashes.sha256: 3ef1ce50b80fa3742462acf49f2312e34188673a3b56e824c7e6be16c8a39640
frozen manifest (unchanged): 75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46
static contract (unchanged): 415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e
runner (unchanged): 60bd1a8aa9455139cc4663b53408cc07b64777319a7b4f83b74417e9ebe4bd50
```

残余风险：fixture 证明 sampler 不再系统性丢弃 TFMessage transforms，但真实 ROS CLI
`/tf` 采样、消息频率和 live gate 与 collector 的独立一致性仍必须由一张新的单次 preflight
package 验证。旧 package `1718c1cf…3b10` 已消费且不得复用；修复本身不批准 smoke。

## 22. 第 17 节 frontier channel 分类最小修复（无实验）

按 `state/sol_plan.md` 第 17 节，只修改了 `scripts/two_uav_collector.py`、
`config/2uav_source_hashes.sha256` 与本记录。未修改 RACER/exploration publisher、单机参数、
`config/2uav_static.yaml`、manifest、runner、preflight、GT mapper、launch/world、公共 baseline、
approval package、receipt、旧 runroot 或正式状态文件；未 commit/push；未启动 ROS、Gazebo、
preflight 或 smoke。

变更：

- 新增纯函数 `telemetry_channel_contract()`，显式区分连续 freshness 与启动期 presence。连续
  通道保持 `odometry/cloud/health/occupancy`；首次 PositionCommand 后且 completion 前，
  `trajectory/pos_cmd/ack` 原样加入连续 freshness 合同。
- `frontier` 在 completion 前仅作 startup-presence：必须至少收到一条，之后停更不再按 wall
  5 s 判 stale。frontier 的订阅、计数、readiness payload 门、topic-owner 基数与 exploration
  node 存活检查均未放宽。
- snapshot 新增 `telemetry_missing_channels`；`telemetry_complete` 同时依赖新鲜连续通道和
  已出现的 presence 通道。watchdog 对 stale 或 missing 均保持
  `corrupted_telemetry:<uav>:freshness` fail-closed abort。

负向纯函数 probes（纳入 collector self-test）覆盖：frontier 从未出现时 `missing` 失败；
frontier 仅出现一次、已过 60 s 时 WAIT_TRIGGER 仍通过；health 过期仍 stale 失败；command
活动期缺 trajectory/pos_cmd/ack 仍失败，补齐新鲜样本后通过；completion 后保留原有退出命令/
frontier 要求的语义。既有超时 ACK 负向检查仍通过。

验证（均离线）：

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio_multi_pycache python3 -m py_compile \
  scripts/two_uav_collector.py
PASS

python3 scripts/two_uav_collector.py --self-test
two_uav_collector self-test: PASS

sha256sum -c config/2uav_source_hashes.sha256
PASS: 12/12

python3 scripts/two_uav_preflight.py --mode static \
  --config config/2uav_static.yaml \
  --manifest experiments/manifests/2uav_smoke.yaml
PASS: 53/53

git diff --check
PASS (no output)
```

## 33. 第 26 节 final freshness reference 修复（无实验）

仅修改 `scripts/two_uav_collector.py`、对应 source hash 与本记录。每次 active `report()` 现在冻结
统一的 active wall-time reference；`finalize()` 的 final metrics 使用最近一次 active report reference，
而非 teardown 之后的 wall clock。因此停栈延迟不会把此前通过的低频 occupancy 误判 stale。

运行期 `_safety_watchdog()` 仍按实时 wall clock 执行原有连续 freshness 门；occupancy 超过 5 s 仍写入
`corrupted_telemetry:<uav>:freshness`。snapshot 对 pending command 的 ACK timeout 亦仍使用同一 active
reference，未改变 1 s fail-closed 合同、其它 telemetry、参数或 manifest。

collector self-test 覆盖：active reference 内 final telemetry complete；同一数据以 active reference
推进超过 5 s 时 `occupancy` 仍 stale；pending ACK 超时仍被记录。未启动 ROS、Gazebo、preflight 或 smoke。

## 34. 第 26 节首次实现复审返工（无实验）

仅修正 collector snapshot 的时钟语义。`now=time.monotonic()` 始终用于 pending ACK timeout 与 freeze，
包括 finalize 期间；`freshness_reference_wall_s` 仅用于 continuous-channel stale 计算。final report 必须
提供最近 active reference；若不存在，所有 continuous channel 被标为 stale，final telemetry fail-closed。
运行期 watchdog 继续省略 override，因而保持当前实时 5 s occupancy freshness 合同。

self-test 新增：teardown 期间才成熟的 ACK timeout 仍被记录；no-active-reference final snapshot 必须失败。
未修改参数、manifest、其它组件或 approval package，未启动实验。

有效 identity：

```text
scripts/two_uav_collector.py: efb27ff4335863f86e319a27ce8a06d8ad24ab90b3cf5eccac655d13c2540004
config/2uav_source_hashes.sha256: 0970f2e4b29aad999753270adb2cd8535d53826b4b0b651bced887e559657596
frozen manifest (unchanged): 75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46
static contract (unchanged): 415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e
runner (unchanged): 60bd1a8aa9455139cc4663b53408cc07b64777319a7b4f83b74417e9ebe4bd50
```

残余风险：该修复只调整无 goal 状态下对 visualization Marker 的 collector 分类，不能证明真实
ROS 运行时的 24 s soak 不会出现其他 abort。`bc75e406…a70713b` 已消费，不得复用；只有
Sol/lead 复审范围、diff、identity 与离线验证后，才可签发一次新的 preflight package；smoke
继续禁止。RT ≈0.33 仍是独立的 smoke 前主机负载/ACK wall-time 风险，未用降低安全阈值的方式掩盖。

## 23. 第 20 节 smoke 最小闭环：事件合同、功能门与机体回波诊断（无实验）

按 `state/sol_plan.md` 第 20 节，只修改了 `scripts/two_uav_collector.py`、
`scripts/two_uav_gt_mapper.py`、`scripts/two_uav_runner.py`、
`config/2uav_source_hashes.sha256` 与本记录。未修改单机/RACER 源码或参数、
`config/2uav_static.yaml`、manifest、launch、world、spawn、公共环境 baseline、PX4/Livox
workspace、freshness/TF/ACK 阈值、preflight live gate、approval package、receipt、旧 runroot、
`project_state.md`、`state/current_summary.md` 或 `state/SESSION_HANDOFF.md`；未 commit/push；
未启动 ROS、Gazebo、preflight 或 smoke。

### 变更与安全语义

1. collector 将 command 阶段的 `/planning/bspline_N` 从连续 freshness 改为 presence/event：
   首次 PositionCommand 后、completion 前必须至少出现一条 trajectory，但一条旧 B-spline 不会
   因超过 5 s wall 被误判 stale。`pos_cmd` 与 `ack` 仍是 5 s 连续通道，pending command 与
   ACK 1 s timeout/recovered-ACK/abort 语义未变；`frontier` 的第 17 节 startup-presence 语义
   也未回退。
2. runner 分离通用 final safety 和 `smoke_command_chain_valid()`。仅 `action_launch` 的最终结果
   额外要求 uav0、uav1 各自 `telemetry.trajectory/pos_cmd/ack > 0` 且
   `ack_timeout.count == 0`；缺字段、错误类型或零计数均 fail-closed 并在 detail 中点名 UAV。
   preflight 不传该门，保留无 goal 时 command 计数为零的既有语义；没有将 freeze 升格为即时
   abort，也未改 trigger/duration/monitor/stop/collect。
3. GT mapper 新增**只读诊断**而非滤波。两个 mapper 以线程安全 pose ledger 共享最新
   scan-time world pose；每个已注册点云只计数其落入 source-self/peer 机体 collision 包络的
   candidate，定期在 `logs/gt_mapper.log` 输出稳定 JSON（source、peer、input/output、candidate、
   pose status 与 geometry identity）。缺失、非有限、时间不可比较或与 scan stamp 相差超过既有
   `SYNC_SLOP_S=0.05` 的 peer pose 都记为 unavailable/stale，candidate 为零；不会猜测或删除点。
4. 冻结几何依据是公共 baseline 指向的
   `/home/houslakers/PX4-Autopilot/Tools/simulation/gazebo-classic/sitl_gazebo-classic/models/iris/iris.sdf.jinja`
   （SHA-256 `e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225`）：
   `base_link_inertia_collision` box `[0.47,0.47,0.11]` at `[0,0,0]`；四个 rotor collision
   cylinders（radius `0.128`、length `0.005`）的 link centers 分别为
   `[0.13,-0.22,0.023]`、`[-0.13,0.2,0.023]`、`[0.13,0.22,0.023]`、
   `[-0.13,-0.2,0.023]`；`link_platform/collision` box `[0.15,0.1,0.1]` at
   `[0,0,0.05]`。代码使用这组 collision primitive 的并集；未使用 inflation、经验半径或
   扩张出生点邻域。

`registered_cloud` 的输入过滤、下采样、world registration 与发布调用未改变；诊断未应用
candidate mask。因此本任务结论为：

```text
peer_body_hypothesis_status: UNCONFIRMED_DIAGNOSTIC_ONLY
point_filtering: NOT_IMPLEMENTED
```

### 离线验证

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio_multi_s19_pycache python3 -m py_compile \
  scripts/two_uav_collector.py scripts/two_uav_gt_mapper.py scripts/two_uav_runner.py
PASS

python3 scripts/two_uav_collector.py --self-test
two_uav_collector self-test: PASS
  command 前不要求 trajectory；command 后 trajectory 缺失失败；旧 trajectory + 新鲜
  pos_cmd/ack 通过；pos_cmd 或 ack stale 失败；既有 ACK timeout 与 frontier presence probes 通过。

python3 scripts/two_uav_gt_mapper.py --self-test
two_uav_gt_mapper self-test: PASS
  identity/90-degree rotation、self/peer 独立 candidate、missing/stale/non-finite pose
  fail-safe、无 mutation 输出均通过。

python3 scripts/two_uav_runner.py --self-test
two_uav_runner self-test: PASS
  双机 command-chain 成功、任一零计数、ACK timeout 和 preflight 无 command 语义均覆盖。

sha256sum -c config/2uav_source_hashes.sha256
PASS: 12/12

python3 scripts/two_uav_preflight.py --mode static \
  --config config/2uav_static.yaml \
  --manifest experiments/manifests/2uav_smoke.yaml
PASS: 53/53

git diff --check
PASS (no output)
```

有效 identity：

```text
scripts/two_uav_collector.py: 2343f0b9024878ea9a5c58d6e4cb941cd99b3950fd3a4184be355361d134aeb4
scripts/two_uav_gt_mapper.py: 9e2362f6f6aca47728e51aed151ad852349fa8586279e78fa66caaa073f1cb1d
scripts/two_uav_runner.py:    ad2fb78376ea71711e2a3f29920bb00118b45b9b3888d0e5e9eea2d3b9e7ef17
source-hash manifest:         3fd97d52d6e104758f8dee3253a63f4b0ae9188bf8052dcbd2546168b6c806b5
frozen manifest (unchanged):  75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46
static contract (unchanged):  415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e
```

残余风险：没有运行时机体 candidate 的数量、时空关联或对 uav1 inflated occupancy 的因果证据，
故不得实施 peer-body 点剔除，也不得据此签发 smoke。Sol/lead 只能先复审本 diff、几何来源及
离线证据；若合格，下一门至多是一张新的单次 preflight **诊断** package，用不可变新 runroot
采集上述 JSON 证据。已消费 smoke package
`3986a46c53dd3c7cfae9dbc03eb388fe80327fc2d2f784b8506a01a8b3988038` 永久不得复用。

## 24. 第 21 节最终门与诊断快照最小返工（无实验）

按 `state/sol_plan.md` 第 21 节，只修改 `scripts/two_uav_runner.py`、
`scripts/two_uav_gt_mapper.py`、`config/2uav_source_hashes.sha256` 与本记录。未修改
collector、冻结 iris collision geometry/点分类/registered cloud 发布、manifest、static config、
参数或阈值、approval package、receipt、旧 runroot、`project_state.md`、
`state/current_summary.md` 或 `state/SESSION_HANDOFF.md`；未 commit/push；未启动 ROS、Gazebo、
preflight 或 smoke。

变更：

1. `smoke_command_chain_valid()` 现在只接受长度恰为 2 的 list/tuple，并按固定顺序绑定
   uav0/uav1；若 metrics 明示 `name`，也必须匹配。每个 command count 只接受非 bool `int > 0`，
   ACK timeout count 只接受非 bool `int == 0`。因此 `None`、bool、string、任何 float（包括
   `NaN`/`Inf`）、零和负数，以及空/单机/三机/非序列 fleet 全部 fail-closed，detail 指向
   cardinality 或相应 UAV/字段。preflight 的通用 final safety 仍不要求 command chain。
2. mapper 增加纯函数 `body_diagnostic_snapshot()`，用 `copy.deepcopy()` 产生 JSON-ready 的
   source/peer/geometry identity 深快照。每个 `VehicleMapper` 有独立 `_body_lock`：raw、
   registered、candidate 及嵌套 pose-status counter 的更新均在锁内；Timer 亦在同一锁内取快照，
   释放锁后才 JSON 序列化/日志。点分类、包络、candidate 数学和 published registered cloud 未变。

离线验证：

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio_multi_s21_pycache python3 -m py_compile \
  scripts/two_uav_gt_mapper.py scripts/two_uav_runner.py
PASS

python3 scripts/two_uav_gt_mapper.py --self-test
two_uav_gt_mapper self-test: PASS
  深快照后修改原 counter 的顶层和嵌套 status 均不改变快照；uav0/uav1 snapshot 不共享。

python3 scripts/two_uav_runner.py --self-test
two_uav_runner self-test: PASS
  正常双机、uav0/uav1 零 command、ACK timeout、所有坏计数类型与空/单机/三机/非序列
  cardinality 全部覆盖；preflight 无 command 路径保留。

pure negative probes
runner_bad_counts_and_cardinality=FAIL_CLOSED
mapper_body_snapshot=DETACHED

sha256sum -c config/2uav_source_hashes.sha256
PASS: 12/12

python3 scripts/two_uav_preflight.py --mode static \
  --config config/2uav_static.yaml \
  --manifest experiments/manifests/2uav_smoke.yaml
PASS: 53/53

git diff --check
PASS (no output)
```

有效 identity：

```text
scripts/two_uav_collector.py (unchanged): 2343f0b9024878ea9a5c58d6e4cb941cd99b3950fd3a4184be355361d134aeb4
scripts/two_uav_gt_mapper.py:             38645cdac77388f8546fe94f2c9d4f332d727500260d4ef2329e19d9f818a690
scripts/two_uav_runner.py:                9e3141efafe8a6f618075d8fe6281b9a41e12f5542cad6d7def25fc377150621
source-hash manifest:                     a962c13024a4cdbadfc3a667ead557214af249698afbfcbedd69749af69c5f03
frozen manifest (unchanged):              75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46
static contract (unchanged):              415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e
```

残余风险不变：peer-body hypothesis 仍为 `UNCONFIRMED_DIAGNOSTIC_ONLY`，没有过滤或改变地图。
只能由 lead 在复审后决定是否签发新的、一次性 diagnostic preflight package；smoke 继续禁止。

## 25. 第 22 节高频 peer pose ledger 与 exact collision-mask 最小返工（无实验）

按 `state/sol_plan.md` 第 22 节，只修改了 `scripts/two_uav_gt_mapper.py`、
`config/2uav_source_hashes.sha256` 与本记录。未修改 collector、runner、preflight、manifest、
static 参数、launch/world、RACER/单机源码、公共 baseline、approval package、receipt、旧 runroot、
`project_state.md`、`state/current_summary.md` 或 `state/SESSION_HANDOFF.md`；未 commit/push；
未启动 ROS、Gazebo、preflight 或 smoke。

变更与安全语义：

1. 每架 mapper 现在在**每条原始 MAVROS odom**到达时，以 odom header stamp、当前姿态、当前位置
   加本机冻结 initial offset 写入共享 `PoseLedger`。ledger 拒绝严格更旧的 stamp，故同步
   scan/odom callback 不再以较旧 scan timestamp 覆盖高频 peer pose。scan callback 仍只以自身
   scan stamp 和未改动的 `SYNC_SLOP_S=0.05` 查询 peer；缺失、非有限、不可比较或 stale peer
   pose 一律完整保留点云。
2. world registration 后、`registered_cloud` 发布前调用纯函数 `peer_body_filter()`。仅当 peer pose
   available 时，删除当前冻结 `IRIS_COLLISION_PRIMITIVES` 并集精确命中的**peer** mask；self
   candidate 永不触发删除，包络外点逐点保留。过滤后即使空 cloud，registered odom、pose 和唯一
   `world -> uavN/base_link` TF 仍照常发布，frame/timestamp/geometry/时间窗均未改变。
3. 每 source 独立且加锁的深快照计数新增 `published_points`、`peer_removed_points` 与
   `peer_preserved_unavailable_points`。available 分支恒有
   `peer_removed_points == peer_candidates` 与
   `published_points == registered_points - peer_removed_points`；unavailable 分支恒有 removed=0，
   全部 registered 点计入 preserved。

mapper self-test 覆盖并已通过：冻结 geometry identity/primitive 常量锁定；available peer 的精确
删除与包络外逐点保持；missing/stale/non-finite peer 全量保留；self 命中不删；90° rotated peer；
过滤后空输出；不可变输入；ledger 拒绝旧 stamp；uav0/uav1 高频 odom 后两个方向均在既有 0.05 s
窗内可分类；诊断深快照不共享。没有实现 inflation、半径扩张、整帧删除或静态墙修改。

离线验证：

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio_multi_s22_pycache python3 -m py_compile \
  scripts/two_uav_gt_mapper.py
PASS

python3 scripts/two_uav_gt_mapper.py --self-test
two_uav_gt_mapper self-test: PASS

sha256sum -c config/2uav_source_hashes.sha256
PASS: 12/12

python3 scripts/two_uav_preflight.py --mode static \
  --config config/2uav_static.yaml \
  --manifest experiments/manifests/2uav_smoke.yaml
PASS: 53/53

git diff --check
PASS (no output)
```

有效 identity：

```text
scripts/two_uav_gt_mapper.py: b45cd7de27109515d9d1a63aec0509e6fa826e740bfcf326a84b477ab9ffbddd
source-hash manifest:         fff0f259ff24e1d2f8812c03ebe25677de96b8f3352c505a76a0abd610a9164b
frozen manifest (unchanged):  75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46
static contract (unchanged):  415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e
collision geometry (unchanged): iris.sdf.jinja:e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225
```

残余风险：这是精确 peer-body 回波的最小缓解，尚无新的运行时证据证明两个方向的 pose 可用率、
mask 恒等式或 sim≥15 的 `start inside inflated occupancy` 已满足第 22 节门槛。当前没有 approval
package；已消费 `aef23aefd98998693f57e4328010363bd849dfae794ab7691ff5b1b7baa57079` 永不得复用。
只能交由 lead 审核本 diff、identity 和离线证据；审核通过后至多签发新的单次 diagnostic preflight
package，smoke 继续禁止。

## 26. 第 23 节 odom 输入别名最小返工（无实验）

按 `state/sol_plan.md` 第 23 节，只修改了 `scripts/two_uav_gt_mapper.py`、
`config/2uav_source_hashes.sha256` 与本记录。未修改 collector、runner、preflight、manifest、static
config、geometry/时间窗/过滤、参数、registered cloud、odom/pose/TF frame 或 timestamp、world/baseline、
approval package、receipt、旧 runroot、`project_state.md`、`state/current_summary.md` 或
`state/SESSION_HANDOFF.md`；未 commit/push；未启动 ROS、Gazebo、preflight 或 smoke。

根因是同步 callback 中 `out_odom.pose = odom.pose` 的共享引用：对输出原地加 initial offset 会改写
同一个原始 MAVROS odom 子对象，而 message_filters 中 synchronizer 可先于 raw odom ledger callback
运行。修复新增纯 helper `offset_pose_copy()`，先 `copy.deepcopy()` 再仅在 detached 输出上叠加 initial
offset；`_callback()` 只使用该副本。`_odom_pose_cb()` 仍从原始输入 pose 和 header stamp 构造 ledger
record，一次且仅一次加入 initial offset。因此 registered odom/pose/TF 的对外数值合同不变，但任意
callback 顺序都不会令 uav1 的 `(0,*,*)` 累加成 `(3.0,*,*)`。

mapper self-test 已保留第 22 节所有 peer-mask、unavailable、rotated、empty、ledger、双向可分类和
deep-snapshot 用例，并新增：uav1 local `(0,2,3)` 输出 `(1.5,2,3)` 时输入仍为 `(0,2,3)`；模拟
“synchronizer callback 先、ledger callback 后”以及连续第二次输出构造，ledger 都保持 `(1.5,2,3)`。
额外使用真实 `nav_msgs/Odometry` 的离线 probe 验证：input=0.0、两次 output=1.5、ledger=1.5。

离线验证：

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio_multi_s23_pycache python3 -m py_compile \
  scripts/two_uav_gt_mapper.py
PASS

python3 scripts/two_uav_gt_mapper.py --self-test
two_uav_gt_mapper self-test: PASS

python3 <offline nav_msgs odom alias regression probe>
odom_alias_regression_probe: PASS input=0.0 output=1.5 repeat=1.5 ledger=1.5

sha256sum -c config/2uav_source_hashes.sha256
PASS: 12/12

python3 scripts/two_uav_preflight.py --mode static \
  --config config/2uav_static.yaml \
  --manifest experiments/manifests/2uav_smoke.yaml
PASS: 53/53

git diff --check
PASS (no output)
```

有效 identity：

```text
scripts/two_uav_gt_mapper.py: 2c4ab51bdecc26d03030ef93631f2376ba991178ea915ab787900096bb0df6ff
source-hash manifest:         2d99a213de37c8228ddbb86a12d748b1b94480289be974d846506fc95efc7788
frozen manifest (unchanged):  75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46
static contract (unchanged):  415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e
collision geometry (unchanged): iris.sdf.jinja:e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225
```

残余风险：本修复证明 mapper 不会将自己的 offset 写回输入消息，但尚无新的运行时证据证明两个方向
peer pose 可用率、精确 mask 计数恒等式或出生点 occupancy 已达到第 22 节门槛。当前没有 approval
package；已消费 `aef23aefd98998693f57e4328010363bd849dfae794ab7691ff5b1b7baa57079` 不得复用。仅可交回
lead 审核；未获新单次 diagnostic preflight 批准前 smoke 继续禁止。

## 27. Gate 5 provenance 只读诊断（无实验）

按本任务包，仅修改 `scripts/two_uav_gt_mapper.py`、对应 source hash 与本记录；未修改 collector、
runner、参数、mask geometry、manifest、approval package 或任何正式状态文件，未启动 ROS、Gazebo、
preflight 或 smoke。

新增 mapper `mapper_body_diagnostic` 的只读 provenance 字段：`uav1_hover_voxels` 逐体素记录
`source_uav`、`point_hits`、`first_sim_time` 与 `recent_sim_time`；hover 邻域固定为 uav1 冻结初始
world 坐标 `(1.5, 0, 1.5)` 周围 `0.35 m`，以冻结 occupancy `0.25 m` voxel 编码。对于 peer pose
`stale`，记录只读的 `peer_unavailable_body_candidates` 和
`peer_unavailable_inflation_candidates`；后者按冻结 iris primitives 的精确点到 primitive 距离与
既有 `0.35 m` inflation 计算。`missing`/`uncomparable` pose 不猜测位置，计数保持零。

这条新增路径只读取已注册 world points 与 pose snapshot，并只写 diagnostic counter；不向 peer mask
传递任何新 mask。mapper self-test 证明：输入 point array 不变；执行 provenance 前后的既有
`peer_body_filter()` published array 与 result 完全相等；stale pose 可产生可审计的 hypothetical
body/inflation 计数，同时既有 fail-safe published path 保留点。它不改变 published cloud、occupancy、
参数或控制路径。既有第 22/23 节 peer-mask 行为未在本任务中改动。

离线验证（无运行时实验）：

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio_multi_gate5_pycache python3 -m py_compile scripts/two_uav_gt_mapper.py
PASS

python3 scripts/two_uav_gt_mapper.py --self-test
two_uav_gt_mapper self-test: PASS
```

最终离线验证（无运行时实验）：

```text
sha256sum -c config/2uav_source_hashes.sha256
PASS: 12/12

python3 scripts/two_uav_preflight.py --mode static --config config/2uav_static.yaml \
  --manifest experiments/manifests/2uav_smoke.yaml
PASS: 53/53

git diff --check
PASS (no output)
```

有效 identity：

```text
scripts/two_uav_gt_mapper.py: bb60d5235d6cdc5d9f0bf03d8e83c1e4f57061a02061a7903a565b78a786f403
source-hash manifest:         7a52642ffceb945341dad812cca7adaea90bd90da4723f4bad791df17ba87571
```

残余风险：诊断本身尚无新的 runroot 运行证据，且 stale pose 的命中是明确标记的假设性计数，不得据此
宣称 occupancy 成因成立。它也不改变既有第 22/23 节 peer-mask 的行为；是否接受已有 mask 或签发
任何 preflight 必须由 lead 单独审核。

## 28. Gate 5 provenance 语义修正（无实验）

按本任务包，仅修改 `scripts/two_uav_gt_mapper.py`、对应 source hash 与本记录。修正第 27 节中
provenance 统计把 registered array 直接用于 hover 归属、以及 available 状态可能进入
`peer_unavailable_*` 的语义缺口；未修改 collector、peer mask、参数、control path、manifest、approval
package 或正式状态文件，未启动 ROS、Gazebo、preflight 或 smoke。

`uav1_hover_voxels` 现在只由 `peer_body_filter()` 已得到的实际 `published` array 生成，故被既有
peer mask 移除的点绝不会被归为 hover voxel。`peer_unavailable_*` 现在仅接受 `stale`、`missing` 与
`uncomparable`：三种状态均分别落盘 status；missing 没有可用 pose 时 body/inflation candidate 保持零，
不猜测位置；available 立即返回，不改变任何 unavailable counter。新增 diagnostic helper 仍只读
published array/pose snapshot、只写 counter，未向 peer mask 或 publisher 返回数据。

mapper self-test 的负向覆盖：available peer 的 hover 点会被既有 mask 移除，因而不进入 hover voxels
且所有 unavailable 字段保持零；stale peer 保持既有 published array，同时记录 hypothetical body/
inflation 命中与 source/first/recent sim time；missing 与 uncomparable 分别只记录状态、不会猜测 body/
inflation 命中。所有分支均断言 diagnostic 前后既有 published array 与 peer-filter result 完全相同，
并断言输入 array 不变。

离线验证（无运行时实验）：

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio_multi_gate5r_pycache python3 -m py_compile scripts/two_uav_gt_mapper.py
PASS

python3 scripts/two_uav_gt_mapper.py --self-test
two_uav_gt_mapper self-test: PASS

sha256sum -c config/2uav_source_hashes.sha256
PASS: 12/12

python3 scripts/two_uav_preflight.py --mode static --config config/2uav_static.yaml \
  --manifest experiments/manifests/2uav_smoke.yaml
PASS: 53/53

git diff --check
PASS (no output)
```

有效 identity：

```text
scripts/two_uav_gt_mapper.py: 7ea6243d1518fc5e1a30f7b33c35378b645871fb201768e0a15f5c57f6d169ae
source-hash manifest:         cb03164c3a3f1f44ad33c62790f7eb1b57dfc7bc5d997b1f9aafca228e00cfc5
```

不得将这项离线证据解释为 runtime occupancy 成因或任何实验批准。

## 29. 第 24 节 frontier readiness 与 node probe 加固（无实验）

按 `state/sol_plan.md` 第 24 节，仅修改 `scripts/two_uav_runner.py`、对应 source hash 与本记录；
未修改 RACER/单机参数、mapper、collector、preflight、manifest、launch、approval package 或正式状态文件，
未启动 ROS、Gazebo、preflight 或 smoke。

变更：

1. `ros_node_names()` 现在返回明确的 `success`、`timeout` 或 `error` observation。每次 node probe
   至多 `2` 次、单次 `3 s`、退避 `0.25 s`；timeout/non-zero 不再伪装成空 node 集合。readiness 仅在
   同一轮成功 node snapshot 包含所有 required node 且 payload 存在时通过；否则最终 detail 保留
   `node probe timeout` 或 `node probe error`。
2. RACER frontier 门使用集中常量的 `20 sim s` 初始化预算、`600 wall s` hard cap 与 `60 wall s`
   clock-stall cap。sim time 单调推进但低 RT 时，旧 `180 wall s` 已过而 sim budget 未耗尽会继续等待；
   sim budget 耗尽、wall cap、clock stalled、probe failure 或 process exit 均 fail-closed。
3. 未改 payload probe、已启动 Popen liveness、bridge node requirement、RACER launch 顺序、frontier
   topic 合同或 teardown 行为。

runner self-test 的负向覆盖包括：node success/missing/timeout/error；当前 node snapshot 与 payload 才
允许成功；低 RT 超过旧 wall 预算仍等到 payload；sim budget 耗尽；wall hard cap；clock stalled；任一
process exit。测试为纯函数/注入时钟，不启动 ROS。

离线验证（无运行时实验）：

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio_multi_s24_pycache python3 -m py_compile scripts/two_uav_runner.py
PASS

python3 scripts/two_uav_runner.py --self-test
two_uav_runner self-test: PASS

sha256sum -c config/2uav_source_hashes.sha256
PASS: 12/12

python3 scripts/two_uav_preflight.py --mode static --config config/2uav_static.yaml \
  --manifest experiments/manifests/2uav_smoke.yaml
PASS: 53/53

git diff --check
PASS (no output)
```

有效 identity：

```text
scripts/two_uav_runner.py: 67cf495c5c893039e386e746f8393b9ce6a9010bf296244381f8da08364f960e
source-hash manifest:      48c2db6153211aec6ff85a3f83ad63229dc40b3de6ce1dc4e4ed8e89e9ec7faa
frozen manifest:           75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46
```

旧 package `6280f48317acda77b6c2659b12b397b186f85a8fd6ed23be93dab61c7e7ac5c1` 已消费，禁止复用。
残余风险：这是离线 readiness hardening，尚无新 runroot 证明真实负载下 frontier 能在 sim budget 内
出现；是否签发新的单次 preflight package 必须由 lead 单独审核。

## 30. 第 25 节 live CLI retry 与 descendant teardown（无实验）

仅修改 `two_uav_preflight.py`、`two_uav_runner.py`、对应 source hash 与本记录。live CLI 采用固定 argv、
15 s 单次 timeout、3 次上限、0.5 s backoff、50 s 总 wall cap；每次保留 timeout/error/success attempt
证据，成功仍须由既有精确值比较通过。runner 在 TERM 前冻结 `/proc` descendant closure，并仅再发现同时
匹配本 runroot `ROS_LOG_DIR`、`ROS_HOME` 与唯一 `ROS_MASTER_URI` 的 reparent 后代；无关 ROS 进程或
环境不匹配 PID 不会被选择。TERM 后仍存活的匹配目标会 KILL，最终 survivor 或 master port 未释放均
`clean=false` 并使 preflight fail-closed。

纯自测覆盖 CLI timeout/error 后成功、全部失败、值不匹配与总 cap；以及多层/reparent closure、无关
进程排除、身份不匹配、TERM 后消失和 survivor failure。未启动 ROS、Gazebo、preflight 或 smoke；
manifest 与参数不变，package `186c9159e90bb918b674f311d5f45bd4565e7305fb164a652fcf2de41c2dda98`
已消费且禁止复用。

离线验证：两个脚本 `py_compile/self-test`、`sha256sum -c` 12/12、static preflight 53/53 与
`git diff --check` 均通过。

```text
scripts/two_uav_preflight.py: 35969b9698fcd802b87c6370ebe9c8e14e50154f2439a3093916e26e67dcd345
scripts/two_uav_runner.py:    a7c23cd7850f6d63b9afe12334186f4898e4338fcf7185c40e71b1e3dbc1ad45
source-hash manifest:         572603dff4e364a95b94385ab0af314ce02e1269519797c9b19ffda3eb04de48
```

## 31. 第 25 节 teardown root identity 锚定修正（无实验）

仅修正 runner teardown：active 现在冻结本 runroot 的 `ROS_HOME`、`ROS_LOG_DIR` 与
`ROS_MASTER_URI`。每一个顶层 PID 必须在 `/proc` snapshot 中精确匹配这三项才会成为 closure root；
PID 不存在、reuse、缺少环境或任一值不匹配时，该 root 被排除、不会展开其子树，并令 teardown
`clean=false`。同 runroot identity 的 reparent 后代仍按既有独立再发现规则处理。CLI retry、readiness
预算、参数和其它组件未变。

runner self-test 新增 PID reuse/root identity mismatch：root 与其无 identity child 均不进入 targets，
teardown fail-closed；无关进程仍排除。未启动实验或创建 package。

验证通过：两个脚本 `py_compile/self-test`、12/12 source hash、53/53 static preflight 与
`git diff --check`。runner hash 为
`bc33a2f6ecdf501e5a4b1b2ab415e925905b4a3b132e6c827c6c226d881363e1`；source-hash manifest 为
`d0c509a6c5e223594442701c98ef102e69c0d22b033c145f99f3cea995fb0455`。

## 32. 第 25 节 partial root identity teardown 修正（无实验）

rejected root 仍使最终 `clean=false`，但不再提前返回：`stop_active()` 会继续 TERM/KILL 所有已通过
完整 runroot identity 验证的 targets。拒绝 root 和仅由该 root 关系发现、但未独立验证的 child 不会收到
信号。新增伪 `/proc` 负向自测：PID-reuse root 与独立 identity-matched reparent target 同时存在时，
仅 reparent target 收到 TERM，最终无 survivors 但仍 fail-closed。CLI retry、参数、manifest 与其它逻辑
未改。

本节最终审计 identity：

```text
scripts/two_uav_runner.py: 67b6a343ea841bbfa54e23d72b6643aa22dde62c8bf47a243f83617ab760d6a2
source-hash manifest:      a96af28ea6d8c9b032ee5b840c48f309a592e5c85de4bc1874b9eae147c1a49b
frozen manifest:           75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46
```

针对上述版本实际完成的离线验证：

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio_multi_s25partial_pycache python3 -m py_compile \
  scripts/two_uav_preflight.py scripts/two_uav_runner.py
PASS

python3 scripts/two_uav_preflight.py --self-test
PASS

python3 scripts/two_uav_runner.py --self-test
PASS

sha256sum -c config/2uav_source_hashes.sha256
PASS: 12/12

python3 scripts/two_uav_preflight.py --mode static --config config/2uav_static.yaml \
  --manifest experiments/manifests/2uav_smoke.yaml
PASS: 53/53

git diff --check
PASS (no output)
```

## 33. 第 27 节 peer source-ray 精确相交 mask（无实验）

按任务包，仅修改 `scripts/two_uav_gt_mapper.py`、其在
`config/2uav_source_hashes.sha256` 的条目和本记录。未修改 collision geometry、
`obstacles_inflation`、任何参数/时间窗/downsample、collector、runner、preflight、manifest、
launch、approval package、正式状态文件或旧 runroot；未启动 ROS、Gazebo、live preflight 或 smoke。

每个同步 scan 现在以该 scan 的 detached source world pose 作为射线起点。只有 peer ledger pose
按既有 stamp 与 `SYNC_SLOP_S` 判定为 `available` 时才进行 endpoint/ray mask；peer missing、stale、
uncomparable 或 nonfinite 均保留原 array。mask 是闭区间 segment 与冻结的 box/cylinder collision
primitives 的精确几何相交，不含 epsilon、inflation、经验半径、hover/start 邻域或 voxel 批量删除。
已保留 endpoint exact mask；实际删除严格为 `endpoint_mask OR ray_mask`。

审计现在分别累计 `peer_endpoint_candidates`、`peer_ray_candidates`、union
`peer_removed_points` 和 `published_points`，其中每 scan 恒等式为
`published_points = registered_points - peer_removed_points`；旧 `peer_candidates` 保留为 endpoint
candidate 的兼容别名。source self candidate 仅为独立诊断，未参与 peer-ray mask 或发布决策。

mapper self-test 覆盖：endpoint body、peer 后方且射线穿过、peer 邻域但绕开、旋转 primitive、
closed tangent/boundary、source origin 在 peer primitive 外、missing/stale/nonfinite 全量保留、两 mask
重叠不重复计数、输入数组与 detached diagnostic snapshot 不变。自测还验证 source scan pose 作为
ray origin，且 available peer 之外不存在推测删除。

离线验证（无运行时实验）：

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio_multi_gate27_pycache python3 -m py_compile scripts/two_uav_gt_mapper.py
PASS

python3 scripts/two_uav_gt_mapper.py --self-test
two_uav_gt_mapper self-test: PASS

sha256sum -c config/2uav_source_hashes.sha256
PASS: 12/12

python3 scripts/two_uav_preflight.py --mode static --config config/2uav_static.yaml \
  --manifest experiments/manifests/2uav_smoke.yaml
PASS: 53/53

git diff --check
PASS (no output)
```

本次有效 identity：

```text
scripts/two_uav_gt_mapper.py: 1f008fba1ded02beea7fa48ada45b3280f8b3b08f566c95cea2a6e8b3332f941
source-hash manifest:         48de98805b0648dbeda460f72f369972ee733ce2859a2fc667bba7f469928ffb
frozen manifest:              75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46
```

残余风险：这是几何与静态合同证据，不证明 runtime hover occupancy 已消失；是否签发一次
diagnostic preflight 只能由 lead 审核决定，不能直接进入 smoke。

## 34. 第 27 节首次实现复审：统一 LiDAR 外参与 ray origin（无实验）

按复审任务包，仅修改 `scripts/two_uav_gt_mapper.py`、mapper 在
`config/2uav_source_hashes.sha256` 的 hash 和本记录。未修改 primitive、collision geometry、epsilon、
inflation、参数、collector、runner、preflight、manifest、launch、approval package 或正式状态文件；未启动
ROS、Gazebo、live preflight 或 smoke。

提取唯一冻结常量 `LIDAR_SENSOR_OFFSET_M = (0.0, 0.0, 0.13)` 与纯 helper
`lidar_sensor_world_origin()`。`register_points()` 和 source-ray origin 共同使用这一个常量；ray origin
现在严格为同步 scan source body world pose 加 `R_source * sensor_offset`，且仍携带该 scan stamp。
不存在第二份 offset 数值、epsilon 或 primitive 扩张。

新增 self-test 以非零 roll/pitch/yaw quaternion 验证 `register_points(local_zero)` 精确等于同一外参导出的
sensor origin，并验证该 origin 到同一注册 endpoint 的 segment 对 peer primitive 产生正确判定。回归构造
还证明旧 body-origin segment 会命中、而当前 LiDAR-origin segment 正确绕开；这证明修复消除了两种几何
模型不一致，而非通过扩大 primitive 掩盖差异。

离线验证（无运行时实验）：

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio_multi_gate27r_pycache python3 -m py_compile scripts/two_uav_gt_mapper.py
PASS

python3 scripts/two_uav_gt_mapper.py --self-test
two_uav_gt_mapper self-test: PASS

sha256sum -c config/2uav_source_hashes.sha256
PASS: 12/12

python3 scripts/two_uav_preflight.py --mode static --config config/2uav_static.yaml \
  --manifest experiments/manifests/2uav_smoke.yaml
PASS: 53/53

git diff --check
PASS (no output)
```

本次有效 identity：

```text
scripts/two_uav_gt_mapper.py: aa67881daa58dd13d3328ff40f0c93c59b71951943a99990493c4665f2d83cd9
source-hash manifest:         07b8f795cc9b0475c3ba815590b3d4a39c59c50a820e0b53357b6285f028047e
frozen manifest:              75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46
```

残余风险：离线几何一致性不等于 runtime hover occupancy 已清除。只可交由 lead 审核是否签发新的
diagnostic preflight；不得直接 smoke。

## 35. 第 28 节 bridge OFFBOARD/arm readiness 重试（无实验，静态门阻断）

按任务包，仅修改外部运行时文件
`/home/houslakers/swarm_ws/src/Swarm-LIO2/swarm_lio/scripts/px4_bridge.py`、
`config/2uav_source_hashes.sha256` 和本记录。未触及该外部仓库的其他文件（该仓库原有大量不相关 dirty
状态保持原样），未改 PX4/MAVROS、hover 阈值、45 s timeout、launch、manifest、mapper、collector、runner、
preflight、approval package 或正式状态文件；未启动 ROS、Gazebo、preflight 或 smoke。

bridge 新增集中常量 `READINESS_REQUEST_INTERVAL_S = 1.0`。physical-hover readiness 的既有 45 s
monotonic hard window 内继续连续发布原 hover target；若 mode 尚未确认 `OFFBOARD` 或尚未 armed，则至多
每秒一次调用对应服务。helper `request_offboard_and_arm()` 只请求未确认的条件，分别记录
`mode_sent`、`arm_success`、`mode_exception` 与 `arm_exception`，不再吞掉异常。每次尝试落盘 drone id、
attempt、当前 mode/armed、服务返回值与异常类；首次 OFFBOARD、首次 armed 和最终 hover ready 都有结构化
日志。原有高度、速度、stable、45 s 和 `RuntimeError("physical hover readiness timeout")` fail-closed
路径未改变。

新增纯 `--self-test`，因此不加载 ROS 消息包：覆盖 mode/arm false 后继续重试并最终成功、mode 已成功而
arm 延迟、服务 exception 后恢复、确认状态不重复调用、45 s timeout 边界与两架状态独立。

离线验证：

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio_multi_gate28_pycache python3 -m py_compile \
  /home/houslakers/swarm_ws/src/Swarm-LIO2/swarm_lio/scripts/px4_bridge.py
PASS

python3 /home/houslakers/swarm_ws/src/Swarm-LIO2/swarm_lio/scripts/px4_bridge.py --self-test
px4_bridge self-test: PASS

sha256sum -c config/2uav_source_hashes.sha256
PASS: 13/13

git diff --check
PASS (no output)

git -C /home/houslakers/swarm_ws/src/Swarm-LIO2 diff --no-index --check \
  /dev/null swarm_lio/scripts/px4_bridge.py
PASS (expected no-index exit 1; no whitespace error)
```

外部仓库将这个精确文件报告为预存未跟踪文件（`?? swarm_lio/scripts/px4_bridge.py`），故普通 tracked
`git diff` 没有基线；no-index check 仅对该精确文件执行，未将其它外部 dirty 文件纳入或清理。

静态 preflight 结果为 **52/53，fail-closed**。唯一失败项是
`source.overlay_installed_21_of_21`：其冻结 overlay identity 清单仍要求 bridge hash
`9ad51e4a8122bea78401e33cc27452a3ae6f49581a9d277a5adf7bad5e553db0`，而当前任务指定的 bridge 修复 hash
为下列值。第 28 节只授权 bridge、主 source-hash manifest 与本记录，未授权修改该外部 overlay identity
清单；因此没有越权更新它来伪造 53/53。

```text
/home/houslakers/swarm_ws/src/Swarm-LIO2/swarm_lio/scripts/px4_bridge.py:
  5cce75ddb7b3d21476a2492f7769cedd43bbfbdd2430dfe69562443bd87becf3
source-hash manifest:
  986982f4b0087a8946463d3659e31c590ef27e4220a0b0a525cf50358f1fab52
frozen manifest:
  75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46
```

阻断事项：lead 必须先决定是否签发一个允许同步更新外部 overlay identity 的最小任务包；在该授权前，
不得把本实现标为静态 53/53、不得签发 preflight 或进入 smoke。

## 36. 第 29 节公共 overlay identity bundle 准备（无实验，等待 Sol commit）

按第 29 节任务包，只准备公共 overlay identity；未修改运行时 bridge、installer 或安全门，未执行
overlay `--apply`，未启动 ROS/Gazebo/preflight/smoke，未创建 approval package、commit 或 push。

新建不可变 bundle source：

```text
/home/houslakers/auto_tune_racer/swarmlio-single-v2/history/
RUN-20260822T000000Z-px4-bridge-readiness-identity/px4_bridge.py
```

它由当前已审核运行时 bridge 逐字节复制，mode 为 `0755`，SHA-256 均为
`5cce75ddb7b3d21476a2492f7769cedd43bbfbdd2430dfe69562443bd87becf3`。公共 overlay 清单仍为 21 条，
仅 bridge 条目从旧 bundle/hash 改为该新 bundle/hash；其它 20 条保持 Git diff 无变化。multi 的 static
contract 和 smoke manifest 仅同步新 overlay manifest SHA；source-hash manifest 同步这两个文件并增加
公共 overlay manifest 与 bundle source 的绝对路径 hash，保留运行时 bridge 条目。

离线验证（均未 apply）：

```text
/home/houslakers/auto_tune_racer/swarmlio-single-v2/scripts/
apply_range20m_omnidirectional_overlay.sh --verify-bundle
OVERLAY_BUNDLE_READY files=21 base=57c1f34

python3 /home/houslakers/swarm_ws/src/Swarm-LIO2/swarm_lio/scripts/px4_bridge.py --self-test
px4_bridge self-test: PASS

sha256sum -c config/2uav_source_hashes.sha256
PASS: 15/15

21-entry identity probe
PASS: bridge hash/mode/source/root/target exact; other 20 unchanged by exact single Git diff

git diff --check
PASS (no output)

git -C /home/houslakers/auto_tune_racer/swarmlio-single-v2 diff --check -- \
  platform_overlays/range20m_omnidirectional_v1/current_config.sha256
PASS (no output)
```

single 精确 status（仅本任务目标）：tracked manifest 为修改一行，new bundle 是未跟踪文件；其它原有
single dirty 文件未纳入、未清理。运行时 bridge 没有在本节修改。此阶段故意不运行 static preflight：
single 尚未由 Sol 提交，`source.single_tracked_clean` 必须继续 fail-closed，不能把准备态宣称为 53/53。

有效 identity：

```text
overlay manifest:      a6479c4991d9d1f9c406b4b62292ab7c1fd1f58137078c65b5b88dcea677b249
bundle / runtime bridge: 5cce75ddb7b3d21476a2492f7769cedd43bbfbdd2430dfe69562443bd87becf3
multi static config:   52a4dbb6bf92b480eb27878b5bb120358b34fa00b77d9fb78a5ca43a178c1726
multi manifest:        4e6e813d3cf4ed7099c1c48c24f5e01bd5d061df0b0d15a745b76df94d7926d1
multi source manifest: 500d70948c7d721cff2a80a604020970be7dba6fa4d168455266756a9365bdd7
```

阻断：等待 Sol 审核并形成 single 公共 identity commit，随后才可同步新的 single commit 到 multi frozen
identity 并复跑 static 53/53；此前不得签发 preflight package 或进入 smoke。

## 37. 第 30 节 bridge 安装 mode 收敛（无实验）

更正第 36 节证据中的 mode 记录：当时运行时
`/home/houslakers/swarm_ws/src/Swarm-LIO2/swarm_lio/scripts/px4_bridge.py` 实际为 `0775`，并非所记的
`0755`；bundle source 和 overlay 清单始终为 `0755`。本节唯一变更是将该运行时文件 mode 从 `0775` 收紧为
`0755`；未修改任何字节、SHA-256、bundle、overlay 清单、installer、multi config/manifest/source-hash、
安全门或其它外部 dirty 文件，未执行 apply、实验、commit、push 或 approval package。

修正前后内容 hash 均为：

```text
5cce75ddb7b3d21476a2492f7769cedd43bbfbdd2430dfe69562443bd87becf3
```

修正后运行时 bridge 与 bundle source 均为 `0755`，并且二者 SHA-256 相同。

离线验证（只读，未 apply）：

```text
stat -c '%a %n' runtime_bridge bundle_bridge
755 runtime_bridge
755 bundle_bridge

sha256sum runtime_bridge bundle_bridge
both: 5cce75ddb7b3d21476a2492f7769cedd43bbfbdd2430dfe69562443bd87becf3

apply_range20m_omnidirectional_overlay.sh --verify-bundle
OVERLAY_BUNDLE_READY files=21 base=57c1f34

apply_range20m_omnidirectional_overlay.sh --check
OVERLAY_CHECK_OK files=21 base=57c1f34

PYTHONPYCACHEPREFIX=/tmp/swarmlio_multi_gate30_pycache python3 -m py_compile runtime_bridge
PASS

python3 runtime_bridge --self-test
px4_bridge self-test: PASS

sha256sum -c config/2uav_source_hashes.sha256
PASS: 15/15

multi git diff --check; single manifest git diff --check
PASS (no output)
```

single task pathspec status 仍仅为 overlay manifest 的一行修改和新 bundle 未跟踪文件；等待 Sol 精确 pathspec
提交公共 identity。尚未同步 single commit 或重跑 static 53/53，故不得签发 preflight 或进入 smoke。

## 38. 第 32 节 bridge/bundle trailing-whitespace 同步清理（无实验）

按第 32 节，只机械删除运行时 bridge 与 bundle 的第 150、168、198、331 行中只含空格的空白行尾随空格；
保留四个空白行本身，未修改非空白代码、readiness 行为、参数、installer、安全门或其它外部 dirty 文件。
两份文件保持 `cmp` 一致且 mode 均为 `0755`。未 commit/push、overlay apply、启动 ROS/Gazebo/preflight/smoke
或创建 approval package。

精确回归 diff 由当前文件重构清理前的四处空白，严格只得到这四个 hunks：

```text
line 150: "    " -> ""
line 168: "    " -> ""
line 198: "        " -> ""
line 331: "            " -> ""
```

两份文件的全文件 trailing-space probe 均为空；清理后内容 SHA-256 相同：

```text
b673080c46916790431f257aea1a27fa8616adeb6b409fe22968e0316b57f34f
```

公共 overlay 清单仍为 21 条，仅 bridge 条目的 hash 从第 29 节 identity 更新为上述清理后 hash；
source/mode/root/target 与其它 20 条不变。multi static config、smoke manifest 与 source-hash manifest
已同步该级联 identity。

离线验证（均未 apply）：

```text
cmp runtime_bridge bundle_bridge
PASS

stat -c '%a %n' runtime_bridge bundle_bridge
755 runtime_bridge
755 bundle_bridge

bridge exact whitespace probe + reconstructed-before diff
PASS: exactly lines 150, 168, 198, 331; no remaining trailing spaces

apply_range20m_omnidirectional_overlay.sh --verify-bundle
OVERLAY_BUNDLE_READY files=21 base=57c1f34

apply_range20m_omnidirectional_overlay.sh --check
OVERLAY_CHECK_OK files=21 base=57c1f34

PYTHONPYCACHEPREFIX=/tmp/swarmlio_multi_gate32_pycache python3 -m py_compile runtime_bridge
PASS

python3 runtime_bridge --self-test
px4_bridge self-test: PASS

sha256sum -c config/2uav_source_hashes.sha256
PASS: 15/15

multi git diff --check; single overlay manifest git diff --check
PASS (no output)

single git diff --cached --name-status
PASS: empty index
```

有效 identity：

```text
runtime/bundle bridge: b673080c46916790431f257aea1a27fa8616adeb6b409fe22968e0316b57f34f
overlay manifest:       bc9864fc24741526548094d425cda877a84d27aabf0ab92cdef08b206fecd2d0
multi static config:    dca22b88a64bd7d3dcd523b62ca1eaf8231aa2cac7c7025b26b5e3c7f600552d
multi smoke manifest:   f36c7517204c51131d8cfa389e151b0751c4f695d3f42ee6038058b1020a0e8c
multi source manifest:  38df7ad265ed4f6534184c4bf273ead47bd0e018fbb0d1b186bd42475bdfe82e
```

阻断保持：single 公共 identity 尚未由 Sol 以精确 pathspec 提交，multi 也尚未同步新的 single commit；
不得签发 preflight package 或进入 smoke。

## 39. 第 33 节 multi frozen single identity 同步与 static 53/53（无实验）

按第 33 节，仅将 `config/2uav_static.yaml` 的 `frozen.single_commit` 与
`experiments/manifests/2uav_smoke.yaml` 的顶层 `single_commit` 同步为已审核完整 single commit
`aea4b71cff10061f3211ffa1d2b21a6500caac78`，并仅更新这两个文件在
`config/2uav_source_hashes.sha256` 中的级联 hash。未修改任何源码、overlay/bundle/installer、参数、
approval package、外部仓库、runroot 或正式状态文件；未 commit/push、启动 ROS/Gazebo/live preflight/smoke
或创建 approval package。

single 身份已验证：`main@aea4b71cff10061f3211ffa1d2b21a6500caac78`，tracked-clean。该 commit 的
精确 file list 仅为：

```text
A history/RUN-20260822T000000Z-px4-bridge-readiness-identity/px4_bridge.py
M platform_overlays/range20m_omnidirectional_v1/current_config.sha256
```

overlay identity 保持已审核内容：manifest
`bc9864fc24741526548094d425cda877a84d27aabf0ab92cdef08b206fecd2d0`，bridge
`b673080c46916790431f257aea1a27fa8616adeb6b409fe22968e0316b57f34f`，installer hash 未变。

离线验证：

```text
single HEAD/full commit + tracked-clean + exact commit file list
PASS

overlay --verify-bundle / --check
PASS: 21/21 CURRENT

py_compile runner/preflight/bridge
PASS

two_uav_runner.py --self-test
PASS

two_uav_preflight.py --self-test
PASS

px4_bridge.py --self-test
PASS

sha256sum -c config/2uav_source_hashes.sha256
PASS: 15/15

python3 scripts/two_uav_preflight.py --mode static --config config/2uav_static.yaml \
  --manifest experiments/manifests/2uav_smoke.yaml
PASS: passed=true, 53/53

git diff --check
PASS (no output)
```

最终 identity：

```text
single commit:          aea4b71cff10061f3211ffa1d2b21a6500caac78
multi static config:    d106f0ca52bfcad5800d65e9a0f6692a074631cea965e96f5880e99d23461de0
multi smoke manifest:   5e841a9662fb49b1289951f490b094843740412f9845e122627e8d069fe1a871
multi source manifest:  1a6e4caa4d784016e763942a601f22c29e1f247a23a582c7927106fc07943ef7
```

静态 53/53 仅恢复身份链，不构成 preflight 授权；是否签发新的单次 diagnostic preflight package 仍完全由
Lead/Sol 审核决定，smoke 继续禁止。

## 40. 第 34 节 available peer inflation-neighborhood endpoint mask（无实验）

按第 34 节，仅修改 `scripts/two_uav_gt_mapper.py`、其在 source-hash manifest 中的 hash 与本记录。未修改
`OCCUPANCY_INFLATION_M=0.35`、collision primitives、freshness/slop、source-ray、range/downsample、起点地图、
manifest/static config、collector/runner/preflight、参数、approval package 或正式状态文件；未启动 ROS、Gazebo、
preflight/smoke，未 commit/push。

available peer pose 下，endpoint mask 现在严格为：

```text
exact_collision_endpoint OR exact_distance_to_frozen_collision<=0.35
```

最终删除为上述两个 endpoint mask 与既有 exact collision ray mask 的 union。ray 仍只相交原始冻结 collision
primitives，不对 inflation 体积做射线扩张。missing/stale/uncomparable/nonfinite peer 与此前一样原数组全量
保留，不推测删除。

新增独立累计 `peer_inflation_endpoint_candidates`；保留 exact endpoint 与 ray counters。每 scan 删除数是三
mask union，因而无重复计数并保持 `published_points = registered_points - peer_removed_points`。hover provenance
继续只记录最终 published array；available pose 不进入 `peer_unavailable_*` diagnostics，故新 mask 删除的
candidate 不会误记为 published hover voxel。

self-test 新增/覆盖：primitive 内、外部但冻结 exact-distance `<=0.35`、闭边界 tangent、刚好超界、rotated
primitive、三 mask overlap union、远环境点保留、available/stale/missing/nonfinite、输入不变与计数恒等式。
以 uav1 hover coordinate 的合成点 `(1.9, 0, 1.5)` 证明旧 exact endpoint 会保留、当前 frozen-neighborhood
endpoint 会删除；超出邻域点保持发布。该离线测试不声称 runtime 问题已消失。

离线验证：

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio_multi_gate34_pycache python3 -m py_compile scripts/two_uav_gt_mapper.py
PASS

python3 scripts/two_uav_gt_mapper.py --self-test
two_uav_gt_mapper self-test: PASS

sha256sum -c config/2uav_source_hashes.sha256
PASS: 15/15

python3 scripts/two_uav_preflight.py --mode static --config config/2uav_static.yaml \
  --manifest experiments/manifests/2uav_smoke.yaml
PASS: passed=true, 53/53

git diff --check
PASS (no output)
```

本节 identity：

```text
mapper:                 c90383cb1083b554e50355405353d5a5e3ed3ce9a586a2d30962f8fc40a5c4e9
multi source manifest:  a932046b25198a692d1932f4cf3b315692b6d4a85d137cf4f5e21b2ee0f6b5c5
frozen smoke manifest:  5e841a9662fb49b1289951f490b094843740412f9845e122627e8d069fe1a871
```

残余风险：该修复具有运行期 peer echo/inflation 证据支撑，但当前证明仍仅为离线几何与静态合同；是否签发
新的 diagnostic preflight 只能由 Lead/Sol 决定，smoke 仍禁止。

## 41. 第 36 节 occupancy snapshot 与 runroot-local resource profiler（无实验）

按第 36 节，仅修改 `scripts/two_uav_collector.py`、`scripts/two_uav_runner.py`、
`scripts/two_uav_preflight.py`、`config/2uav_static.yaml`、
`config/2uav_source_hashes.sha256` 与本记录。未修改 RACER、GT mapper、manifest、approval package、
正式状态文件或外部仓库；未启动 ROS、Gazebo、live preflight/smoke，未 commit/push。

collector 将 occupancy 从连续 5 s freshness 通道改为 startup-presence：在 startup grace 内必须成功解析至少一帧，
缺失或解析异常仍 fail-closed；已出现的 occupancy 不再因地图大快照间隔超过 5 s 触发 stale。odom、cloud、health，
以及运行期 pos_cmd/ACK freshness、trajectory presence、ACK timeout、TF/topic-owner/process-death/abort 等既有门
未放宽。occupancy subscriber 使用 `queue_size=1`，callback 只保存最新 frame；flush 按冻结的 2.0 s sim-time
period 处理 coverage union。每 UAV metrics 记录 received/processed/coalesced、消息/处理 wall+sim time 与最近
callback/处理耗时，解析异常继续写 abort request。

runner 增加每 1 wall s 的低开销 `/proc` sampler，写入 runroot append-only
`resource_usage.jsonl`。按启动 role 聚合其进程树 CPU ticks/delta、RSS、threads 与 PID 列表，同时记录 wall、sim、
loadavg 和 MemTotal/MemAvailable；PID 消失或读取失败只标为 `evidence_missing`，不改变生命周期控制。preflight/smoke
结果汇总提供 p50/p95/max RSS、累计 CPU delta 与 top CPU consumers。live 与 final gate 均 fail-closed 要求 resource
profile schema/records 完整；这不替代 occupancy startup presence 与 coverage available 的 final 要求。

static contract 固定：`occupancy_contract: startup_presence`、`coverage_coalesce_sim_s: 2.0`、
`resource_sample_wall_s: 1.0`，而 `freshness_s` 保持 5.0。preflight static 明确验证上述值。

离线验证（均未启动实验）：

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio-pyc-36 python3 -m py_compile \
  scripts/two_uav_collector.py scripts/two_uav_runner.py scripts/two_uav_preflight.py
PASS

python3 scripts/two_uav_collector.py --self-test
PASS: startup presence、occupancy 非连续 stale、其他连续通道/ACK fail-closed

python3 scripts/two_uav_runner.py --self-test
PASS: resource schema、CPU delta、RSS p95、PID disappearance evidence_missing

python3 scripts/two_uav_preflight.py --self-test
PASS

sha256sum -c config/2uav_source_hashes.sha256
PASS: 15/15

python3 scripts/two_uav_preflight.py --mode static --config config/2uav_static.yaml \
  --manifest experiments/manifests/2uav_smoke.yaml
PASS: passed=true, 53/53

git diff --check
PASS (no output)
```

本节 identity：

```text
collector:             0bc92bb15244cccdc604b5416105575f4e7ba60d158928656c0436174fdc6ec6
runner:                aa87e9103b3ce3f599abe00c59d8f4eaa6400eb32c6a794f9e18d3a604bd7251
preflight:             0b9f93e36f7a7b7c580c05c8babfc4733d22296883a8b90bc5f33381d4d918c0
static config:         d269f96c3c59fc15035ee8fcb0d47b97ae41db60f6ad00c726a8ae783e38c303
source-hash manifest:  43f9ce10fc457ea7ff10863546201ad993d26795351a7ad18950389141227bbe
frozen smoke manifest: 5e841a9662fb49b1289951f490b094843740412f9845e122627e8d069fe1a871
```

仍为离线合同与自测证据，不构成实验授权；是否签发任何新的 diagnostic preflight package 完全由 Lead/Sol 审核决定，
smoke 继续禁止。

## 42. 第 37 节 captured-frame 竞态与完整 resource profile（无实验）

按第 37 节，只修改 `scripts/two_uav_collector.py`、`scripts/two_uav_runner.py`、
`scripts/two_uav_preflight.py`、`config/2uav_source_hashes.sha256` 与本记录。未修改
`config/2uav_static.yaml` 的冻结值、manifest、GT mapper、RACER、approval package、旧 runroot 或正式状态文件；
未启动 ROS、Gazebo、preflight/smoke，未 commit/push。

修复 collector 的 captured-frame 提交竞态：解析完成的 captured occupancy frame 现在始终提交
coverage/presence、processed 与 last processed 时间；仅当 `pending_occupancy is captured` 才清空 pending。
因此 parse 期间到达的 newer frame 保持 pending，留给下一 coalesced 周期处理，而不会让持续大消息流将已成功
解析的旧帧全部丢弃。callback 与 processing duration 已拆分；coverage 还提供 received/processed/coalesced、
last message/processed wall+sim 与按当前 report reference 计算的 message/processed age。零 frame/解析异常仍
fail-closed，occupancy 仍不进入连续 5 s stale 集合，其他连续与 ACK/TF/owner/process gates 未放宽。

runner profiler 在第一个 role spawn 前创建并保留动态 `processes` mapping；每次 role spawn 及 readiness 轮询按
1 wall s 限频采样，故覆盖 PX4/Gazebo/RACER 启动与 readiness。soak 从现有 collector telemetry JSONL 读取 sim
time，monitor 使用既有 clock probe；不会为 profiler 新增 subprocess 高频采样。任何时刻取不到 sim 都写
`sim_s: null, sim_evidence_missing: true`，不伪造时间。每条 record 现含 wall delta、sim、RT factor、CLK_TCK
和每 role 归一化 `cpu_cores`；summary 输出 role CPU-core p50/p95/max、RSS p50/p95/max、top consumers 与有效
RT 样本及 RT p50/p95/max。PID 消失仍只是 `evidence_missing`，不改变控制路径。live schema 同步要求新字段。

离线验证（均未启动实验）：

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio-pyc-37 python3 -m py_compile \
  scripts/two_uav_collector.py scripts/two_uav_runner.py scripts/two_uav_preflight.py
PASS

python3 scripts/two_uav_collector.py --self-test
PASS: 确定性 A parse 期间 B 替换；A 计入 coverage/presence，B 保持 pending，下一周期清空 B

python3 scripts/two_uav_runner.py --self-test
PASS: fake /proc + fake clock 覆盖动态 startup role、wall delta、CLK_TCK CPU normalization、
sim missing、RT、PID disappearance、CPU/RSS p50/p95/max

python3 scripts/two_uav_preflight.py --self-test
PASS: profile schema（wall delta/sim missing/CLK_TCK）正反测试

sha256sum -c config/2uav_source_hashes.sha256
PASS: 15/15

python3 scripts/two_uav_preflight.py --mode static --config config/2uav_static.yaml \
  --manifest experiments/manifests/2uav_smoke.yaml
PASS: passed=true, 53/53

git diff --check
PASS (no output)
```

本节 identity：

```text
collector:             1685dcd64a442423fd3c00d4c1062e84e2fa667f01e2aee1009e195a7ad36eca
runner:                f818feec31d8ad8bc480b11d851580bd7d3fdb0fca571a5879bd83ba5bff41f2
preflight:             50fd9d421b64080f9b8616321a85032bd1b7ce4204276ba67ddd5fb2b69eac92
source-hash manifest:  0d240a7df3f442ded8eca4b0ae9bfc72b5995272fdfe501cd18824c67cef22ff
static config unchanged:d269f96c3c59fc15035ee8fcb0d47b97ae41db60f6ad00c726a8ae783e38c303
mapper unchanged:      c90383cb1083b554e50355405353d5a5e3ed3ce9a586a2d30962f8fc40a5c4e9
manifest unchanged:    5e841a9662fb49b1289951f490b094843740412f9845e122627e8d069fe1a871
```

这些是离线实现与诊断证据，不构成实验或 package 授权；是否重新签发 diagnostic preflight package 仍仅由
Lead/Sol 决定，smoke 继续禁止。

## 43. 第 38 节公共 compute overlay 准备（未 apply/未实验）

按第 38 节准备 compute baseline：运行时 RACER XML 仅将 `sdf_map/resolution` 从 0.05 改为
0.10，并新增 `map_ros/all_map_publish_period=2.0`；`map_ros.cpp` 仅读取该参数（默认 0.2）、
拒绝非有限/非正值并以 ROS/sim time 的 elapsed period 节流 `publishMapAll()`。local map、ESDF、融合、
规划和控制 timers 未改；sim time 回退会立即重新建立 full-map cadence。两文件逐字节复制到新的 immutable bundle
`history/RUN-20260822T201500Z-compute-overlay-prepared/`，overlay manifest 恰替换这两个条目，仍为 21 条，
root/target/mode 与其他 19 条不变。未执行 overlay `--apply`。

50×50×3 m 地图 voxel：0.05 m 为 60,000,000，0.10 m 为 7,500,000（1/8）。该比例只说明主要
per-voxel SDF buffer 的理论常驻量下界下降；double/short/flag 等实际 buffer 组合与共享页决定 RSS，不能将
理论字节直接等同实测 RSS。2/4 UAV 的该类下界分别为每机 buffer 字节数的 2/4 倍。

runner 增加 fail-closed 负载门：启动前 `MemAvailable>=8 GiB` 与 `load1<10`；stack-ready 与 soak
`MemAvailable>=3 GiB`、相对启动基线无 swap-in/out。缺失证据、低内存、load 或 swap 都失败。profile 已保留
连续 clock 采样得到的 overall RT 字段，且不以瞬时 collector flush 混叠作为通过依据。preflight static/live
增加 resolution 与 full-map period readback。

离线验证：

```text
single overlay --verify-bundle: PASS 21
single overlay --check: PASS 21/21 CURRENT (未 --apply)
cmp runtime/bundle XML,map_ros.cpp: PASS
git -C single diff --cached --name-only: empty
git diff --check (multi/single): PASS

cd /home/houslakers/racer_ws && catkin_make -DCMAKE_BUILD_TYPE=Release --pkg exploration_manager
PASS (map_ros.cpp rebuilt; exploration_node linked)

PYTHONPYCACHEPREFIX=/tmp/swarmlio-pyc-38 python3 -m py_compile runner preflight
runner/preflight self-test: PASS（含 8/3 GiB、load、swap、缺失证据边界）
sha256sum -c config/2uav_source_hashes.sha256: PASS 15/15
```

identity：overlay `7ae5413c0f2197f15bba038635c2dc9f631ad98aeeb0bb4f452d552422cafc63`；
XML `9c0ce4b2a489e019aee01cfcf124a11d66cdcc7bc10cdc5b82b69cdc3aa73721`；
map_ros `fc23045c16e2f81aa9110a0ede8b2161e50805303a3a361bccfd1609f51e70ae`；
multi source hash `82565a1b8c46a39142eec748319fb0dc79799fabc21efd6880ddffbe13bc410e`。

single overlay 尚未由 Sol 精确 pathspec commit，故 multi single commit 未伪造更新；prepared static identity
必须保持 fail-closed，不能签发 package 或启动 preflight/smoke。

## 44. 第 40 节 compute XML trailing-whitespace 清理（无实验）

按第 40 节先安全执行 single 的精确 pathspec `git restore --staged --`，取消暂存 compute bundle 两文件和
overlay manifest，保留工作树内容；随后确认 single index 为空。仅删除 runtime
`single_drone_planner.xml` 的 10 处历史 trailing whitespace（25、62、64–68、74、374、386 行），未重排或
改变 XML 值。清理后 XML 逐字节同步至 immutable bundle；bundle `map_ros.cpp` 未修改并保持
`fc23045c16e2f81aa9110a0ede8b2161e50805303a3a361bccfd1609f51e70ae`。

single overlay manifest 保持 21 项，恰仅 XML bundle 条目的 SHA 变为
`6739a77cc56bcf91a9525a0ea4b6932b40c1994cb485e437cbed9e587072d227`；其派生 overlay manifest 为
`68ceb54faa24f4cc97396634bfc3d611f8e40a6db89999d3cbabc112092ccf62`。multi 仅同步该 manifest identity 及
必要 source hash；`single_commit` 未改变。未 apply overlay、commit/push、启动 ROS/Gazebo/preflight/smoke 或
创建 package。

验证：XML parse/value probe 确认 resolution 仍 `0.10`、all-map period 仍 `2.0`；`rg '[ \t]+$'` runtime XML
无输出；runtime/bundle `cmp` PASS；overlay `--verify-bundle`/`--check` 均为 21/21；single index empty；
multi/single `git diff --check` 无输出；runner/preflight py_compile/self-test PASS；source hash 15/15 PASS。

static 为预期 prepared-not-committed fail-closed：54/55，唯一失败
`source.single_tracked_clean`（新的 single overlay manifest 尚未由 Sol 提交）。当前 preflight 增加的 compute
readback 合同使总数从旧 53 变为 55；未据此创建 package。

本节 multi source-hash manifest：
`f23b290e5110fd49e79fdced842a4de78287310c313a5d56c6d6cc0b604ebb46`。

## 45. 第 42 节 multi frozen single identity 同步（无实验）

按第 42 节，仅将 `config/2uav_static.yaml` 的 `frozen.single_commit` 与
`experiments/manifests/2uav_smoke.yaml` 的 `single_commit` 从
`aea4b71cff10061f3211ffa1d2b21a6500caac78` 同步为已审核 single `main` commit
`8c8ddf2add3f7b3ce4f9943583fd945f16b1bd91`，并仅更新这两项的派生 source hash。
overlay manifest SHA 保持 `68ceb54faa24f4cc97396634bfc3d611f8e40a6db89999d3cbabc112092ccf62`；
resolution、full-map period、资源门及所有其他代码/参数不变。未 commit/push、apply overlay、启动 ROS/Gazebo/
preflight/smoke 或创建 approval package。

验证：single HEAD 精确为上述 commit，index 为空，tracked tree clean；multi runner/preflight py_compile 与
self-test PASS；source hash 15/15 PASS；static `55/55` PASS；multi/single `git diff --check` 无输出，single
cached file list 为空。

本节 identity：static config `a0fb9077b67d48cf30ed233a886954966e57df331c73c3f8f2ffa6958b44faed`，
smoke manifest `5cc07755cb46cfb13fda34fa96b9e528766340541c8eb919f62f7a000381e3c5`，source-hash manifest
`b275c3e06238b9e7a00653bd3b2439e893b47d947b7f085c64fa3974fb25c99a`。

static 55/55 仅恢复可审核的公共 identity；不构成 preflight 授权，是否签发新 package 仍完全由 Lead/Sol 决定，
smoke 继续禁止。

## 46. 最小资源治理方案与离线资源证据（无实验）

任务来源：`state/SESSION_HANDOFF.md` 交接指令 + RUN-20260821T202125Z 资源证据。本任务为
**治理方案分析与离线验证**，未修改任何源码、manifest、config、launch、overlay、approval package、
receipt 或正式状态文件；未启动 ROS、Gazebo、preflight 或 smoke，未 commit/push。实现结果只记录于本文件。

### 46.1 运行证据解析（只读，两轮 profile 对比）

对 `resource_usage.jsonl` 的逐角色进程树 RSS/CPU 基线做只读解析（脚本见
`/tmp/resource_analyze.py`，仅统计不落盘任何新实验产物）：

```text
RUN-20260821T194922Z (0.05 m, 未 apply compute overlay):
  gazebo      max_rss=4.933 GiB  max_cores=3.14  pids=18
  racer       max_rss=6.917 GiB  max_cores=2.20  pids=9
  bridges     max_rss=0.130 GiB  max_cores=2.96  pids=3
  gt_mapper   max_rss=0.098 GiB  max_cores=0.46  pids=1
  collector   max_rss=0.052 GiB  max_cores=0.15  pids=1
  samples=41  min MemAvailable=1.25 GiB

RUN-20260821T202125Z (0.10 m, compute overlay 生效; PREFLIGHT_FAILED_RESOURCE_GATE_SWAP):
  gazebo      max_rss=4.932 GiB  max_cores=3.20  pids=18
  racer       max_rss=1.667 GiB  max_cores=0.61  pids=9
  bridges     max_rss=0.130 GiB  max_cores=3.28  pids=3
  gt_mapper   max_rss=0.102 GiB  max_cores=0.52  pids=1
  collector   max_rss=0.004 GiB  max_cores=0.00  pids=1
  samples=17  min MemAvailable=6.35 GiB
```

结论（归因）：

- **compute overlay 已兑现地图侧主收益**：`racer` 进程树 RSS 从 6.917 → 1.667 GiB（−5.25 GiB），
  栈总 RSS 从 ~11.1 → ~6.8 GiB（−4.3 GiB），最低 MemAvailable 从 1.25 → 6.35 GiB。0.10 m overlay
  使 per-voxel buffer 的理论下界降为 1/8（60M→7.5M voxels），实测与第 43 节预测量级一致。
- **剩余主导消费者是 sim 基础设施而非算法**：`gazebo` 进程树（gzserver + 2×PX4 SITL + 2×livox
  ray 插件）RSS 在两次运行均为 ~4.93 GiB，与地图分辨率无关。传感器 samples=24000、update_rate=10、
  机型/物理、世界均为冻结合同，不能在不改变安全语义的前提下继续拆分。
- **本次失败是 fail-closed 按设计生效**：startup 门 load1=2.01、MemAvailable=12.69 GiB 通过；running
  门 MemAvailable=6.41 GiB（≥3 GiB 满足）但 `swap_in` 29491→29619（+128 KB）触发
  `swap activity observed`。+128 KB 是启动爬升期的瞬时残留换页（本 boot 累计 swap_out 已 221,525 KB，
  主要来自上一轮 0.05 m 运行），资源门拒绝它是正确行为；不得放宽门来掩盖。

### 46.2 内存预算模型（2-UAV 全栈，来自实测）

```text
MemTotal            = 16.17 GB (15.42 GiB, 本机)
非栈基线(内核+系统+外部进程) ≈ 2.73 GiB   (startup 时 15.42−12.69)
栈 MemAvailable 消耗          ≈ 6.28 GiB   (12.69−6.41, 含共享页重复计数的 RSS 上限 6.84 GiB)
running 时 MemAvailable      ≈ 6.4 GiB    (gate 采样 6.88 GB; profile 最低 6.35 GiB)
```

### 46.3 方案评估

**方案 A：增加物理内存至 32 GB（优先）**

- 32 GB 主机（~29.8 GiB 可用）推算：startup MemAvailable ≈ 29.8−2.7 = 27.1 GiB（≥8 GiB 门）；
  running MemAvailable ≈ 27.1−6.3 = **20.8 GiB**（≥3 GiB 门，余量 ~17.8 GiB）；启动/运行全程
  pswpin/pswpout 保持 0，无残留换页债务。
- 确定性消除 swap-in 风险，且是 3-4 UAV 的必要前提（每架 UAV 增加约 ~3 GiB 栈 + sim 基础设施）。

**方案 B：关闭外部竞争负载（必要的操作纪律，但不充分）**

- 当前桌面负载（firefox ~0.9 GiB + cursor 多进程 ~2.4 GiB + gnome-shell ~0.8 GiB + Xorg ~0.3 GiB +
  sogou/snap 等）合计 RSS ~5 GiB，其中可回收匿名页对 MemAvailable 的净增益约 1–3 GiB。
- 16 GB 上即便全关，running MemAvailable ≈ 6.4+2 ≈ 8.4 GiB，仍可能因上一 boot 残留 swap 页被触碰而
  触发 +128 KB 级 swap-in；无法保证不 fail。必须与方案 A 或全新 boot + 无历史 swap 债务配合。

**方案 C：进程/地图负载拆分（已兑现主要部分，无进一步安全余量）**

- 地图侧拆分已由 0.10 m overlay 完成（racer −5.25 GiB）。剩余 gazebo ~4.93 GiB 是 sim 基础设施，
  受冻结合同约束；bridges 0.13 GiB / gt_mapper 0.10 GiB / collector 0.004 GiB 无可拆分空间。
- 结论：在"不改变安全语义"约束下，代码侧没有新的有意义拆分。

**方案 D（不采用）：降低资源门** —— 8/3 GiB 与 swap-free 门是正确防线，本次失败是资源不足的真实
信号；不降门、不忽略 swap、不改 freshness/occupancy/安全合同。

### 46.4 最小治理方案（推荐顺序）

1. **主机物理内存升至 32 GB**（优先、确定性、可长期复用；同时是 3-4 UAV 的硬件前提）。
2. **每次运行前关闭外部竞争负载**（firefox/cursor/gnome/Xorg 等）并记录 MemTotal/MemAvailable/pswpin/
   pswpout 基线；推荐在全新 boot 后执行，避免历史 swap 债务。
3. **保持全部 fail-closed 门不变**（startup MemAvailable≥8 GiB、load1<10；running MemAvailable≥3 GiB、
   swap-in/out 不增长；缺失证据失败）。
4. 当前 16 GB 主机在完成 32 GB 升级前，不得再次签发 preflight package；smoke 继续禁止。

### 46.5 离线验证（只读系统证据，未启动实验）

```text
free/proc/meminfo: MemTotal=16,166,636 kB; MemAvailable=10,281,144 kB (当前空闲)
/proc/vmstat: pswpin=0, pswpout=0 (主机已重启，无历史 swap 债务)
SwapTotal=2,097,148 kB; SwapFree=2,097,148 kB
loadavg=0.74 1.43 2.24; nproc=20
ps -eo pid,rss,comm --sort=-rss 顶部: firefox~975MB, cursor~711MB, gnome-shell~549MB,
  Xorg~281MB, sogou~174MB, snap-store~171MB … 外部负载合计 RSS ~5 GiB

资源门代码复核: scripts/two_uav_runner.py capacity_gate() 固定
  startup minimum=8 GiB + load1<10; running minimum=3 GiB + swap_in/out 与 baseline 逐字节相等;
  config/2uav_static.yaml 冻结 resource_startup_mem_available_gib=8,
  resource_running_mem_available_gib=3, resource_swap_activity=abort。门未被修改。
```

### 46.6 残余风险

- 上述 32 GB 推算基于单次 running gate 采样与进程树 RSS 上限，实际不同主机/BIOS 内存量、共享页比例
  会使数值 ±1–2 GiB；需要 32 GB 硬件到位后以同一 manifest 重跑一次 diagnostic preflight 实证。
- 本次没有有效连续 RT 样本（`sim_evidence_missing: true`），compute baseline 的 RT≥0.5 目标仍未验证。
- 本任务不构成任何实验或 package 授权；是否升级硬件、是否签发新的单次 diagnostic preflight package
  完全由 Lead/Sol 决定，smoke 继续禁止。

有效身份（本任务未改任何文件，以下为上一审核基线，未变化）：

```text
runner:  4ee36556e0cf5ddefa9bed7cf753e5ca00cd13512c69d6600e18e101fe03b8f1
preflight: 0739418767fa19bc35ecd302d7feb5c8feebe9c2578f1ad733b28cf3ae840ccd
collector: 1685dcd64a442423fd3c00d4c1062e84e2fa667f01e2aee1009e195a7ad36eca
gt_mapper: c90383cb1083b554e50355405353d5a5e3ed3ce9a586a2d30962f8fc40a5c4e9
multi source-hash manifest: b275c3e06238b9e7a00653bd3b2439e893b47d947b7f085c64fa3974fb25c99a
static config: a0fb9077b67d48cf30ed233a886954966e57df331c73c3f8f2ffa6958b44faed
smoke manifest: 5cc07755cb46cfb13fda34fa96b9e528766340541c8eb919f62f7a000381e3c5
```

## 47. 当前 16 GB 主机（不升级硬件）的 2-UAV / 3-UAV 资源方案

用户意见（本会话）：**当前不能升级主机**；若四机不可行，最多考虑三机。本任务只做方案与离线
估算，未改任何源码/launch/config/manifest，未启动实验；四机结论先行记录：4-UAV 栈 RSS 预计
~10.2-11.0 GiB，MemAvailable 消耗 ~9.5-10.1 GiB，16 GB 下 running 余量不足 1 GiB 且启动瞬态
必触发 swap，**当前主机四机明确不可行**，故只给出 2-UAV 与 3-UAV 两套方案。

### 47.1 关键归因：上次失败是“残留 swap 页重读”，不是运行中新增换页

RUN-20260821T202125Z 数据（第 46 节已记录）：running 门失败时 `swap_in` 29491→29619
（+128 KB），而 **`swap_out` 全程保持 221,525 KB 未增长**。pswpout 不变说明本轮没有发生新的
换出；+128 KB swap-in 是**本 boot 早期（0.05 m 运行）被换出的页在本轮被触碰后重读**的残留债务。
这直接决定治理优先级：**消除历史 swap 债务（全新 boot）比加内存前的任何代码改动都更直接**。

当前主机只读状态（2026-08-22 检查）：`pswpin=0, pswpout=0, SwapFree=2,097,148 KB`
（主机已重启，残留 swap 债务已清零）；`MemTotal=15.42 GiB, MemAvailable≈10.28 GiB,
load1=0.74, nproc=20`；桌面负载合计 RSS ~5 GiB（firefox ~0.95 GiB、cursor 多进程 ~2.0 GiB、
wechat ~0.29 GiB、gnome-shell ~0.55 GiB、Xorg ~0.28 GiB 等）。

### 47.2 方案一：2-UAV（当前冻结范围，仅操作治理，零代码改动）

目标：让冻结的 `2uav_smoke` manifest 的 diagnostic preflight 在当前主机通过 running 资源门。

1. **运行前全新 boot 一次**，确认 `pswpin/pswpout=0`、SwapCached=0（清除残留 swap 页）。
2. **运行前关闭外部竞争负载**：firefox/cursor/wechat/gnome/Xorg 等（合计 RSS ~5 GiB），
   预期回收 MemAvailable 约 2-4 GiB；运行期间保持负载 1 < 3。
3. **保持全部 fail-closed 门不变**：startup MemAvailable≥8 GiB、load1<10；running
   MemAvailable≥3 GiB、swap_in/out 不增长。不做任何降门或参数放宽。
4. 预期（推算）：startup MemAvailable ≈ 14-15 GiB（≥8 GiB 门），running MemAvailable ≈
   8-9 GiB（较上次实测 6.41 GiB 提升 ~2-3 GiB），且无残留 swap 页可重读 → swap_in 保持 0
   → 有较高把握通过 running 门。残余风险：启动爬升瞬态（gazebo 0→5 GiB、racer 0→1.7 GiB）
   若瞬时触及换页仍会 fail-closed；需以一次诊断 preflight 实证。
5. 成功后：由 lead 决定是否按第 19 节最小修复后再签发 smoke；本方案本身不授权 smoke。

### 47.3 方案二：3-UAV（超出冻结范围，需 lead 批准扩大范围）

**内存推算**（per-UAV 增量取自 2-UAV 实测，按 92% MemAvailable 消耗/RSS 折算）：

```text
gazebo(3)   ≈ 4.93 + 1.0~1.2 = 5.9~6.1 GiB   (每 UAV: PX4 SITL+mavros+livox 模型数据)
racer(3)    ≈ 1.667 + 0.83   = 2.50 GiB
bridges(3)  ≈ 0.130 + 0.065  = 0.20 GiB
gt_mapper   ≈ 0.10 GiB (共享), collector ≈ 0.004 GiB
3-UAV 栈 RSS      ≈ 8.4~9.2 GiB (mid 8.8)
3-UAV MemAvail 消耗 ≈ 7.7~8.5 GiB (mid 8.1)
running MemAvailable (外部负载关闭、全新 boot, 基线≈1.5~2.0 GiB)
            ≈ 15.42 − 1.75 − 8.1 ≈ 5.6 GiB (范围 4.9~6.2) → 相对 3 GiB 门余量 ≈ 1.9~3.2 GiB
```

- **可行性结论：边界可行但风险高**。预算中值可过 3 GiB 门（余量 ~2.6 GiB），但启动瞬态
  （3×SITL + 3×mavros + gzserver + 3×exploration 同时爬升）会显著压低瞬时 MemAvailable，
  在 16 GB 上触碰换页的概率不低；且 3-UAV 每次实验消耗一个 package，失败成本高。
- **所需范围扩大**（当前全部不存在，需 lead 批准后才能创建/修改）：
  1. `config/3uav_static.yaml`（uav_count: 3；uav2：racer_id=3、sysid=3、
     fcu 14542:14582、mavlink_udp 14562、mavlink_tcp 4562、gst 5602、cam 14532；topics
     *_3、log_subdir uav2）；
  2. `launch/3uav_px4_sitl.launch`（uav2 group、tgt_system=3）、`launch/3uav_racer.launch`
     （exploration_node_3、drone_num=3、node_3 box 参数）、`launch/3uav_bridges.launch`
     （px4_bridge_3、/uav2、odom_3）；
  3. `experiments/manifests/3uav_smoke.yaml`（uav_count: 3、命令白名单、approval contract）；
  4. `scripts/two_uav_collector.py` 接触分类需支持 uav2/iris_2（第 30-49 行硬编码 uav0/uav1）；
     runner/preflight 的进程规格与 launch 路径需按 3uav 参数化。
- **建议实施顺序**（与 lead 商定后）：
  1. 先在 2-UAV 冻结 manifest 上完成 47.2 的实证（证明资源门行为可控）；
  2. 批准范围扩大到 3-UAV 后，先做 **3-UAV 静态检查 + 单次 diagnostic preflight**（同一组
     fail-closed 门），绝不可直接 3-UAV smoke；
  3. 若 3-UAV preflight 仍触发 swap 门或 MemAvailable 低于 ~4 GiB 瞬态，则 3-UAV 在
     16 GB 不成立，回退到仅 2-UAV。

### 47.4 不采用项（与 47.2/47.3 共用）

- 不降低资源门、不忽略 swap、不改 freshness/occupancy/安全合同；
- 不通过延迟 running 门检查或跳过启动爬升来“消化”瞬态内存；
- 不修改单机算法参数或 overlay（0.10 m 已是冻结基线）。

### 47.5 本任务身份

本任务未修改任何文件；下列 hash 与上一审核基线一致（sha256sum 复核）：

```text
runner:  4ee36556e0cf5ddefa9bed7cf753e5ca00cd13512c69d6600e18e101fe03b8f1
preflight: 0739418767fa19bc35ecd302d7feb5c8feebe9c2578f1ad733b28cf3ae840ccd
collector: 1685dcd64a442423fd3c00d4c1062e84e2fa667f01e2aee1009e195a7ad36eca
gt_mapper: c90383cb1083b554e50355405353d5a5e3ed3ce9a586a2d30962f8fc40a5c4e9
```

## 48. D1 runner dropout 事件（2026-08-23）

- 任务来源：`state/sol_plan_dropout.md` 第 3 节；高终端即时交接已签发。
- 范围：**只实现 runner 级 dropout 事件，manifest 保持 `enabled: false`（D1 只解析不触发）**；
  不启动实验、不改安全门、不临时 kill、不 commit/push。
- 允许写入：`scripts/two_uav_runner.py`、`experiments/manifests/2uav_smoke.yaml`（仅增加
  `dropout:` 段）、`state/terra_implementation.md`、`state/events.jsonl`（追加）。

### 48.1 修改内容

`scripts/two_uav_runner.py`：

1. `parse_dropout_config(manifest)`：解析 `dropout:` 段（`enabled/vehicle/mode/trigger_sim_s/
   cleanup_policy/record`），缺失或非法字段 fail-fast；无 `dropout` 段返回 `None`（向后兼容）。
2. `dropout_target_nodes(config, dropout_config)`：纯映射 vehicle+mode → 待 kill 的 ROS 节点：
   - `control_chain` 与 `node_level`：`/px4_bridge_{racer_id}`、`/exploration_node_{racer_id}`、
     `/traj_server_{racer_id}`；
   - `communication`：仅 `/px4_bridge_{racer_id}`。
   - racer_id 来自 `config/2uav_static.yaml`（uav0→1、uav1→2），与 launch 接线一致。
3. `dropout_due(dropout_config, elapsed_sim_s, triggered)`：纯一次性触发判定（enabled 且未触发
   且 elapsed_sim_s ≥ trigger_sim_s）。
4. `rosnode_pid()` / `rosnode_kill()`：通过 `rosnode info`/`rosnode kill` 的白名单 runner 事件，
   不执行裸 shell kill。
5. `execute_dropout(runroot, dropout_config, config, sim_s=None, ...)`：执行注入并写
   `fleet/dropout.json`（`vehicle/mode/trigger_sim_s/sim_s/wall_s/pids/killed_nodes/missing_nodes/
   cleanup_policy/record/reason=intentional_dropout`）。
6. `monitor_until(active, duration_sim_s, dropout_config=None, config=None, ...)`：在
   `monitor_until` 循环中按相对 sim 时间到达 `trigger_sim_s` 时触发一次 dropout，之后
   `dropout_triggered=True` 禁止重复触发；abort/process-death 路径保持活跃。
7. `action_launch()`：解析 manifest dropout 配置并传给 `monitor_until`；
   `action_preflight()`：解析并 fail-fast 校验（拒绝非法配置，不消耗 package）。

`experiments/manifests/2uav_smoke.yaml`：增加 `dropout:` 段（`enabled: false`），供 D3
rehearsal 使用（届时由高终端改为 `enabled: true`）。

### 48.2 验证证据（未启动实验）

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio-pyc-d1 python3 -m py_compile scripts/two_uav_runner.py
py_compile PASS
PYTHONPYCACHEPREFIX=/tmp/swarmlio-pyc-d1 python3 scripts/two_uav_runner.py --self-test
two_uav_runner self-test: PASS（含 dropout 解析 fail-fast、target 映射、dropout_due 一次性判定、
execute_dropout 落盘 fleet/dropout.json、monitor_until 触发/禁用/一次性/向后兼容）
git diff --check scripts/two_uav_runner.py experiments/manifests/2uav_smoke.yaml
PASS（无 trailing whitespace）
```

### 48.3 新 hash（D1 后）

```text
runner:  c64c46c610f45ec3258aaf24716c7fa80c78f31805134bd3ff9cfcf328169c4b
smoke manifest: ae21426cb3a62761dc8650cebc6d10626a4089802a7e4efb62b100dac37fd4ef
```

### 48.4 语义说明与残余风险

- 触发时机按 `monitor_until` 循环内的相对 sim 时间（`current_sim_s - start_sim_s ≥
  trigger_sim_s`），即「进入 command 链/soak 完成后」的 elapsed sim 时间，与工作流 0.3 的
  「起飞稳定 + 进入 command 链之后 ≥ 30 sim-s」一致。
- kill 的是 ROS 节点（bridges/racer roslaunch 的子进程）；这些进程树仍被 `active["processes"]`
  追踪，`stop_active` 的 descendant 闭包会回收掉线机残余节点，不会成为 survivors。
- `communication` 模式只 kill bridge；`control_chain` 与 `node_level` 目前 kill 相同的三个节点，
  差异体现在语义分类与后续 D4 的分类强化上，由 D0 语义层界定。
- 残余风险：`rosnode kill` 依赖 ROS master 可达；若掉线机的节点已不在 `/rosnode list`，会记为
  `missing_nodes` 而不算失败。D1 阶段 manifest 为 `enabled: false`，任何 launch/preflight 都
  不会实际触发 dropout。

## 50. D1 返工：control_chain 保留 px4_bridge（无实验）

按高终端返工指令修正 `dropout_target_nodes()` 的 D0 模式语义：

- `control_chain`：仅 kill `/exploration_node_{racer_id}` 与 `/traj_server_{racer_id}`；保留
  `/px4_bridge_{racer_id}`，使机体仍可飞/悬停；
- `communication`：仍仅 kill `/px4_bridge_{racer_id}`；
- `node_level`：仍 kill bridge、exploration、traj 三节点。

同步更新 runner self-test 与 `execute_dropout()` 断言，确保 control_chain 的目标节点、PID
记录和 `killed_nodes` 均不包含 bridge。未启动实验、未创建或消费 approval package、未 commit/push。

验证：

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio-pyc-r1 python3 -m py_compile scripts/two_uav_runner.py
PASS
PYTHONPYCACHEPREFIX=/tmp/swarmlio-pyc-r1 python3 scripts/two_uav_runner.py --self-test
PASS
git diff --check scripts/two_uav_runner.py
PASS
```

runner 返工后 SHA-256：`fa9ce9f9fe057bc8fd07b608532ee7d15b6c4cd021e5198536f60fae732f345b`。

## 49. D2 collector dropout classification v1（中终端）

- 日期：2026-08-23
- 任务来源：`state/sol_plan_dropout.md` 第 4 节
- 允许写入：`scripts/two_uav_collector.py`、`state/terra_implementation.md`、`state/events.jsonl`（追加）。
- 实现结论：`D2_COLLECTOR_DROPOUT_CLASSIFICATION_V1`

### 49.1 修改内容

`scripts/two_uav_collector.py`：

1. 新增 `dropout_classification(vehicle_name, dropout_record, liveness, snapshot, active)`：
   - `intentional_dropout`：runroot 中存在 `fleet/dropout.json` 且 vehicle 名称匹配；
   - `unexpected_loss`：未见 dropout 记录但 active 期出现 liveness 断裂；
   - `telemetry_missing`：进程仍 live，但 telemetry/channel 出现 stale/missing；
   - `none`：无异常或 teardown 期。
2. 新增 `apply_dropout_report(report, dropout_record)`：将被 drop 的 UAV 标记为
   `dropout=true`、`dropout_classification=intentional_dropout`、`dropout_mode`、
   `dropout_sim_s`，并写入 `telemetry_dropout_breakpoint_sim_s`；
   dropped UAV 的 `freeze/crash` 被清零，`ack_timeout` 视为 fault 结果而非安全故障。
   `telemetry_complete` 对 dropped UAV 语义化为 `dropout_expected`。
3. `VehicleState` 扩展：
   - 记录 `last_command_position` / `last_command_wall_s`；
   - snapshot 新增 `hold_at_goal`；
   - 佔位 telemetry 字段扩展为 `occupancy_received/processed/coalesced`、
     `last_*`、`callback_wall_duration_s`、`processing_wall_duration_s`，以支持掉线后审计。
4. freeze 判定修复：当 `pos_cmd` 在最近 15 s 仍活跃且 UAV 已停在最近命令位置附近时，
   不再误标 `freeze`。这直接修复 RUN-20260822T173640Z 中 uav1 晚期悬停误标。
5. `Collector` 扩展：
   - 读取 `fleet/dropout.json` 并缓存；
   - dropped vehicle 的 freshness / ack / tf / topic-owner / contact / crash / freeze 判定跳过；
   - `contact` 仅对非 dropped vehicle 执行安全判定；
   - `TF` / topic owner 失效仅对未掉线车辆触发 abort；
   - `report()` 中为 dropped vehicle 写入掉线分类并在 fleet metrics 中附加 `dropout`
     与 `dropout_classifications`；
   - `vehicle_reports` 保持向后兼容。

### 49.2 语义核验

- 读取 `fleet/dropout.json` 作为 intentional dropout 的唯一来源；
- dropped UAV 维持 `dropout=true` / `dropout_mode` / `dropout_sim_s`，并在 telemetry 中保留
  `telemetry_dropout_breakpoint_sim_s`，便于后续报告区分 intentional dropout vs unexpected loss；
- 监视期的 crash/freeze/contact 不再把已掉线车辆误判成安全故障；
- 其余未掉线车辆仍按原安全门 fail-closed。

### 49.3 验证证据（未启动实验）

```text
PYTHONPYCACHEPREFIX=/tmp/swarmlio-pyc-d2 python3 -m py_compile scripts/two_uav_collector.py
py_compile PASS
PYTHONPYCACHEPREFIX=/tmp/swarmlio-pyc-d2 python3 scripts/two_uav_collector.py --self-test
self-test PASS（含 intentional_dropout / unexpected_loss / telemetry_missing / none 分类，
freeze 联合 pos_cmd 活跃判定，apply_dropout_report 覆盖）
git diff --check scripts/two_uav_collector.py
PASS（无 trailing whitespace）
```

### 49.4 新 hash（D2）

```text
collector: cb2443adfa61d27edd28e4ab8b98222bce9fa920f9570e6890ebad07df42a02c
```

### 49.5 残余风险

- `telemetry_complete` 对 intentional dropout 语义化为 `dropout_expected`，与原布尔语义不同；
  该值用于后续 D3/D4 报告，现阶段仍兼容既有 2-UAV 非 dropout metrics。
- `rosnode` / `rosgraph` 探针在 ROS master 不可达时仍 fail-closed 为 telemetry/owner 相关异常，
  但 intentional dropout 场景下的掉线机相关 checks 已被隔离，不会误杀 surviving UAV。
- 当前未运行 D3 rehearsal；因此这些 classification 分支只通过 self-test 和静态 diff 证据验证。

## 51. D4 分类强化 + 报告字段（有 D3 runroot 可验证）

- 任务来源：`state/dropout_experiment_plan.md` D4（collector 分类强化 + 报告字段）
- 允许写入：`two_uav_collector.py`、`two_uav_runner.py`（仅分类自检）、terra、events
- 验证输入：D3 正式 runroot `results/RUN-20260823T070849Z-2uav-smoke/`（返工后
  control_chain，kill exploration_node_2+traj_server_2，sim_s=90.14）；
  对照 runroot `RUN-20260823T063342Z-2uav-smoke/`（旧 control_chain，含 px4_bridge_2）。

### 51.1 修改内容

`scripts/two_uav_collector.py`：

1. `dropout_classification(..., vehicle_nodes=None)`：强化 unexpected_loss 归因——只有当
   liveness `lost_after_seen` 包含**该机自己的节点**（px4_bridge/exploration/traj 按
   racer_id）才判 unexpected_loss；其它机节点死亡不再误伤本机分类。
2. `_load_dropout_record()`：强化记录有效性——必须含 `vehicle`（str）且 `mode`（非空 str）
   且 `sim_s`（非 bool 数字），否则不视为 intentional_dropout 依据。
3. 新增 `dropout_continue_evidence(baseline, report, dropped=False)`：纯函数，输出
   `{"continued": bool|None, "coverage_delta": int|None}`——幸存机在 dropout 基线后
   有 coverage/telemetry/path 任一增量即 `continued=True`；dropped 机恒为
   `{continued: False, coverage_delta: None}`。
4. `Collector` 新增 `dropout_baseline` 与 `_capture_dropout_baseline()`：首个看到
   dropout 记录的 report 时快照每机 coverage_voxels/path_length/ack/pos_cmd/odometry。
5. `report()`：fleet metrics 新增（仅 dropout 场景出现）：
   - `surviving_uavs_continue`：每机 `{"uav0": true, "uav1": false}`；
   - `post_dropout_coverage_delta`：每机 coverage 增量（dropped 为 null）。

`scripts/two_uav_runner.py`（仅 self-test）：新增 D4 分类自检——对三种 mode 各执行一次
`execute_dropout`，断言记录含 collector 分类消费字段（vehicle/mode/sim_s/reason）且
`killed_nodes` 与该 mode 的 `dropout_target_nodes` 完全一致（control_chain 不含
px4_bridge、communication 仅 bridge、node_level 三节点）。

### 51.2 验证证据（未启动实验）

```text
collector: py_compile PASS / self-test PASS / git diff --check PASS
runner:    py_compile PASS / self-test PASS（含 D4 三 mode 分类自检）/ git diff --check PASS
```

D3 runroot 只读验证（D4 指标语义，非实验）：

```text
dropout vehicle=uav1 mode=control_chain sim_s=90.14
uav0 final coverage=7227  baseline@dropout≈4861  post_dropout_delta=2366 continued=True
uav0 coverage first=0 last=7227 samples=70
```

### 51.3 新 hash（D4）

```text
collector: 1e029f55dac22d500564dc4ce38caf5bec8bc8419d56763e5dd3335e803b2460
runner:    aca7cbd2f91ec37c57f6a4d1a9514ee091ce46124b84fd29dc7ec0e64878b90b
```

### 51.4 残余风险

- `surviving_uavs_continue` 的 baseline 取「collector 首个看到 dropout.json 的 report」，
  与 runner 触发时刻相差一个 flush 周期（≤2 s），coverage delta 存在 ≤1 个 snapshot 的
  近似误差；仅用于报告，不影响 fail-closed 门。
- 对照 runroot（063342Z）是旧 control_chain（kill 含 px4_bridge_2）；与正式 runroot
  （070849Z）不可直接按 coverage 对比，D4 只用于验证分类字段齐全，不改变安全门。

## 52. D5 三机参数化（uav_count 由 config.vehicles 驱动，2-UAV 向后兼容）

- 任务来源：`state/dropout_experiment_plan.md` D5
- 允许写入：`two_uav_runner.py`、`two_uav_collector.py`、`two_uav_preflight.py`、terra、events
- 目标：把双机硬编码改为 config.vehicles 列表推导；2-UAV 行为不变；self-test 覆盖 uav_count=2 与 =3

### 52.1 修改内容

`scripts/two_uav_runner.py`：

1. 新增 `config_vehicle_names()` / `config_bridge_nodes()` / `vehicle_metrics_summary()`
   （全部由 `config.vehicles` 推导）。
2. `process_specs()`：launch 文件由 `uav_count` 派生前缀（`2uav_*.launch` / `3uav_*.launch`），
   2-UAV 路径不变。
3. `make_runroot()`：runroot 目录 = 每机目录 + `fleet` + `logs`；runroot 名
   `RUN-…-{n}uav-{kind}`。
4. `start_stack()`：bridges/racer readiness 的 `required_nodes` 用 `config_bridge_nodes()`。
5. `watchdog_evidence()` / `wait_final_metrics()` / `final_safety_result()`：
   车辆列表改为 `config_vehicle_names()`。
6. `smoke_command_chain_valid(vehicles, expected_names=("uav0","uav1"))`：N 机通用，
   默认值保持 2-UAV 契约与既有 self-test。
7. `action_launch` / `action_collect`：summary 用 `vehicle_metrics_summary()`（2-UAV 时
   仍是 `uav0_metrics`/`uav1_metrics` 键，向后兼容）。

`scripts/two_uav_collector.py`：

1. `vehicle_alias_map(config)`：collision 名称 → vehicle（uavN / iris_<racer_id-1>），
   `vehicle_names`/`contact_category` 接受 `alias_map`（默认 2-UAV 契约不变）。
2. `pairwise_fleet_metrics(maps)`：任意机数下取**最小** pairwise overlap/jaccard（2 机时
   与原单对结果一致）；fleet `union` 改为 `set().union(*maps)`。
3. `_odom_cb`：最小机间距改为全部机对 `itertools.combinations` 计算。
4. `expected_nodes` 由 config.vehicles 推导；`_contact_cb` 使用 config 派生的 alias map；
   `main()` 目录循环由 config.vehicles 驱动。

`scripts/two_uav_preflight.py`：

1. `contract.uav_count` 校验改为「uav_count 为 int、≥2、且等于 vehicles 数量」。
2. launch XML 检查路径、`expected_bounds`（drone_id 由 vehicles 的 racer_id 推导）、
   `drone_num == str(uav_count)`、approval package 路径
   （`state/{n}uav_approval.yaml`）、source hash manifest
   （`config/{n}uav_source_hashes.sha256`）、source_files 全部由 `launch_prefix` 派生。
3. self-test 增加 uav_count=3 的 TF contract 覆盖（vehicle-list 驱动）。

### 52.2 验证证据（未启动实验）

```text
two_uav_runner    self-test: PASS（新增 3 机 smoke_command_chain / config 辅助 3 机断言）
two_uav_preflight self-test: PASS（新增 uav2 TF contract 用例）
two_uav_collector self-test: PASS（新增 alias map uav2 / pairwise metrics 3 机用例）
py_compile（三脚本）: PASS
git diff --check: PASS
```

### 52.1b preflight 附带健壮性强化（同批验证，经高终端审核后补录）

`scripts/two_uav_preflight.py` 与 D5 参数化同文件包含以下健壮性强化（D4 审核时已
存在于工作区，随 D5 一并验证提交）：

1. `FROZEN_RUNTIME` 增补 `sdf_map/resolution` 与 `map_ros/all_map_publish_period` 检查项；
2. `readonly_cli_retry()`：live 期只读 ROS CLI（rosparam 等）带 3 次退避重试 + 50 s
   wall cap，替代单次 `subprocess.run`，缓解 ROS master 偶发拥塞导致的误判；
3. `runtime_value_matches()`：rosparam 输出数值归一比较（`0.1` == `0.10`），
   修正字符串字面比较误报；
4. `resource_profile_schema_valid()`：live 检查新增 `resource_usage.jsonl` 首样本
   schema 校验；
5. watchdog 契约补强 `occupancy_contract` / `coverage_coalesce_sim_s` /
   `resource_*` 门限检查。

以上均为只读/校验层增强，不改变安全门阈值语义，self-test 全覆盖。

2-UAV 向后兼容核对：`process_specs`/`make_runroot`/`start_stack`/metrics 汇总键/
preflight 校验路径在 uav_count=2 时逐一与原实现一致。

### 52.3 新 hash（D5）

```text
runner:    1ca6f9c5833de66b53c1f621180c7e66d2ba3c44809877c21482b7918e83d636
collector: 20a1832b89c6c6425d15ef948423e38e020f29da82ee32d5fb5a72f7629806b2
preflight: 41f0c76913532c4d184162d787055ec49155d9ba6272690c96d687b0c52be1aa
```

### 52.4 残余风险

- 三机启动本身需要 D6 的 `config/3uav_*.yaml`、`launch/3uav_*.launch`、3uav 世界与
  source hash manifest 就位后才能实证；本阶段只保证脚本层参数化与 self-test 覆盖。
- 3-UAV 时 fleet 的 `overlap_ratio`/`map_consistency_jaccard` 取最小 pairwise 值，语义与
  2-UAV 的「单对」一致且更保守；若后续需要全对报告可在 D6 扩展。

## 53. D6 3-UAV 资产新建（config/launch/manifest/hash，2-UAV 冻结文件未动）

- 任务来源：`state/dropout_experiment_plan.md` D6
- 约束：只新建 3uav 资产；禁止修改 2-UAV 冻结文件；未启动实验。

### 53.1 新建资产（7 个文件）

1. `config/3uav_static.yaml`：`uav_count: 3`、`contract_id: range20m_omnidirectional_3uav_static_v1`；
   新增 uav2（namespace `/uav2`、racer_id 3、mavlink_system_id 3、
   端口 14542/14582/14562/4562/5602/14532、初始位姿 `[-3.0, 3.0, 0.0]` 避开 uav0/uav1 及
   建筑/墙体/柱体）；uav0/uav1 字段与 2uav 契约逐项一致。
2. `launch/3uav_px4_sitl.launch`：复用 2uav 模板，新增 uav2 group（ID=2、spawn
   `-3.0 3.0 0.0`、mavlink 14562/4562、gst 5602、cam 14532、fcu `udp://:14542@localhost:14582`、
   tgt_system 3）。
3. `launch/3uav_bridges.launch`：新增 `px4_bridge_3`（drone_id 3、mavros_ns `/uav2`、
   init_pos `[-3.0, 3.0]`、odom `/mavros_relay/odom_3`）。
4. `launch/3uav_racer.launch`：新增 drone_id 3（drone_num 3、init `-3.0 3.0 0.0`）与
   `/exploration_node_3/sdf_map/box_*` 边界参数。
5. `experiments/manifests/3uav_smoke.yaml`：`experiment_id: three_uav_smoke_v1`、
   `uav_count: 3`、`duration_sim_s: 120`、dropout 段（uav1/control_chain/trigger 60/
   stop_active_reclaim，沿用 2uav 语义）。
6. `config/3uav_approval_contract.yaml`：同 2uav 契约，`approval_package: state/3uav_approval.yaml`
   （approval package 本身由高终端在 preflight/smoke 时签发）。
7. `config/3uav_source_hashes.sha256`：新 source-hash manifest（脚本复用 2uav 的
   validate_2uav_outdoor_world.py / 2uav_outdoor_50x50_v1.world 共享资产，hash 与当前
   工作树一致）。

world 评估结论：`2uav_outdoor_50x50_v1.world` 无 UAV 模型/出生点（spawn 由 px4_sitl
launch 注入），50×50 内可放置第三机位姿，**无需新建 world**。

### 53.2 验证证据（未启动实验）

```text
python3 scripts/two_uav_preflight.py --mode static \
  --config config/3uav_static.yaml --manifest experiments/manifests/3uav_smoke.yaml
passed: true，55 项检查全部 ok（uav_count/isolation 三机、3uav launch XML、
wiring.uav2_bridge/racer/px4、approval contract、source.multi_hash_manifest 全部匹配）

py_compile + self-test（runner/preflight/collector）: 全部 PASS（D6 无脚本改动，回归通过）
git diff --check: PASS
2-UAV 冻结文件：未修改（config/2uav_static.yaml 的工作树改动为 D6 之前既有变更）
```

### 53.3 新资产 hash

```text
config/3uav_static.yaml:              c307d66070a57fdb23d1a6f38e72d950da941e9d7f8caab7f6cfc5c4027fc406
config/3uav_approval_contract.yaml:   d57b9f8675a752128dddc97965639a1d2ca33fe6a42f5e9ede520716ec646143
config/3uav_source_hashes.sha256:     f8b2a8a078c4f42125456a7d0afc78902b4b85ab7da1b57a2876427694300af9
launch/3uav_px4_sitl.launch:          a79f9c9e8e84dcb8ed76221ddaa59f8af3dac632291f5f5237de432388afd6ab
launch/3uav_bridges.launch:           5c6fdf8837c83841623f9c98527966ade9d60c0f009ffc58800aaf4d07ff6eb3
launch/3uav_racer.launch:             bec4e99d0b27931561154a3ce2b9746534a4437f4dbef87c069df2e1dbc41cf1
experiments/manifests/3uav_smoke.yaml: 2232cb58445e7bd765e9747443dd3296532fd10a8f3afd0ae1e8fad6262ef26b
```

### 53.4 残余风险

- `state/3uav_approval.yaml` 尚未签发（由高终端在 preflight/smoke 时按契约签发）。
- runner 的 `CONFIG`/`ACTIVE` 全局仍指向 2uav；3-UAV 实跑需要 D7 让 runner 从 manifest
  `static_contract` 解析 config（脚本层已由 D5 参数化，实例化尚缺）。
- gt_mapper `load_contract` 仍要求 `uav_count == 2`（2uav 冻结脚本），3-UAV 实跑前需
  单独评审其参数化；本次未改。

## 54. D7 runner CONFIG 实例化 + gt_mapper uav_count 泛化（>=2）

- 任务来源：`state/dropout_experiment_plan.md` D7（3-UAV static 校验 + self-test 前置）
- 目标：runner 从 manifest `static_contract` 派生 config/approval/source-hash 路径；
  gt_mapper 支持 uav_count>=2；恢复 git HEAD 与 source hash manifest 一致性。

### 54.1 修改内容

`scripts/two_uav_runner.py`（CONFIG 实例化）：

1. 新增解析器：`manifest_static_config_path(manifest)`（static_contract →
   `config/Nuav_static.yaml`）、`manifest_approval_contract_path(manifest)`、
   `approval_package_path(contract)`（contract 的 approval_package → `state/Nuav_approval.yaml`）、
   `source_hashes_for_config(config_path)`（`config/Nuav_static.yaml` →
   `config/Nuav_source_hashes.sha256`）、`runroot_config_path(runroot)`（runroot 内
   `static.yaml` → `2uav_static.yaml` → manifest 派生，最后回退默认 CONFIG）。
2. `approval_guard` / `verify_source_hashes`：contract/package/hash manifest 全部由
   manifest 派生（2-UAV 路径不变）。
3. `process_specs` / `make_runroot` / `start_stack`：gt_mapper/collector 的 `--config`
   与 static_checks 用 manifest 派生的 config；runroot 拷贝改名为 `static.yaml`
   （旧 runroot 的 `2uav_static.yaml` 仍被 `runroot_config_path` 兼容读取）。
4. `watchdog_evidence` / `wait_final_metrics` / `final_safety_result` /
   `action_preflight` / `action_launch` / `action_collect`：config/车辆列表按
   runroot 或 manifest 解析。
5. `parse_dropout_config(manifest, config_path=None)`：无显式 config_path 时从
   manifest 的 `static_contract` 派生（self-test 的裸 dict 仍回退默认 2uav）。

`scripts/two_uav_gt_mapper.py`（uav_count>=2）：

1. `load_contract`：`uav_count` 为 int、>=2 且等于 `vehicles` 长度。
2. 新增 `multi_peer_body_filter`：单 peer 时与 `peer_body_filter` 逐字节一致；
   多 peer 时 endpoint/inflation/ray mask 累加计数并对移除 mask 取并集。
3. `VehicleMapper` 接受 `peer_names`（可迭代）；`main()` 以「其它所有车辆」作为每机
   peers；provenance recorder（741 行遗留实现）保持 2-UAV 冻结键语义不变。
4. self-test：单 peer 等价性、双 peer 并集、缺失 peer 降级、3uav contract 加载、
   uav_count=1 拒绝。

### 54.2 source hash manifest 更新（恢复 HEAD↔manifest 一致性）

`config/2uav_source_hashes.sha256` 与 `config/3uav_source_hashes.sha256` 的四个脚本条目
更新为当前工作树 hash（gt_mapper 含 provenance recorder + D7 泛化）：

```text
runner:    4eff30e5003e98b261c70d1cfdd1d5defedbd8e57a5d6fbe5665b698334420aa
gt_mapper: ead7324d68fa69b00df6a44d90532be758d91538c1e467d1023d2259c0a8c23c
preflight: 41f0c76913532c4d184162d787055ec49155d9ba6272690c96d687b0c52be1aa
collector: 20a1832b89c6c6425d15ef948423e38e020f29da82ee32d5fb5a72f7629806b2
```

### 54.3 验证证据（未启动实验）

```text
2uav static preflight: passed=true，54/54 ok（含 source.multi_hash_manifest 匹配）
3uav static preflight: passed=true，57/57 ok（含 source.multi_hash_manifest 匹配）
py_compile（四脚本）: PASS
self-test（runner/preflight/collector/gt_mapper）: 全部 PASS
git diff --check: PASS
approval 路径解析（2uav/3uav）: verify_source_hashes OK
```

### 54.4 新 hash（D7）

```text
runner:    4eff30e5003e98b261c70d1cfdd1d5defedbd8e57a5d6fbe5665b698334420aa
gt_mapper: ead7324d68fa69b00df6a44d90532be758d91538c1e467d1023d2259c0a8c23c
2uav hashes manifest: aa4ca5660c5f81de0b1d634fccbdd4ff15c32b8ff0447b14857ee126aea0c02a
3uav hashes manifest: c3f11e561d3b1160d6d06701b83068ba887f29637ae4601f949fc4a3c59b587e
```

### 54.5 残余风险

- `state/3uav_approval.yaml` 仍未签发；D7 提交后 HEAD 的 gt_mapper（含 provenance
  recorder）与两个 hash manifest 一致，后续修改任一冻结脚本必须同步更新 manifest。
- `VehicleMapper` 的 provenance recorder 键（`uav1_hover_voxels` 等）仍为 2-UAV 语义；
  3-UAV 实跑时 provenance 以 peer_names[0] 记录，属已知受限（不影响注册/发布/控制）。


