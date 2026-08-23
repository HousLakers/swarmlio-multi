# 多机掉线负载均衡实验详细计划（每组 300s × 3 次重复，夜间自动执行）

> 状态：`计划定稿，等待执行批准`
> 前置：P0（绘图标准）P1（MINMAX/容量参数化）已完成并本地提交；
> approval 已重签为 `load-balancing-20260824-3uav-300s-smoke`（尚未消费）。
> 本文档是第四步"跑实验"的执行蓝本。
> **每组重复 3 次（用户决策）**，共 6 组 × 3 = **18 runs**；
> **夜间全程自动执行**，由执行器脚本驱动、监控兜底。

---

## 1. 实验目标与假设

### 1.1 目标

1. **无掉线基线**：确认 `MINSUM + 0.75`（历史默认）在 300s 内的三机探索表现。
2. **负载均衡评估**：验证 `MINMAX` 是否降低三机路径失衡比（同伴报告：2.56× → 1.57×）。
3. **容量影响评估**：验证 `capacity_factor=0.5` 在 MINMAX 基础上是否进一步缩短 makespan。
4. **掉线鲁棒性**：三组配置在 `uav1 node_level 掉线`（sim 60s）后，剩余机能否继续完整建图。
5. **完整搜图**：最终目标是在 300s 内覆盖尽可能接近全图，且完成时间/总路径最短。

### 1.2 假设（可证伪）

- **H1**：`MINMAX` 相比 `MINSUM` 降低三机路径失衡比（max/min path ratio）。
- **H2**：`MINMAX + 0.5` 相比 `MINMAX + 0.75` 缩短 fleet makespan（最后一机完成时间）。
- **H3**：掉线后，三组配置剩余两机的 coverage 增量都 > 0（鲁棒性成立），
  但 `MINMAX` 组掉线后负载转移更平滑（单机承担比例更小）。
- **H4**：300s 内三机 fleet coverage ratio 显著高于 120s（此前 11.5%），
  接近完整搜图（目标 ≥ 50% 或覆盖收敛）。

---

## 2. 实验矩阵（6 组 × 3 次重复 = 18 runs，每组 300 sim-s）

| 组 | ID | 掉线 | 目标函数 | 容量 | 重复 |
|----|----|------|---------|------|------|
| A1 | `no-drop-minsum-075` | 无 | MINSUM | 0.75 | 3 |
| A2 | `no-drop-minmax-075` | 无 | MINMAX | 0.75 | 3 |
| A3 | `no-drop-minmax-050` | 无 | MINMAX | 0.50 | 3 |
| B1 | `drop-minsum-075` | uav1@60s node_level | MINSUM | 0.75 | 3 |
| B2 | `drop-minmax-075` | uav1@60s node_level | MINMAX | 0.75 | 3 |
| B3 | `drop-minmax-050` | uav1@60s node_level | MINMAX | 0.50 | 3 |

> C1（最终最佳配置验证）在 A/B 结果分析后追加 3 次，不在首批夜间矩阵内。

**常量**（所有 run）：

- `duration_sim_s: 300`
- 地图：`racer_outdoor_50x50_v1`（50×50×3 m，planner box ±24.5）
- 种子：`20260823`；3 UAV；起飞位置固定
- 掉线组统一：`uav1`、`node_level`、`trigger_sim_s: 60`、`stop_active_reclaim`
- 每组 3 次重复，runroot 各自独立

---

## 3. 每组执行前的配置准备

### 3.1 无掉线组（A1–A3）

每个无掉线组使用一个**独立 manifest**（`dropout.enabled: false`），
避免与掉线组共用 manifest 造成 approval 绑定混乱。

新建三个 manifest（从 `3uav_smoke.yaml` 复制后修改）：

| 文件 | 修改点 |
|------|--------|
| `experiments/manifests/3uav_nodrop_minsum.yaml` | `dropout.enabled: false` |
| `experiments/manifests/3uav_nodrop_minmax_075.yaml` | `dropout.enabled: false` |
| `experiments/manifests/3uav_nodrop_minmax_050.yaml` | `dropout.enabled: false` |

### 3.2 掉线组（B1–B3）

复用 `experiments/manifests/3uav_smoke.yaml`（`dropout.enabled: true`，
uav1 node_level @ 60s，已就绪），但每组因 config 不同仍需**重新签发 approval**。

### 3.3 每组的 config 参数切换

修改 `config/3uav_static.yaml` 的 `exploration` 段：

