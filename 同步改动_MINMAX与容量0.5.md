# 多机掉线实验完整落地实验方案

基于你当前多机掉线实验现状，结合同伴的 MINMAX + 容量 0.5 改动，
以及你单机项目的图标准，提出完整落地方案。

---

## 一、掉线实验最终目标

### 第一目标：完整搜图

- 即使一机掉线，剩余机仍能完成全图覆盖
- 不因为一机失联而导致 abort / crash / freeze
- 掉线分类必须正确（intentional_dropout，不是 crash/contact/freeze）

### 第二目标：效率优化

在完整搜图的前提下，优化两项指标：

- **最短完成时间**（makespan）：最后一架机完成探索的时刻
- 或 **最短总路径**（total path length）：
  - 三机路径之和
  - 如果掉线了，剩余机路径之和

### 最终目标语句

> 多机掉线实验：在受控单机失联（node_level）后，剩余机仍能通过均衡负载策略
> 以最短时间或最短总路径完成全图建图。

---

## 二、同伴改动筛选与采用方案

### 改动 A：ACVRP 目标函数 MINSUM → MINMAX

**结论：采用，作为可切换参数**

实现方式：在 `allocateGrids` 函数中，ACVRP (prob_type=2) 分支的 `.par` 文件生成处，
加一行 `MTSP_OBJECTIVE = MINMAX`，但保留 MINSUM 作为默认值。

**建议配置**（三组实验参数）：

| 配置名 | 目标函数 | 容量 | 用途 |
|--------|---------|------|------|
| `minsum_cap075` | MINSUM（默认） | 0.75 | 基线对照 |
| `minmax_cap075` | MINMAX | 0.75 | 评估 MINMAX 单独效果 |
| `minmax_cap050` | MINMAX | 0.50 | 评估 MINMAX + 容量降低效果 |

### 改动 B：单机探索容量 0.75 → 0.5

**结论：采用，作为实验参数，不直接默认替换**

理由：

- 容量降低可以辅助 MINMAX 均衡任务
- 但容量过低可能增加协调开销和总路径
- 建议保留 0.75 作为默认，0.5 作为实验组

### 改动 C（新增）：coverage 时间序列落盘

**结论：需要新增**

当前 collector 只落盘最终 coverage_voxels 集合，没有时间序列。
为了画"栅格数量增加曲线"，需要记录每帧 occupancy 处理后的累计 voxel 数和 sim_s。

改动位置：`two_uav_collector.py` 的 `_process_occupancy_snapshots` 中，
每次 `commit_occupancy_snapshot` 后，记录：

```python
state.coverage_seq.append((sim_s, len(state.coverage_voxels)))
```

finalize 时落盘为 `coverage_seq.json`。

---

## 三、多机绘图标准（对齐单机画法）

### 3.1 `coverage.png`（主图，上下两栏）

**布局**：`figsize=(10, 12), gridspec_kw={'height_ratios': [2, 1]}`

**上栏：二维俯视图**

- 点云：`/sdf_map/occupancy_all_*` 的最终占据体素 → xy 平面投影 → 黑色小点散点图
  - `ax.scatter(pts[:,0], pts[:,1], s=0.2, c='k', alpha=0.5)`
  - 随机采样至多 200,000 个点
  - 限高 z ∈ [1.15, 2.70]（planner flight layer）
- 轨迹：从 telemetry.jsonl 提取每机 position → 蓝色线条
  - 每机一个颜色（uav0=蓝, uav1=绿, uav2=红）
- 起点：绿色大圆点 `go, ms=10`
- 终点：红色三角 `r^, ms=10`
- 掉线标记：橙色 x 标注掉线事件位置
- 接触/坠机标记：橙色 x / 红星
- `set_aspect('equal')`
- 坐标范围：`xlim(-25, 25), ylim(-25, 25)`
- 标题：`cov_grids=%d  rate=%.1f cells/s  uav0=%d  uav1=%d[dropout]  uav2=%d`
- legend 右上

**下栏：栅格数量增加曲线**

- x 轴：模拟时间（sim_s）
- y 轴：unique observed voxels 累计数（严格单调递增）
- 曲线：`ax2.plot(sim_seq, cov_seq, 'b-', lw=2.0, label='unique coverage voxels (cumul)')`
- 如果掉线，用垂直虚线标注掉线时刻
- 每机曲线用不同颜色（uav0=蓝, uav1=绿, uav2=红），fleet 汇总用黑色粗线
- 副 y 轴（红色虚线）：coverage ratio `%`（仅供参考）
- 标题：`exploration progress | final=%d voxels, rate=%.1f cells/s`
- grid/legend 右下

### 3.2 `grid_map.png`（辅助图，灰度栅格）

