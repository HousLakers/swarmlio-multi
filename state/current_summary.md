# Current Summary

阶段：多机负载均衡 300s 矩阵实验已完成（18 runs：17 done / 1 failed），
绘图标准已修复（下方面板三机增长曲线清晰可见），当前进入报告与收尾。

冻结输入：`racer-platform@57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`、
`swarmlio-single-v2@08fb545a78ed7f1df2e1182a0e6d7a13540a28f6`、
`range20m_omnidirectional_v1`（22 文件），公共环境 `racer_outdoor_50x50_v1`。

## 负载均衡矩阵最终结论（18 runs，每组 300 sim-s）

### 矩阵结构（6 组 × 3 次重复）

- 无掉线：A1 `MINSUM+0.75`、A2 `MINMAX+0.75`、A3 `MINMAX+0.5`
- 掉线（uav1 node_level @ sim 60s）：B1 `MINSUM+0.75`、B2 `MINMAX+0.75`、B3 `MINMAX+0.5`

### 总体结果

- **17/18 done**，唯一失败 `A2-r3`：`duration_complete` 但
  `final_safety_passed=false`，残留 `abort.request` 为
  `corrupted_telemetry:topic_owner_probe_failed`（收尾残留，非算法失败）
- 所有 9 个掉线 run：`exit_reason=duration_complete`、`final_safety_passed=true`、
  uav1 分类全部 `intentional_dropout`，掉线后剩余机 coverage delta 全部 > 0
- 18/18 无 crash、无 contact、无 abort 残留（A2-r3 仅 final safety 收尾门触发）

### 分组统计（均值 ± 标准差，仅 done run）

| 组 | n | fleet ratio | 总路径 m | 路径失衡比 | Jaccard | overlap |
|---|---:|---:|---:|---:|---:|---:|
| A1 MINSUM 0.75 | 3 | 0.205±0.025 | 557±174 | 2.41±1.03 | 0.657±0.128 | 0.902±0.030 |
| A2 MINMAX 0.75 | 2 | 0.222±0.008 | 745±4 | 1.35±0.21 | 0.725±0.018 | 0.897±0.021 |
| A3 MINMAX 0.50 | 3 | 0.213±0.009 | 709±109 | 2.11±1.30 | 0.745±0.011 | 0.877±0.014 |
| B1 MINSUM 0.75 | 3 | 0.201±0.019 | 503±55 | 7.36±1.28 | 0.141±0.037 | 0.893±0.028 |
| B2 MINMAX 0.75 | 3 | 0.207±0.008 | 562±34 | 9.08±3.38 | 0.080±0.009 | 0.911±0.008 |
| B3 MINMAX 0.50 | 3 | 0.185±0.023 | 427±72 | 6.41±2.65 | 0.260±0.189 | 0.897±0.026 |

### 主要发现

1. **MINMAX 均衡性优于 MINSUM**：无掉线组 A2 失衡比 1.35 显著低于 A1 的 2.41，
   代价是总路径更长（745 m vs 557 m）
2. **掉线后失衡比大幅上升**：B 组失衡比 6.4–9.1，远高于 A 组（1.3–2.4），
   剩余机负载压力集中是掉线鲁棒性的主要代价
3. **掉线后 Jaccard 骤降**：B1/B2/B3 的 map consistency 0.08–0.26 vs A 组 0.66–0.75，
   掉线机地图贡献丢失导致共享一致性下降
4. **300s 下 fleet coverage ratio 0.19–0.22**：显著高于此前 120s 的 11.5%，
   但尚未达到完整搜图（H4 部分成立）

### 绘图修复（本轮新增）

- `coverage.png` 下方面板三条增长曲线（uav0/uav1/uav2）此前被黑色 fleet 线遮盖、
  半透明洗淡；已改为不透明彩色线置顶（zorder=10）、黑线淡化虚线（alpha=0.25）
- 上方面板轨迹图、`grid_map.png`、`point_cloud.png` 绘图函数未改动
- 18 个 run 全部重绘并验证三色线可见（commit `f31a3c2`）

## 当前状态

- 掉线实验 Route A（D0–D11）：已闭环（此前完成）
- 负载均衡矩阵：**已完成 18/18**（17 done + 1 failed 已记录）
- C1 最终最佳配置验证：待 A/B 分析后追加（未跑）
- 绘图标准：已修复并全量重绘

## 备注

- 执行器 `scripts/run_overnight_matrix.py` 支持断点续跑（`matrix_state.json`）
- 台账：`experiments/matrix_results.md` / `matrix_results.jsonl`
- 每 run 自动产出 `coverage.png` + `grid_map.png` + `point_cloud.png` +
  `coverage_seq.json`（三机 + fleet 增长序列）
- 后续任何新实验须重新签发 approval，不能复用已消费包
