# Load-balancing matrix results (300s)

| Run | Group | Objective | Capacity | Dropout | Status | Exit | Safety | Runroot |
|-----|-------|-----------|----------|---------|--------|------|--------|---------|
| A1-r1 | A1 | MINSUM | 0.75 | none | done | duration_complete | True | results/RUN-20260823T213717Z-3uav-smoke |

## A1-r1 详情（MINSUM + 0.75，无掉线，300s）

- runroot：`results/RUN-20260823T213717Z-3uav-smoke`
- exit_reason：`duration_complete`；final_safety_passed：`True`；abort_reasons：`[]`
- fleet coverage：48,717 voxels（18.1%）；overlap：0.93；jaccard：0.52
- min inter-UAV distance：1.441 m；fleet contacts：0
- 三机 completion 均已触发（300s 内探索收敛，120s 时从未出现）
- 各机路径：uav0=59.5m，uav1=129.3m，uav2=214.0m → 失衡比 **3.60×**
- 各机 coverage：uav0=25,868，uav1=26,753，uav2=46,572
- 掉线分类：全部 `none`（本组无掉线）
- 结论：**PASS** —— MINSUM 基线在 300s 完成收敛，但负载严重不均（uav2 承担 53% 路径），为 MINMAX 对照提供基线