- 5cm 分辨率栅格
- 从 `/sdf_map/occupancy_all_*` 最终占据体素投影到 xy 平面
- 限高 z ∈ [1.15, 2.70]
- bounds：`[-24.5, 24.5]`（planner box）
- 灰度 imsave：`plt.imsave(np.flipud(grid), cmap='gray', vmin=0, vmax=255)`
- 同时输出 `grid_map_meta.json`（含分辨率、bounds、occupied_cells、map_quality 指标）

### 3.3 `point_cloud.png`（二维俯视点云图）

注意：和单机一样，**俯视投影**，不是 3D 透视图。

- 从最终 occupied_map.xyz 取点
- `ax.scatter(pts[:,0], pts[:,1], s=0.2, c='k', alpha=0.5)`
- 叠加轨迹（每机不同颜色）
- `set_aspect('equal')`
- 坐标范围：`xlim(-25, 25), ylim(-25, 25)`

### 3.4 数据文件

- `occupied_map.xyz`：final occupancy 点云（3D 坐标，浮点数，空格分隔）
- `cloud_registered.xyz`：final registered 点云（3D 坐标）
- `trajectory.csv`：轨迹 CSV（每机一个文件或合并 CSV）
- `coverage_seq.json`：coverage 时间序列 `[[sim_s, unique_voxels], ...]`

---

## 四、collector 改动清单

### 4.1 已实现的改动

- `two_uav_collector.py` finalize 时落盘 `coverage_voxels.json`（已实现）
- `two_uav_collector.py` finalize 时调用 `_write_visual_artifacts`（已实现）

### 4.2 需要新增的改动

1. **coverage 时间序列记录**
   - 在 `_process_occupancy_snapshots` 中，每次 `commit_occupancy_snapshot` 后，追加：
     ```python
     state.coverage_seq.append((stamp or processed_wall_s, len(state.coverage_voxels)))
     ```
   - finalize 时落盘 `coverage_seq.json`

2. **绘图脚本重写**
   - 重写 `draw_experiment_artifacts.py`，输出：
     - `coverage.png`（上下两栏，对齐单机画法）
     - `grid_map.png`（5cm 灰度栅格）
     - `point_cloud.png`（二维俯视点云）
     - `occupied_map.xyz`
     - `coverage_seq.json`（如果新增了时间序列）

3. **collector `_write_visual_artifacts` 重写**
   - 调用 `draw_experiment_artifacts.py` 或直接内置绘图代码

### 4.3 掉线研究者改动（MINMAX + 容量 0.5）

1. 修改 `fast_exploration_manager.cpp` 的 `allocateGrids` 函数
   - 在 ACVRP 分支 (`prob_type == 2`) 加 `MTSP_OBJECTIVE = MINMAX`
   - 保留 MINSUM 作为默认，MINMAX 通过参数切换
2. 容量 0.5 作为实验参数
   - 保留 0.75 默认，0.5 通过参数切换

---

## 五、实验矩阵

> 统一仿真时长：**每组 300 sim-s**（按用户 2026-08 决策，相比 120 sim-s
> 更接近"完整搜图"目标，便于观察 coverage 收敛趋势）。

### 阶段 1：基线确认（1 次实验）

| 实验 | 时长 | 目标 | 容量 | 预期 |
|------|------|------|------|------|
| 1-1 | 300s | 无掉线 baseline | 0.75 | MINSUM 默认，三机正常探索 |

### 阶段 2：MINMAX 评估（2 次实验）

| 实验 | 时长 | 目标 | 容量 | 预期 |
|------|------|------|------|------|
| 2-1 | 300s | MINMAX 单独效果 | 0.75 | 负载均衡改善，完成时间可能缩短 |
| 2-2 | 300s | MINMAX + 容量 0.5 | 0.50 | 进一步均衡，可能总路径略增 |

### 阶段 3：掉线 + 均衡（3 次实验，每次 node_level 掉线）

| 实验 | 时长 | 配置 | 掉线 | 预期 |
|------|------|------|------|------|
| 3-1 | 300s | MINSUM + 0.75 | uav1 @ sim 60 | 基线掉线，一机干绝大部分 |
| 3-2 | 300s | MINMAX + 0.75 | uav1 @ sim 60 | 掉线后剩余机更均衡，完成更快 |
| 3-3 | 300s | MINMAX + 0.50 | uav1 @ sim 60 | 最低容量，最快完成（预期） |

### 阶段 4：最终验证（1 次实验）

| 实验 | 时长 | 目标 | 容量 | 预期 |
|------|------|------|------|------|
| 4-1 | 300s | 最佳配置 + 掉线 | 最佳配置 | 完整搜图 + 最短完成时间 |

---

## 六、本地 git 版本管理方案

### 保持原始版本不变

```bash
# 原始 D10 版本（无 MINMAX，无容量 0.5）
# 不作任何改动，保留在 git 历史中
```

### 创建实验分支保存 MINMAX + 容量 0.5 改动

