# 多机掉线负载均衡实验详细计划（每组 300s）

> 状态：`计划定稿，等待执行批准`
> 前置：P0（绘图标准）P1（MINMAX/容量参数化）已完成并本地提交；
> approval 已重签为 `load-balancing-20260824-3uav-300s-smoke`（尚未消费）。
> 本文档是第四步"跑实验"的执行蓝本。

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

## 2. 实验矩阵（7 组，每组 300 sim-s）

| 组 | ID | 掉线 | 目标函数 | 容量 | 用途 |
|----|----|------|---------|------|------|
| A1 | `no-drop-minsum-075` | 无 | MINSUM | 0.75 | 历史默认基线 |
| A2 | `no-drop-minmax-075` | 无 | MINMAX | 0.75 | 评估 MINMAX 单独效果 |
| A3 | `no-drop-minmax-050` | 无 | MINMAX | 0.50 | 评估 MINMAX + 容量降低 |
| B1 | `drop-minsum-075` | uav1@60s node_level | MINSUM | 0.75 | 掉线基线 |
| B2 | `drop-minmax-075` | uav1@60s node_level | MINMAX | 0.75 | 掉线 + MINMAX |
| B3 | `drop-minmax-050` | uav1@60s node_level | MINMAX | 0.50 | 掉线 + MINMAX + 容量 |
| C1 | `final-best-config` | 依 A/B 结果 | 最佳 | 最佳 | 最终验证（可选） |

**常量**（所有组）：

- `duration_sim_s: 300`
- 地图：`racer_outdoor_50x50_v1`（50×50×3 m，planner box ±24.5）
- 种子：`20260823`；3 UAV；起飞位置固定
- 掉线组统一：`uav1`、`node_level`、`trigger_sim_s: 60`、`stop_active_reclaim`
- `repetitions: 1`（若某组失败/资源门不过，允许重跑该组并记录）

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

## 4. 每组执行流程

### 4.1 标准流程（每组重复）

```bash
cd /home/houslakers/auto_tune_racer/swarmlio_multi

# 0) 环境检查：确保无残留进程
ls /tmp/swarmlio_multi_2uav_active.json 2>/dev/null && echo "残留! 先 stop"
pgrep -af "gazebo|rosmaster" | grep -v grep || echo "环境干净"

# 1) 确认/修改 config 的 exploration 段
vim config/3uav_static.yaml

# 2) 更新 source hash manifest + 重算哈希 + 重签 approval（见第 3 节）

# 3) runner 自测（快速门）
python3 scripts/two_uav_runner.py --self-test

# 4) 静态 preflight（可选但推荐首组）
python3 scripts/two_uav_runner.py preflight --manifest <manifest>

# 5) launch（含 live preflight + watchdog soak + 掉线注入 + 300s 监控）
python3 scripts/two_uav_runner.py launch --manifest <manifest>
# 等待约 25–30 分钟 wall time（300 sim-s / RT≈0.28）

# 6) 结果收集与绘图（collector finalize 已自动产出三张图 + coverage_seq.json）
python3 scripts/two_uav_runner.py collect --manifest <manifest>

# 7) 记录 runroot 到实验台账（第 6 节）
```

### 4.2 每组耗时估算

- 启动 + readiness：约 2–3 分钟
- 300 sim-s 监控：约 23–28 分钟（实测 RT≈0.22–0.30）
- 收尾 + 收集：约 2 分钟
- **单组约 30 分钟，7 组约 3.5–4 小时**

### 4.3 监控

```bash
# 另一终端实时监控（看 telemetry 是否健康、coverage 是否增长）
python3 scripts/monitor_experiment.py
```

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

## 6. 实验台账（每完成一组就记录）

新建 `experiments/matrix_results.md`，逐组记录：

```markdown
## <组ID>（UTC 时间）

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
| 300s 下 RT 偏差放大 wall time | 监控 RT；若 wall 超 40 分钟考虑中断重跑 |
| approval 消费后不能复用 | 每组建独立 manifest+approval，绝不共享 |
| config 切换漏更新 hash | 用 `sha256sum` 校验 + `--self-test` 门 |
| 无掉线组误触发掉线 | manifest `dropout.enabled: false` 单独校验 |
| 三机探索负载本身不均衡 | 这正是本实验要测的；A1 作为参照 |
| 某组 crash/abort | 记录 FAIL 原因；是否重跑由结果决定 |
| 远端 push 不通 | 本地提交保存历史（已确认可行） |

---

## 8. 执行顺序与前置检查清单

```text
□ 每组 config 的 exploration 段与矩阵一致
□ 无掉线组使用 dropout.enabled:false 的独立 manifest
□ source hash manifest 与 static config 一致（sha256sum 核对）
□ approval 的 manifest/source-hash 绑定正确（runner self-test + 手动核对）
□ 环境无残留进程
□ 每组 launch 前记录预注册组 ID
□ 每组完成后更新 experiments/matrix_results.md
□ 全部完成后汇总对比表 + 更新报告图与 luna_review
```

---

## 9. 与最终目标的关系

- **完整搜图**：300s 下 fleet coverage ratio 是否收敛、接近全图（H4）。
- **最短时间/最短路径**：A 组选出最优 objective/容量组合，B 组确认其在掉线下仍最优。
- **图标准**：所有 run 的 `coverage.png` 上下两栏 + 栅格增长曲线 + 俯视点云，
  与单机旧标准一致，可直接进报告。
