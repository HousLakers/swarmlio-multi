# 赛题收尾与指标补齐计划（XH-202629，截止 2026-09-15）

> 状态：`计划定稿（lead-planning 2026-08-24）`
> 背景：负载均衡矩阵 17/18 已完成；掉线 Route A 已闭环。当前进入赛题交付期。
> 赛题四指标（PDF 第六节）：①定位与建图精度 ②实时性与鲁棒性 ③自主决策能力 ④平台约束。
> 用户决策（2026-08-24）：A2-r3 补跑 + C1 一起收尾；指标①②③全部补齐；演示走实验室路线（有实验室）。

---

## 0. 时间线（今天 2026-08-24，提交 09-15，约 22 天）

| 阶段 | 窗口 | 内容 | 主要终端 |
|---|---|---|---|
| P0 收尾 | 08-24 ~ 08-26 | A2-r3 补跑、C1 验证、收尾 commit | 低（执行）→ 高（审核） |
| P1 指标① | 08-26 ~ 09-01 | 真实 LIO 接入、ATE、5cm 地图、SLAM≥10Hz 证据 | 中（代码）→ 低（执行） |
| P2 指标② | 09-01 ~ 09-06 | 通信丢包 ≤20% 鲁棒性实验 | 中（代码）→ 低（执行） |
| P3 指标③ | 09-05 ~ 09-09 | 重规划延迟测量、突发障碍场景 | 中（代码）→ 低（执行） |
| P4 交付物 | 09-07 ~ 09-14 | 三报告、国产化说明、PPT、源码包、演示视频 | 高（撰写/编排）+ 各终端 |

> 并行：指标③的重规划延迟可从掉线实验的 drop.json 事件时间戳直接后处理得出（低终端可提前做），
> 不需要等中终端开发。

---

## P0 收尾（08-24 ~ 08-26）

### P0.1 A2-r3 补跑（18/18 口径）

- 发现：`scripts/run_overnight_matrix.py` 的 `cmd_run` **会跳过 `failed` 状态**的 run
  （`if rec.get("status") in ("done", "failed", "error", "running"): continue`），
  与 SESSION_HANDOFF 中「执行器自动仅执行失败项」的表述不符。
- 已完成（中终端 2026-08-24）：新增 `--rerun-failed` 标志——`cmd_run` 在
  `rerun_failed=True` 时跳过集合收窄为 `("done","running")`，仅重跑 failed/error。
  已验证：`--rerun-failed --groups A2` 只选中 A2-r3；不带标志时选中空集。无 lint。
- 执行（低终端）：`python3 scripts/run_overnight_matrix.py run --groups A2 --rerun-failed`。
- 验收：`matrix_results.md` 出现 A2-r3 `done=True`，18/18 done。

### P0.2 C1 最终最佳配置验证（3 runs）

- A/B 分析结论：**MINMAX + 0.75（A2 配置）为最终最佳**——
  失衡比 1.35（全矩阵最低）、fleet ratio 0.222（最高）、Jaccard 0.725（次高）、
  总路径 745m（略长但可接受）。
- C1 定义：`objective=MINMAX, capacity=0.75, dropout=none, ×3 runs`。
- 执行：复用执行器矩阵机制（新增 C1 组定义 + 3 次重复），或按 `3uav_nodrop` 方式手工 3 个 run。
- 掉线鲁棒性已由 B2（MINMAX 0.75 + dropout）3/3 覆盖，无需重复。

### P0.3 收尾 commit + push

- 内容：`matrix_results.md/.jsonl`、`matrix_state.json`、`PLAN_COMPETITION_2026.md`、
  `state/current_summary.md`、`state/SESSION_HANDOFF.md`。
- 格式：`stage: LB-matrix closeout`（按每阶段提交规则 push origin main）。

---

## P1 指标① 定位与建图精度（08-26 ~ 09-01）

### 现状与差距

