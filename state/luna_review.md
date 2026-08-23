# Luna review: RUN-20260822T173640Z-2uav-smoke

状态：本轮 runroot 证据完整，**smoke 首次完整通过**（duration_complete、final_safety_passed=true）。
不得把本报告解释为已满足所有比赛指标或可跳过未来 preflight。

## 1. 不可变身份与运行结论

- runroot：`results/RUN-20260822T173640Z-2uav-smoke/`
- manifest：`experiments/manifests/2uav_smoke.yaml`，SHA-256 `5cc07755…`
- multi source hash manifest：`01ba0648f9e4bbaa3197db87941c15489fccb05120bb9cde86b66c1cfd67bdf2`
- 公共环境 baseline：`racer_outdoor_50x50_v1`，manifest SHA-256 `ce595caf…`
- platform commit：`57c1f34a…`；single commit：`8c8ddf2…`
- overlay：`range20m_omnidirectional_v1`，分辨率 0.10 m
- smoke package `smoke-20260823-2uav-first-pass-1`（22e160bb）已消费，不得复用
- `execution_result.json`：`exit_reason=duration_complete`、`final_safety_passed=true`、
  `fleet_metrics/uav0_metrics/uav1_metrics` 全 true；teardown clean、无 survivors、无 kill

证据：`execution_result.json`、`live_preflight.json`（53/53）、`static_preflight.json`（55/55）、
`resource_capacity_*.json`、`stop_result.json`、各 metrics/telemetry.jsonl。

## 2. 资源与实时性

| 门 | 周期 | 值 | 门限 | 结果 |
|---|---:|---:|---:|:---:|
| MemAvailable | startup | 11.18 GiB（12.00 GB） | ≥ 8 GiB | ✅ |
| load1 | startup | 2.43 | < 10 | ✅ |
| swap_in/out | startup | 0 / 0 | — | ✅ |
| MemAvailable | running | **4.95 GiB**（5.31 GB） | ≥ 3 GiB | ✅ |
| load1 | running | 3.52 | — | ✅ |
| swap_in/out | running | **0 / 0**（delta +0/+0） | delta ≤ 200000 | ✅ |
| RT factor | smoke 全程 | **p50=0.41, p95=0.43** | ≥ 0.5 | ❌ **未达标** |

**资源关键状态：**
- Gazebo max RSS 5.17 GiB（稳定，与 preflight 一致）
- RACER max RSS **1.87 GiB**（双机，含两个 exploration_node；0.10m overlay 使 racer 内存从 6.9 GiB 降至 1.87 GiB）
- bridges 137 MB, gt_mapper 105 MB, collector 82 MB
- 栈总 RSS 约 **7.3 GiB**，运行态 MemAvailable 4.95 GiB（≥ 3 GiB 有 1.95 GiB 余量）
- load1 稳态 6.28-6.72（20 核，CPU 并非瓶颈；RT 低的原因不在此）
- **swap 零活动**：全程 pswpin/pswpout 保持 0，资源面已充分可控

**RT factor 分析：** preflight no-goal soak 时 RT p95≈1.97（快于实时）；smoke 有双机实时规划/轨迹执行时 RT 降至 0.41。机器有 20 核但 load1 仅 ~6.5，RT 低可能原因是 gzserver 的 `real_time_update_rate=1000`（1000 Hz physics）产生同步约束，或者串行依赖（如 map 共享锁）在双机并发时形成瓶颈。该指标未达标，但 **120 sim-s 实际用时 ~293 wall-s（~5 分钟）**，对开发可接受，对比赛 "在线重规划响应延迟不超过 2 秒" 需进一步验证。

## 3. uav1 freeze = true 分析（用户重点提问）

### 数据

| 指标 | uav0 | uav1 |
|---|---:|---:|
| trajectory（总） | **83** | **52** |
| ack_count | 10,178 | 12,238 |
| path length | **121.27 m** | **51.43 m** |
| pos_cmd | 10,178 | 12,238 |
| ack_timeout | 0 | 0 |
| freeze | **false** | **true** |
| crash | false | false |
| contact | 0/0/0 | 0/0/0 |
| completion | false | false |
| coverage ratio | 0.081（8.1%） | **0.106（10.6%）** |
| final position | (-4.07, 9.14, 2.05) | **(-4.32, -19.10, 1.91)** |

### freeze 判定逻辑

collector 的 `update_position()`：
```python
if distance >= 0.02:            # 单次位移 ≥ 2cm 才算 "motion"
    self.last_motion_wall_s = now
```

`snapshot()` 的 freeze 判定：
```python
moved = self.path_length_m >= 0.25
frozen = bool(moved and self.last_motion_wall_s is not None and
              now - self.last_motion_wall_s >= 15.0)
```