```yaml
exploration:
  mtsp_objective: MINSUM   # MINSUM | MINMAX
  capacity_factor: 0.75    # 0.75 | 0.50
```

**连锁更新**（每切换一次 config 都必须做）：

```bash
# 1) 重新计算 static config 哈希
sha256sum config/3uav_static.yaml

# 2) 更新 config/3uav_source_hashes.sha256 中 static.yaml 的行
#    （manifest 若为新建组则也要更新 manifest 行）

# 3) 重新计算 source hash manifest 自身哈希
sha256sum config/3uav_source_hashes.sha256

# 4) 重新签发 approval（绑定新的 manifest/source-hash 组合）
#    见下方"approval 签发"章节
```

### 3.4 approval 签发（每组一次，消费后不可复用）

每组 launch 前更新 `state/3uav_approval.yaml`：

```yaml
schema_version: 1
stage: smoke
approved: true
allowed_actions: [launch]
manifest_sha256: <该组 manifest 的 sha256>
source_hash_manifest_sha256: <该组 hash manifest 的 sha256>
issued_by: sol
max_uses: 1
issuance_id: <组ID-YYYYMMDD-3uav-300s>
dropout:
  enabled: <true/false>
  vehicle: uav1
  mode: node_level
  trigger_sim_s: 60
  cleanup_policy: stop_active_reclaim
  record: fleet/dropout.json
```

> 说明：掉线组 approval 与无掉线组的区别仅在 `manifest_sha256`（
> 因 manifest 的 `dropout.enabled` 不同）与 `issuance_id`。

---

## 4. 夜间自动执行流程（由执行器驱动）

### 4.1 执行器

新增脚本 `scripts/run_overnight_matrix.py`，职责：

- 内置矩阵定义（6 组 × 3 次 = 18 runs）
- 每组 run 前自动完成连锁准备：
  1. 生成/更新 manifest（无掉线组独立 manifest，`dropout.enabled: false`）
  2. 写 `config/3uav_static.yaml` 的 `exploration` 段（objective + capacity）
  3. 刷新 `config/3uav_source_hashes.sha256` 的 config/manifest 哈希
  4. 重签 `state/3uav_approval.yaml`（绑定最新 manifest + source-hash）
- 调用 frozen runner `launch`（含 live preflight + soak + 掉线注入 + 300s 监控）
- 每 run 结束记录到 `experiments/matrix_results.jsonl` 并渲染
  `experiments/matrix_results.md`
- 状态机持久化在 `experiments/matrix_state.json`，可断点续跑

### 4.2 使用方式

```bash
cd /home/houslakers/auto_tune_racer/swarmlio_multi

# 预演：打印矩阵 + 时间估算
python3 scripts/run_overnight_matrix.py plan

# 查看当前进度
python3 scripts/run_overnight_matrix.py status

# 夜间自动执行（可后台挂起：nohup ... &）
python3 scripts/run_overnight_matrix.py run
# 可选：--groups A1,B2 只跑指定组；--max-runs N 本次最多跑 N 个
```

### 4.3 监控兜底

执行器本身串行驱动，每个 run 结束后才启动下一个。额外的兜底：

```bash
# 另一终端实时看 telemetry 健康
python3 scripts/monitor_experiment.py

# 检查是否有 run 卡死 / 残留进程
pgrep -af "gazebo|rosmaster" | grep -v grep
```

### 4.4 每组耗时估算

- 启动 + readiness：约 2–3 分钟
- 300 sim-s 监控：约 23–28 分钟（实测 RT≈0.22–0.30）
- 收尾 + 收集：约 2 分钟
- **单 run 约 30 分钟，18 runs 约 9 小时（夜间可行）**

### 4.5 失败策略

- 单个 run 失败：记录 `status=failed` + 原因，继续下一 run
- 连续 2 个 run 失败：执行器停止，等待人工介入
- 资源门不满足：runner 自身在 launch 前拒绝（MemAvailable 等硬门）

---

## 5. 评价指标与判定标准

### 5.1 核心指标（每组从 runroot 提取）