- 现状：`registration_source: gt`（`config/3uav_static.yaml`），地图融合用**真值位姿**，
  runner 启动 `two_uav_gt_mapper.py`（GT 同步注册适配器）。
- 差距：没有真实 LIO 里程计闭环 → ATE 从未测量；`sdf_resolution_m: 0.1`（10cm），
  高于赛题要求的 5cm。

### 关键事实（已验证）

- 平台已编译 **FAST_LIO**（`swarm_ws/src/FAST_LIO`）与 **Swarm-LIO2**
  （`swarm_ws/src/Swarm-LIO2`），devel 下已有 `fast_lio` / `swarm_lio` 可执行文件。
- FAST-LIO 配置含 `mid360.yaml`；仿真传感器为 `livox_laser_simulation`（mid360）。
- 静态 contract 已定义 LIO 风格 topic：`/cloud_registered_N`、`/lidar_slam/odom_N`、
  `/lidar_slam/pose_N`——说明 LIO 接入的 topic 契约已预留。

### 任务

1. **中终端**：runner 增加 `registration_source: lidar_slam` 模式——launch 时
   用 `roslaunch fast_lio mapping_mid360.launch`（每 UAV 独立 namespace）替换/旁路 gt_mapper；
   校验 extrinisics（livox 与 IMU 外参对齐，仿真值已知可写死）。
2. **低终端**：跑 1 次 3-UAV smoke（minimal 120s 或 300s），对比 `registration_source: gt` vs
   `lidar_slam` 的 map consistency / coverage；记录 LIO 输出频率。
3. **ATE 评估（中终端脚本）**：比较 `lidar_slam/odom_N`（LIO 轨迹）与 GT
   （`/gazebo/ground_truth/state` 或 mavros local_position）→ 输出 APE/ATE（m，RMS）。
   可直接写轻量脚本（对齐时间戳 + Umeyama/SVD 刚体对齐），无需 evo 依赖。
4. **5cm 地图**：用已积累的 registered cloud 重栅格化为 5cm 分辨率重建图
   （如 50×50×3 m → 1000×1000×60 voxel），出对比帧；并明确报告「3D 地图分辨率 ≥5cm」证据。
5. **SLAM≥10Hz 证据**：`rostopic hz /uavN/lidar_slam/odom_N` 采样统计（≥10Hz）。

### 验收

- ATE ≤ 0.5m（RMS，50×50m 室外场景）成立或有量化结果；
- 5cm 分辨率重建图产出；
- SLAM 节点频率 ≥10Hz 采样统计。

---

## P2 指标② 实时性与鲁棒性（09-01 ~ 09-06）

### 差距

- 丢包鲁棒：`communication_delay_ms: 0`，从未做通信断续实验。赛题要求「丢包率 ≤20% 下核心任务不中断」。
- SLAM 频率：见 P1.5（≥10Hz 证据）。

### 任务

1. **中终端**：runner 增加 `comm_degrade` 事件（新增 fault-injection 类型，**与 dropout 分开记录**，
   遵守掉线工作流约束）：
   - 字段：`{enabled, mode: packet_loss, vehicle: all|uav1, rate: 0.05/0.10/0.20, window_s, record: fleet/comm_degrade.json}`
   - 实现方式建议：在 fleet 协调 topic（`/swarm_expl/drone_state` 与共享地图 topic）入口做
     drop 采样；或对 `udp_bridge`（Swarm-LIO2 通信层）加丢包模拟。
2. **低终端**：3 组实验（5% / 10% / 20%），每组 1~2 个 300s run，验证核心任务（建图+探索）
   不中断、无 abort、coverage 仍增长；记录 `exit_reason=duration_complete`。
3. 报告中与 dropout 实验明确区分（通信断续 vs 子系统失效）。

### 验收

- 丢包 20% 下 `final_safety_passed=true`、无 abort、剩余 coverage 增长；
- 报告给出丢包率-覆盖率/一致性退化曲线。