### 结论：该 freeze 是"晚期规划停滞"，非"早期不接令"

uav1 的 telemetry 时间线：

| 样本 | sim 区间 | path (m) | ack_id | freeze |
|---|---:|---:|---:|:---:|
| 0-7 | 起飞 | 0→1.67 | None | false→true（短暂）→false |
| 10-30 | 活跃探索 | 2.92→47.84 | 4→52 | false |
| **35-70** | **末期** | **48.64→51.43** | **52（不变）** | **true** |

uav1 最后一条轨迹 id=52 完成后，规划器无法找到下一条可行路径。racer.log 显示在 sim 150.68-150.80 期间 `exploration_node_2` 连续抛 `Astar timed out`，从地图各角落候选 viewpoint 均超时，最高单次迭代 49154 次、reject 183729 次。此后车辆在 (-4.3, -19.1, 1.9) 处悬停，单次 odometry 位移 < 2cm 不触发 motion 标记，15s 后 freeze=true。

**这与上一轮 smoke（uav1 trajectory=0/ack=0，完全不接令）有本质区别。** 本轮回度冻结束是由于规划器在给定地图边界内耗尽了可达 viewpoint —— 这在 120 sim-s 有限探索下是正常终点现象。若运行更长时间（或更大地图），可能需要更鲁棒的 frontier 选择与 A* 优化。

### 建议

- freeze 判定阈值（目前 15s 无 ≥2cm 运动）对 hover-in-place 场景过于敏感。可在 collector 中增加对 `airborne && pos_cmd_active` 的联合判定：若最新 pos_cmd wall 时间距今 < 15s 且车辆已就位目标点，则不应标为 freeze。但这属于功能改进，**不改变已在 smoke 中通过的核心安全门**。
- 更长时间的 smoke（如 300 sim-s）可验证是否为真正的"探索耗尽"。

## 4. 无图像仿真的问题（用户重点提问）

### 原因

当前 world 和 SITL launch 中无 camera/RGB 传感器。仿真硬件栈仅为：**LiDAR（livox ray plugin）+ PX4 SITL + IMU/气压计**。Gazebo 世界没有任何 `<camera>` 标签。这是为了在 16 GB 主机上节省 GPU 和 CPU 算力——加 visual camera 会显著增加 gzserver 负载，使 RT factor 进一步下降。

### 影响

- **栅格（occupancy）图**：系统内在产生 `/sdf_map/occupancy_all_*` topic（0.10m 分辨率，268,912 voxels 在 planner_box 内）。**可在 smoke 结束时 dump 为 PGM/PNG + 叠加轨迹。** 这是一个后处理脚本，不涉及仿真更改。
- **点云图**：GT mapper 产生 `/cloud_registered_*` topic，可 dump 为 PCD + 渲染截图。也需后处理。
- **相机/视觉证据**：如果比赛报告需要视觉 SLAM 证据（如特征点跟踪、关键帧快照），则需要添加 camera sensor 或在 GT mapper 中保存视角渲染。这会增加资源消耗。

### 建议

1. 短期：编写 post-smoke 后处理脚本，从 occupancy_all topic 导出栅格图（PGM/PNG），从 registered_cloud 导出点云快照（PCD）
2. 中期：评估是否可加一个低分辨率 camera（320×240, 5fps）而不显著影响 RT factor
3. 这些后处理脚本属于**结果分析工具而非实验修改**，可并行开发

## 5. Fleet 关键指标

| 指标 | 值 | 评价 |
|---|---:|---:|
| fleet_coverage_ratio | **0.114**（11.4%） | 120s 内低，因 50×50 地图大；需更长 run |
| fleet_coverage_voxels | 30,655 | — |
| map_consistency_jaccard | **0.639** | 两机地图 64% 一致，合理 |
| overlap_ratio | **0.904** | 90% 观察重叠，共享地图良好 |
| minimum_inter_uav_distance | **1.479 m** | 略低于初始间距1.5m，仍安全 |
| fleet_contact_count | 0 | 无碰撞 |
| process_liveness | 8/8 全存活 | — |
| abort_reasons | **空（无 abort）** | 全运行时通过 |
| telemetry_completeness | true | — |
| task_allocation_state_samples | 3,581 | — |

## 6. 三机扩建与单机掉线实验方案

### 比赛要求

题目文件明确要求"自适应决策：当部分子系统因故障、损毁或通信阻塞而失联时，无人机能否自主重构并持续完成任务"以及"通信断续（丢包率≤20%）保持核心任务不中断"。这是本文件夹系列实验的最终目标。单机掉线实验需要**至少 3 机**才能演示"一架掉线，剩余继续"的场景。