| 指标 | 来源 | 判定 |
|------|------|------|
| `exit_reason` | `execution_result.json` | 必须 `duration_complete` |
| `final_safety_passed` | 同上 | 必须 `true` |
| fleet coverage ratio | `fleet/metrics.json` | 记录；A 组对比 120s 的 11.5% |
| makespan（最后完成时间） | `coverage_seq.json` 收敛点 | 组间比较 |
| 总路径长度 | 三机 `metrics.json` path_length_m 求和 | 组间比较 |
| 各机路径失衡比 | `max(path)/min(path)` | H1：MINMAX 组更低 |
| 各机 coverage 差 | 三机 observed_voxels 极差 | H1 佐证 |
| 掉线后 survivor coverage delta | `fleet/metrics.json` `post_dropout_coverage_delta` | H3：>0 |
| overlap_ratio / jaccard | `fleet/metrics.json` | 共享地图一致性 |
| abort_reasons | `fleet/metrics.json` | 必须 `[]` |
| 掉线分类 | `fleet/dropout.json` + classifications | 必须 `intentional_dropout` |

### 5.2 判定规则

- **通过**：`duration_complete + final_safety_passed + abort_reasons=[]`
  + 掉线组分类正确 + survivor coverage delta > 0。
- **组间优胜**（A/B 各自比较）：
  1. 先看完整搜图（fleet coverage ratio）——越高越好；
  2. 同 coverage 水平下看 makespan——越短越好；
  3. 同 makespan 下看总路径——越短越好；
  4. 均衡性：路径失衡比——越低越好（佐证）。

### 5.3 报告图（每 run 自动产出，对齐单机标准）

- `coverage.png`：上=俯视点云+轨迹+起终点；下=栅格数量累计增长曲线（每机+fleet）
- `grid_map.png`：5cm 灰度栅格
- `point_cloud.png`：二维俯视点云
- `coverage_seq.json`：growth 序列（供曲线复用）

---

## 6. 实验台账（执行器自动维护）

执行器每 run 结束自动追加 `experiments/matrix_results.jsonl`，并渲染
`experiments/matrix_results.md` 表格（18 行）。手动复核用：

```markdown
## <run key>（UTC 时间）

- runroot：`results/RUN-<ts>-3uav-smoke/`
- 配置：objective=MINSUM, capacity=0.75, dropout=<none|node_level@60s>
- manifest sha256 / approval issuance_id
- 结果：exit=... safety=... abort=[] dropout_cls=...
- fleet coverage=... ratio=... makespan=... 总路径=...
- 失衡比=... survivor delta=...
- 结论：PASS/FAIL（FAIL 原因）
```

---

## 7. 资源门与风险

### 7.1 硬门（不豁免）

- 启动 MemAvailable ≥ 8 GiB；运行 ≥ 3 GiB（实测本机 available 11 GiB，充足）
- swap delta ≤ 200,000；RT ≥ 0.5 尽力（历史偏差 p95=0.305，记录不放大）
- 每机 freeze/crash/contact/ack_timeout 逐机记录

### 7.2 风险与对策

| 风险 | 对策 |
|------|------|
| 300s 下 RT 偏差放大 wall time | 执行器 timeout 3600s/run；监控 RT |
| approval 消费后不能复用 | 执行器每 run 自动重签，issuance_id 唯一 |
| config 切换漏更新 hash | 执行器自动刷新 hash manifest + approval 绑定校验 |
| 无掉线组误触发掉线 | 独立 manifest `dropout.enabled: false`，执行器按组生成 |
| 三机探索负载本身不均衡 | 这正是本实验要测的；A1 作为参照 |
| 某 run crash/abort | 记录 FAIL 原因；连续 2 次失败暂停 |
| 执行器中途退出 | `matrix_state.json` 断点续跑，`run` 重进即可 |
| 远端 push 不通 | 本地提交保存历史（已确认可行） |

---

## 8. 执行顺序与前置检查清单

```text
□ python3 scripts/run_overnight_matrix.py plan   # 确认 18 runs 矩阵
□ runner / collector self-test 通过
□ 环境无残留进程（无 gazebo/rosmaster）
□ MemAvailable ≥ 8 GiB（本机 11 GiB 满足）
□ 执行器启动：python3 scripts/run_overnight_matrix.py run
□ 每 run 完成后 matrix_results.md 自动更新，人工/自动化核对
□ 全部完成后汇总对比表 + 更新报告图与 luna_review
```

---

## 9. 与最终目标的关系

- **完整搜图**：300s 下 fleet coverage ratio 是否收敛、接近全图（H4）。
- **最短时间/最短路径**：A 组选出最优 objective/容量组合，B 组确认其在掉线下仍最优。
- **图标准**：所有 run 的 `coverage.png` 上下两栏 + 栅格增长曲线 + 俯视点云，
  与单机旧标准一致，可直接进报告。
