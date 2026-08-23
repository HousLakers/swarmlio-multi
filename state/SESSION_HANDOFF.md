# SESSION_HANDOFF

## 当前目标

掉线实验 Route A（D0–D11）已完成并闭环。当前进入**多机负载均衡与图标准对齐**阶段：
先把多机图标准做成和单机一致，再以 300 sim-s 为每组时长，比较 `MINSUM` / `MINMAX`
以及 `capacity=0.75` / `0.5` 对完整搜图、完成时间和总路径的影响。

## 已完成事项（本轮）

- D0 掉线语义冻结：`state/dropout_experiment_plan.md` + `handoff/DROPOUT_EXPERIMENT_WORKFLOW.md` 批准。
- D1/D2 runner 掉线事件 + collector 掉线分类（`control_chain` / `communication` / `node_level`）。
- D3 2-UAV 掉线 rehearsal 通过。
- D4 分类强化（intentional_dropout / unexpected_loss / telemetry_missing）。
- D5 三机参数化；D6/D7 3-UAV config/launch/manifest + static 校验；D8 diagnostic preflight。
- D9 3-UAV control_chain 掉线 smoke 通过；uav2 冻结根因定位。
- D9r 源码修复：`sdf_map.clearVehicleBody(pos, r=0.8)` + `planTrajToView` 前置清理；
  collector `ack_timeout` 竞态误杀修复（可恢复语义，`command_ack_timeout_s=6.0`）。
- D10 3-UAV `node_level` 掉线 smoke 最终验证通过：
  - runroot `results/RUN-20260823T194616Z-3uav-smoke/`
  - `exit_reason=duration_complete`、`final_safety_passed=true`、`abort_reasons=[]`
  - uav1 掉线（node_level，sim 87.166s，三节点全杀）分类 `intentional_dropout`
  - 剩余机继续：uav0 +5,350、uav2 +24,231 voxels
  - 三机 freeze=false / crash=false / ack_timeout=0
- D11 报告与收尾：`state/luna_review.md` 按掉线模板重写；`current_summary.md` 更新；
  固定交付 `grid_path.png` + `point_cloud.png`（collector 收尾自动生成）
  且本次图基于 **无人机真实建图 voxel** 重做。
- 新增多机负载均衡计划：`MINMAX` 作为 makespan 候选，`capacity=0.5` 作为实验参数；
  图标准将对齐单机的上下两栏 `coverage.png` 与俯视 `point_cloud.png`。

## 最终身份链

- platform commit：`57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`
- single commit：`08fb545a78ed7f1df2e1182a0e6d7a13540a28f6`
- overlay：`range20m_omnidirectional_v1`
  - manifest `7c54d34ad5aa878a89fb07394b5efe88373fcdf848bbe0188b81b6fbdecb1f3c`（22 文件）
  - installer `8cabae8d6c8019cf49e4f3f6d836ac9c0fa7d26d6926e1140af8cc87c42ee5eb`
- 3-UAV manifest：`experiments/manifests/3uav_smoke.yaml`
  - SHA-256 `509e71fda25d275caae12f6d01246bf264ca3d1588c7a056853877764a29370f`
  - `duration_sim_s=300`（用户决策，每组 300s）
  - `dropout.mode=node_level`
- 3-UAV source hash manifest：`config/3uav_source_hashes.sha256`
  - SHA-256 `48ce54177330f445d4bb154fa2764f14c94d580e853c0dff3922bf300589f72e`
- 新 approval（待消费）：`load-balancing-20260824-3uav-300s-smoke`（max_uses=1）
- 已消费 approval：`dropout-smoke-20260824-3uav-D10-replay`（不得复用）

## 已知偏差（不阻断掉线语义结论）

- RT factor：全程实测 p50=0.278、p95=0.305（历史偏差，掉线语义 ≠ 实时性对比）。
- 资源门：本次 ready MemAvailable=3.45 GiB，满足 ≥3 GiB 门。
- 120 sim-s 内无 `completion` 触发（探索未收敛，属地图规模正常现象）。

## 固定交付约定（新增）

- 每个实验 run 的 collector 收尾自动输出：
  - `coverage.png`：上半部分为二维俯视点云 + 轨迹 + 起终点，下半部分为栅格累计增长曲线；
  - `grid_map.png`：5cm 灰度栅格图；
  - `point_cloud.png`：二维俯视点云图。
- 以上图形语义对齐单机旧标准，不再使用 3D 透视点云作为正式交付图。
- 本次 D10 重跑的图已按“真实建图数据”标准生成并替换旧版本。

## 下一阶段执行顺序

1. ✅ 新增 `coverage_seq.json`，记录每架机和 fleet 的累计 unique coverage voxel 随 sim-s 增长。
2. ✅ 重写多机绘图：`coverage.png` 上下两栏、`grid_map.png` 灰度栅格、`point_cloud.png` 二维俯视。
3. ✅ 将 ACVRP 目标和容量参数化，保留历史默认 `MINSUM + 0.75`。
4. ✅ 创建本地实验分支 `experiment/load-balancing`（RACER 仓库，含 D9r 修复 + MINMAX/容量参数化），已编译通过。
5. ✅ 完成静态检查、self-test、编译和参数回读；每组实验统一 `duration_sim_s=300`；approval 已重签为 `load-balancing-20260824-3uav-300s-smoke`。
6. ⬜ 按实验矩阵启动实验（当前尚未跑，等审核通过后再 launch）。

### 预注册实验矩阵（每组 300 sim-s）

- 无掉线：`MINSUM+0.75`、`MINMAX+0.75`、`MINMAX+0.5`。
- `uav1` 在 `sim_s=60` 进行 `node_level` 掉线：同样三组。
- 主要指标：完整搜图、makespan、总路径、coverage 增长率、各机负载差、overlap、Jaccard、掉线后 survivor coverage delta。

## 后续边界

- 任何新实验（含资源复跑）必须重新签发 approval package。
- 禁止把 `intentional_dropout` 写成 crash/contact；不外推单机/双机性能到 fleet。
- 禁止降低资源门（MemAvailable ≥3 GiB、swap delta ≤200000、RT 尽力 ≥0.5）。
- 禁止复用已消费 approval package / runroot。

handoff_status: READY
handoff_model: high-terminal
handoff_command:
掉线实验 Route A 已完成（D0–D11）。审核 `state/luna_review.md` 与最终 runroot 证据，
如需正式比赛口径请在资源更充裕主机复跑；后续新实验需重新签发 approval package。