```bash
# 从当前 main 创建实验分支
git checkout -b experiment/load-balancing

# 在这个分支上修改 fast_exploration_manager.cpp
# 加 MINMAX 和容量 0.5 参数
# 所有改动只在这个分支

# 提交
git add 同步改动_MINMAX与容量0.5.md
git add racer_ws/src/RACER/swarm_exploration/exploration_manager/src/fast_exploration_manager.cpp
git commit -m "experiment: add MINMAX objective + capacity 0.5 parameter for load balancing"

# 切换回 main 分支继续掉线实验
git checkout main
```

### 绘图脚本改进（主分支）

```bash
# 重写 draw_experiment_artifacts.py
# 按单机画法标准：coverage.png（上下两栏），grid_map.png（灰度），point_cloud.png（俯视）
git add scripts/draw_experiment_artifacts.py
git add scripts/two_uav_collector.py
git commit -m "fix: align multi-UAV figures with single-UAV drawing standard"
```

### 版本管理总览

| 分支 | 用途 | 包含改动 |
|------|------|---------|
| `main` | 掉线实验主线 | collector 改进、绘图标准、掉线实验流水线 |
| `experiment/load-balancing` | 负载均衡实验 | MINMAX + 容量 0.5 参数 |
| （未来）`experiment/minmax-only` | 分拆实验 | 仅 MINMAX，容量保持 0.75 |
| （未来）`experiment/capacity-050` | 分拆实验 | 仅容量 0.5，目标保持 MINSUM |

---

## 七、实施状态

> 已按本方案完成到"第四步跑实验之前"，具体状态见下表。
> 当前身份链（2026-08 参数化后）：
> - 3-UAV manifest `experiments/manifests/3uav_smoke.yaml`
>   - SHA-256 `509e71fda25d275caae12f6d01246bf264ca3d1588c7a056853877764a29370f`（duration 300s）
> - 3-UAV source hash manifest `config/3uav_source_hashes.sha256`
>   - SHA-256 `48ce54177330f445d4bb154fa2764f14c94d580e853c0dff3922bf300589f72e`

### P0（已完成）

1. ✅ 重写 `draw_experiment_artifacts.py`
   - 产出 `coverage.png`（上下两栏，对齐单机画法）
   - 产出 `grid_map.png`（5cm 灰度栅格）
   - 产出 `point_cloud.png`（二维俯视点云）
   - 产出 `coverage_seq.json` 时间序列（无该文件时从 telemetry 回退）

2. ✅ collector 新增 coverage 时间序列记录
   - `_process_occupancy_snapshots` 中追加 `coverage_seq`
   - finalize 落盘 `coverage_seq.json`

### P1（已完成）

3. ✅ 创建实验分支 `experiment/load-balancing`（RACER 仓库）
   - `fast_exploration_manager.cpp` 加 `MTSP_OBJECTIVE` 参数（MINSUM/MINMAX）
   - `capacity_factor` 参数化（0.75 默认 / 0.5 实验）
   - `single_drone_planner.xml` / `single_drone_exploration.xml` 透传参数
   - 已编译通过（`exploration_node` Built target）
   - swarmlio_multi：`3uav_static.yaml` 加 `exploration` 段，
     `3uav_racer.launch` 透传 launch arg，runner 转发给 roslaunch
   - main 分支保留默认 `MINSUM + 0.75`，实验矩阵只改 config 即可切换

### P2（待验证阶段）

4. ⬜ 按实验矩阵跑阶段 1-3（每组 300s）
5. ⬜ 阶段 4 最终验证
6. ⬜ 更新报告和图表

### 跑实验前需重新签发 approval

- 已消费的 approval（`dropout-smoke-20260824-3uav-D10-replay`）不得复用
- 新的 manifest/source-hash 组合必须签发新 approval package 后才能 `launch`

---

## 八、与单机目标的对齐

### 单机目标

> 单机搜完全图，以最短时间或最短路径完成建图。

### 多机掉线目标

> 多机单机掉线：一机失联后，剩余机通过均衡负载策略，
> 以最短时间或最短路径完成全图建图。

### 图标准对齐

| 输出物 | 单机标准 | 多机标准 |
|--------|---------|---------|
| `coverage.png` | 上下两栏：俯视点云+轨迹 / 栅格累计曲线 | 同上，多机多色轨迹 |
| `grid_map.png` | 5cm 灰度栅格图 | 同上，bounds ±24.5 |
| `point_cloud.png` | 二维俯视点云 | 同上，多机轨迹叠加 |
| `occupied_map.xyz` | occupancy 点云 | 同上 |
| `coverage_seq.json` | `[[t, unique_grids], ...]` | 同上，每机一个序列 |

---

## 九、总结

当前多机掉线实验已经走通了：

- 掉线注入（node_level）
- 分类正确（intentional_dropout）
- 剩余机继续探索
- 无 abort / crash / contact

接下来要做的：

1. **把两栅格图标准改成和你单机一致**（上下两栏 + 二维俯视 + 增长曲线）
2. **落地 MINMAX + 容量 0.5**，但保留版本分支
3. **按实验矩阵验证**，确认最短时间/最短路径配置