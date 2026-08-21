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
