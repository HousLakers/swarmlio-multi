# 单机 20 m 全向候选到多机的正式交接包

日期：2026-08-20
交接状态：`READY_FOR_MULTI_INTEGRATION / NOT_APPROVED_FOR_EXPERIMENT`

本文件是进入多机工作时的首要任务包。它只批准静态导入、源码接入和 2-UAV
preflight 准备，不批准启动 2-UAV smoke，更不批准多机长跑。

## 1. 冻结输入

| 项目 | 冻结身份 |
|---|---|
| 公共环境仓库 | `https://github.com/HousLakers/racer-platform.git` |
| 公共环境 commit | `57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc` |
| 单机配置仓库 | `https://github.com/HousLakers/swarmlio-single.git` |
| 单机配置 commit | `c01f1f5af40ec25631aa11765a0f21e06834abc4` |
| 节点候选 | `platform_overlays/range20m_omnidirectional_v1` |
| overlay manifest SHA-256 | `80d0d06a5a9b3722804c28d3efc6ace9a71d5955b26f8124e12bf3579e0d9529` |
| overlay installer SHA-256 | `7e2280d5d0ba88ee501764ab5b5ccc3f3724d5b6abf39704badc7a8976349151` |
| 多机编排仓库交接前 commit | `41879e8ccea783895965831f75646ac2a6a43ed7` |

本机多机目录实际为
`/home/houslakers/auto_tune_racer/swarmlio_multi`，目录名使用下划线；远程仓库名仍是
`HousLakers/swarmlio-multi`。脚本和交接记录不得混用这两个名字。

## 2. 单机证据及其边界

有效短 smoke：
`swarmlio-single/results/RUN-20260819T142427Z-range20m-omnidirectional-gate-smoke-v8/`。
它完成 60.20 simulated seconds，记录 608 个 odometry 样本、11.94 m 路径、
72.94% coverage、ATE RMSE 0.0802 m、P10 clearance 1.898 m；crash、freeze、
contact、live-vehicle inflated-A*、ACK timeout、invalid SDF 和 process death 均为 0。

功能长测：
`swarmlio-single/results/RUN-20260819T143725Z-range20m-omnidirectional-endurance-3h/`。
用户在约 1768 simulated seconds 主动停止。运行在约 1076 s 达到 97.56%
coverage，累计路径 183.32 m、轨迹 ID 1–122；RACER 在 958.016 s 报告
`No coverable frontier`，之后驻留不判为 freeze。6 次稳态 1 s ACK timeout 均恢复，
但它们仍是多机必须重新设门并逐机计数的风险。人工停止导致最终 scorer metrics
缺失，因此正式结论只能是：

```text
FUNCTIONAL_VALIDATION_PASS / FORMAL_ENDURANCE_INCOMPLETE
```

这些证据只允许把 20 m 水平全向配置作为每架 UAV 的节点候选；它们不证明
fleet coverage、重叠率、负载均衡、地图一致性、通信鲁棒性或机间安全。

## 3. 导入顺序

推荐在同一父目录内保留三个并列仓库：

```text
auto_tune_racer/
├── racer-platform/
├── swarmlio-single/
└── swarmlio_multi/
```

先按 `PLATFORM_ENVIRONMENT.md` 重建并检出公共环境，再检出冻结的单机仓库：

```bash
git clone https://github.com/HousLakers/racer-platform.git
git -C racer-platform checkout 57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc

git clone https://github.com/HousLakers/swarmlio-single.git
git -C swarmlio-single checkout c01f1f5af40ec25631aa11765a0f21e06834abc4
```

在 `swarmlio-single` 根目录先只读验证。`--check` 返回 3 且显示
`NEEDS_APPLY` 表示平台已导入但 overlay 尚未安装，并非包损坏：

```bash
RACER_PLATFORM_ROOT=../racer-platform \
  scripts/apply_range20m_omnidirectional_overlay.sh --verify-bundle

RACER_PLATFORM_ROOT=../racer-platform \
  scripts/apply_range20m_omnidirectional_overlay.sh --check
```

确认目标和备份位置后才允许安装；安装会为被替换文件建立 append-only 备份：

```bash
RACER_PLATFORM_ROOT=../racer-platform \
SWARMLIO_ALLOW_PLATFORM_OVERLAY=yes \
  scripts/apply_range20m_omnidirectional_overlay.sh --apply

RACER_PLATFORM_ROOT=../racer-platform \
  scripts/apply_range20m_omnidirectional_overlay.sh --check
```

随后按公共平台合同重编译 Swarm-LIO 与 RACER，并从单机仓库执行只读配置探针：

```bash
python3 scripts/prepare_single_uav_lidar_range_profile.py \
  --profile range20m-omnidirectional --check
python3 scripts/test_nearfield_map_fix.py
python3 scripts/test_startup_map_bound_fix.py
```

overlay 的 21/21 hash 正确只证明源码/config 一致；重编译、ROS package 解析和
runtime 参数回读仍必须分别通过。不得把旧 build/devel 二进制当作重建证据。

## 4. 多机接入任务包

### 目标