---

## P3 指标③ 自主决策能力（09-05 ~ 09-09）

### 差距

- 子系统失效（掉线）已验证（强项）；多机协同决策（MINMAX）已验证。
- 缺：在线重规划响应延迟 ≤2s 的证据；突发障碍弹性决策演示。

### 任务

1. **重规划延迟（低终端先行，后处理即可，已确认无需新埋点）**：
   - 证据来源（已验证）：`fleet/dropout.json` 有事件 `sim_s`（如 87.166）；
     每机 `logs/ros/<uuid>/exploration_node_*-stdout.log` 含 sim 时间戳的
     `[FSM] published bspline id=N` 事件（如 `[INFO] [wall, 76.165]: published bspline id=4`）。
   - 方法：取「掉线/丢包事件 sim_s → 幸存机下一段 bspline publish sim_s」差值，
     统计中位数/P95。从已有掉线 run 与 P2 丢包 run 后处理即可。
2. **突发障碍（中终端）**：runner 增加 `dynamic_obstacle` 事件——在指定 sim_s
   spawn 一个 Gazebo 动态模型（如运动障碍盒/落物）切入某机轨迹，验证避障重规划。
3. **验收指标**：重规划延迟 ≤2s（P95）成立；突发障碍后无 crash/contact 且继续探索。

---

## P4 交付物（09-07 ~ 09-14）

按 PDF「八、（二）作品提交方式」：

1. **系统设计方案**：架构、算法原理、通信协议（ROS topic/namespace 隔离、shared_async 地图、
   掉线/丢包/突发障碍 fault-injection 协议）。
2. **关键技术创新报告**：创新点——①掉线弹性决策与负载均衡（MINMAX 失衡比 1.35）②
   通信断续鲁棒 ③fault-injection 验证方法论。
3. **系统测试与验证报告**：18-run 矩阵 + 掉线 9/9 + LIO/ATE + 丢包实验 + 资源门记录。
4. **国产化组件说明**：平台选型（Atlas 200I DK A2 / RK3588 / 昇腾 310B），功耗核算 ≤30W，
   openEuler/麒麟 aarch64 + ROS 移植路径；实测优先做「板端回放 FAST-LIO」演示。
5. **答辩汇报 PPT**。
6. **核心软件源代码**。
7. **原型系统实物工作展示视频**（用户确认有实验室：按实验室可用硬件定实机 vs 板端回放）。

---

## 禁止事项（沿用 AGENTS.md + 掉线约束）

- 复用任何已消费 approval / runroot；新实验重新签发。
- 把 intentional_dropout 写成 crash/contact；comm_degrade 与 dropout 分开记录。
- 降低资源门（MemAvailable ≥3GiB、swap delta ≤200,000、RT 尽力）。
- 修改冻结的单机参数 / 环境 baseline；实验期间 commit/push（收尾 commit 除外）。
- 未经批准扩大实验范围（新增 LIO/丢包/突发障碍均需本轮 approval 重签）。

## 风险与对策

| 风险 | 对策 |
|---|---|
| 真实 LIO 接入后 map consistency 下降 | 先单机 120s smoke 冒烟；外参写死仿真已知值；对比 gt vs lidar_slam |
| FAST-LIO 与 mid360 仿真点云时序不匹配 | 检查 livox_laser_simulation 发布频率与 FAST-LIO 配置（mid360 10Hz） |
| 丢包注入改通信层影响面大 | 先做 topic 入口 drop 采样（最小侵入），再考虑 udp_bridge |
| 突发障碍 spawn 导致碰撞误报 | 障碍物避开 contact 阈值语义，记录为 dynamic_obstacle 独立事件 |
| 板卡未到货 | 演示视频先用仿真录屏 + 板端回放双轨，实机留给终审擂台赛 |
| 时间不够 | 优先级：指标①>②>③；每阶段有独立验收，可单独进报告 |