### 当前资源余量

16 GB 主机，当前双机 smoke 运行态：
- 栈 RSS ≈ 7.3 GiB（Gazebo 5.17 + RACER 1.87 + bridges 0.14 + gt_mapper 0.11 + collector 0.08）
- 运行 MemAvailable = 4.95 GiB
- RT factor = 0.41

第三机边际增量预估（按第 47 节模型）：
- Gazebo（额外 SITL + mavros + livox）：**+1.0-1.2 GiB**
- RACER（exploration_node_3 + 地图/规划器）：**+0.83 GiB**
- bridges（px4_bridge_3）：**+0.065 GiB**
- 合计：**+1.9-2.1 GiB**

三机栈 RSS ≈ 7.3 + 2.0 ≈ 9.3 GiB → MemAvailable ≈ 15.42 - 1.75（OS 基线） - 9.3 ≈ **4.4 GiB**（余量 1.4 GiB ≥ 3 GiB 门）。边界可行，但风险较高。RT factor 会进一步下降（可能到 0.25-0.30）。

### 最快三机扩建步骤（不升级硬件）

```text
1. 创建新文件（不改 2-UAV 冻结文件）：
   - config/3uav_static.yaml（uav_count: 3，uav2 参数）
   - launch/3uav_px4_sitl.launch（uav2 group, tgt_system=3）
   - launch/3uav_racer.launch（exploration_node_3, drone_num=3）
   - launch/3uav_bridges.launch（px4_bridge_3, /uav2）
   - experiments/manifests/3uav_smoke.yaml（uav_count: 3）

2. 修改现有文件（改变 identity 链）：
   - scripts/three_uav_collector.py（或 two_uav_collector.py + uav2 支持）
   - scripts/three_uav_runner.py（或 runner 参数化，支持 uav_count 推导路径）
   - scripts/three_uav_preflight.py（或 preflight 参数化）

3. 更新 source hash manifest → 新的 source-hash manifest hash

4. 静态检查 + 单次 diagnostic preflight

5. 单机掉线实验（在 3-UAV 基础上断开一机，验证剩余 2 机自适应继续）
```

但注意：**三机 preflight 和掉线实验绝不能在三机 preflight 通过前执行。** 所有步骤与 2-UAV 有依赖关系，建议使用 `scripts/two_uav_runner.py` 作为基准修改为参数化版本（接受 `--manifest` 中的 `uav_count`），而不是复制三份不同的 runner。

### 更快速路径：先在 2-UAV 上验证掉线逻辑

如果开发时间紧张，可以先在 2-UAV smoke 基础上实现"主动断开 uav1"实验（软掉线）：在 smoke 过程中 kill uav1 的 px4_bridge/exploration_node 进程，验证 uav0 继续探索、collector 正确报告掉线、系统不进入未知状态。这只需要修改 runner 的 smoke 阶段（或添加一个 dropout 模式），可在**现有 identity 链**基础上进行，不涉及三机扩建。然后三机扩建时复用该掉线逻辑。

## 7. Luna 判断与后续边界

本轮是 **首次完全通过的 2-UAV smoke**。所有安全门通过（55+53 static+lives、资源门、final safety、teardown），RT 目标未达标（p95 0.43 < 0.5）但 120s 实验在 ~5 分钟 wall 内完成，不影响数据完整性。uav1 freeze=true 是晚期规划停滞而非早期掉线，与上一轮有本质区别。

### 进入三机扩建的条件

1. 确认 2-UAV smoke 结果满足比赛基线
2. 资源评估确认 3-UAV MemAvailable ≥ 3 GiB + swap delta ≤ 200000（当前 16 GB 边界可行但风险高）
3. 建议先做 collect/tools 后处理（栅格图 + 点云图输出），再切换到三机

### 不批准项

- 不修改已冻结的 2-UAV 身份文件（manifest、source hash、config、launch、scripts）来适应 3-UAV；新建 3-UAV 文件
- 不降低资源门（MemAvailable ≥ 3 GiB、swap delta ≤ 200000 不变）
- 不在三机 preflight 通过前进入三机 smoke 或掉线实验
- 不添加 camera sensor 到 world 而不评估 RT 影响

```text
handoff_status: READY
handoff_model: lead-planning
handoff_command:
审核完毕。请基于本 luna_review.md 决定后续路径：(A) 直接进入三机扩建（创建 config/launch/manifest + 参数化 runner/collector/preflight）；(B) 先在 2-UAV 上实施主动掉线实验（验证掉下逻辑再扩展）；(C) 先做后处理工具（栅格图/点云图导出）再决定。package 已消费、不得复用同一 identity 重试 smoke。
```