在不修改已冻结单机算法参数的前提下，为 UAV0/UAV1 建立可审计的 2-UAV
preflight 和短 smoke 入口；先证明两个节点身份、消息链和安全记录完全隔离。

### 允许写入

- `swarmlio_multi` 内的 launch/runner/preflight/collector 脚本；
- `experiments/manifests/2uav_smoke.yaml`；
- 每轮开始前的 `state/sol_plan.md`、`state/terra_implementation.md` 和
  `state/sol_approval.md`；
- 新的 append-only `results/RUN-*`，但只能由 DeepSeek 按批准 manifest 生成；
- RACER/Swarm-LIO 中纯多机 namespace、remap、vehicle identity 接线；如需改动，
  Terra 必须列出 diff 和静态/编译证据，且不得同时有第二个源码写入者。

### 禁止事项

- 不得改动 20 m 视距、水平 360°、near-field、A* 分类、startup/ACK 语义；
- 不得在首轮同时引入通信延迟、丢包、动态分区或参数搜索；
- 不得混用 GT 与 LIO 注册结果；首轮保持冻结的 GT 同步注册语义；
- 不得复用 namespace、vehicle ID、MAVLink/ROS 端口、TF child frame 或日志目录；
- 不得让一架 UAV 的 completion/freeze 覆盖另一架状态；
- 2-UAV preflight 未通过不得执行 smoke；smoke 未经 Luna 审核和 Sol 收尾不得长跑；
- 不得提交原始大日志、点云、build/devel/install 或密钥。

## 5. 2-UAV preflight 硬门

所有项目必须有机器可读证据，任一失败即保持 `approved: false`：

1. 三个冻结身份和两个 overlay SHA-256 回读一致，工作树 diff 已记录；
2. UAV0/UAV1 的 namespace、初始位姿、vehicle/system ID、ROS/MAVLink 端口唯一；
3. `/clock` 唯一且单调，两个节点使用相同 simulated time；
4. odometry、cloud、map、frontier、trajectory、pos_cmd、ACK、contact 和 health
   topic 均可归属到唯一 UAV；
5. TF 树无重复 child frame、无跨 UAV parent 串线、无持续 extrapolation；
6. 两架 UAV 分别具有独立日志和结果子目录，停止一架不会覆盖另一架结果；
7. 每架分别记录 completion、freeze、crash、contact、coverage、telemetry 和 ACK；
8. fleet 侧记录 coverage、overlap ratio、minimum inter-UAV distance、contact count、
   map consistency、任务分配状态和进程存活；
9. abort 路径能在 crash、严重接触、telemetry 损坏、namespace/TF 串线时停止全局运行，
   同时保留已生成的 append-only runroot；
10. 启动、监控、停止、采集命令均被列入 manifest 白名单，且没有占位符。

## 6. 首轮 2-UAV smoke 的固定范围

当前建议仍是 2 UAV、120 simulated seconds、1 次、seed `20260814`、shared async
map、static partition、0 ms 人工通信延迟。它只是链路和安全 smoke，不是性能对比。

首轮成功至少要求：

- UAV0/UAV1 都完成 startup 并持续产生完整 telemetry；
- 两架分别有实体运动或由 manifest 预先定义的有效完成状态；
- 两架均无 crash、freeze、严重 contact、live-vehicle inflated-A* 和 process death；
- ACK timeout 必须逐机记录；是否允许“随后恢复”必须由 Sol 在运行前明确写入合同，
  不得沿用单机长测的人工解释；
- fleet coverage、overlap、最小机间距离和地图一致性均成功落盘；
- 退出原因明确，scorer 正常写出最终 metrics，任何缺失均判无效运行。

当前 `experiments/manifests/2uav_smoke.yaml` 故意保留
`REPLACE_WITH_VERIFIED_2UAV_LAUNCH_COMMAND`，所以实验尚未获批。只有 Terra 完成接线
和证据、Sol 审核并生成 approval 后，才能由 DeepSeek 执行白名单命令。

## 7. 角色交接顺序

```text
Lead/Sol 冻结任务范围
  → Terra 接入并提交 diff/编译/静态 preflight 证据
  → Sol 审核 manifest 与白名单并决定是否批准
  → DeepSeek 只执行获批 preflight/smoke，保存新 runroot
  → Luna 只读 runroot 形成结果总结
  → Sol 一次性更新正式状态并形成唯一收尾 commit
```

实验运行期间不得更新 `project_state.md`、`state/SESSION_HANDOFF.md`，不得 commit 或
push。原始 runroot 只追加，不覆盖。当前交接没有正在运行的实验，因此本次准备态
文档由 Sol 一次性同步到短状态文件。

## 8. 新多机对话的首条指令

```text
这是从单机 20 m 水平全向候选进入多机集成的新阶段。先完整读取 AGENTS.md、
handoff/SINGLE_TO_MULTI_TRANSFER_20260820.md、state/SESSION_HANDOFF.md、
state/current_summary.md 和 experiments/manifests/2uav_smoke.yaml。不要读取全部单机
历史，不要启动仿真。先核对冻结 commit/hash、工作树和 2-UAV 接线缺口，再生成仅限
静态接入与 preflight 的计划；launch 仍是占位符时不得批准实验。
```
