# SESSION_HANDOFF

## 当前目标

掉线实验 Route A（D0–D11）与多机负载均衡矩阵均已闭环。当前进入**报告与收尾**阶段：
整理负载均衡 300s 矩阵（6 组 × 3 次 = 18 runs）的最终结论、修复绘图标准、
按需补跑 A2-r3 与 C1 最终验证。

## 已完成事项（本轮）

### 掉线实验 Route A（此前完成，背景）

- D0 语义冻结 → D1/D2 注入与分类 → D3 2-UAV rehearsal → D4 分类强化 →
  D5 三机参数化 → D6 3-UAV 资产 → D7 实例化 → D8 preflight → D9/D10 掉线 smoke
  → D11 收尾，全链路闭环。
- D10 node_level 最终验证：`RUN-20260823T194616Z-3uav-smoke/`，
  `final_safety_passed=true`，uav1=`intentional_dropout`，剩余机继续。

### 负载均衡矩阵（本轮核心）

1. **执行器**：新增 `scripts/run_overnight_matrix.py`：
   - 内置矩阵（6 组 × 3 次 = 18 runs，每组 300 sim-s）
   - 每 run 自动完成：per-group manifest → config exploration 段 →
     source-hash manifest → 独立 approval 重签 → frozen runner launch →
     结果台账（`matrix_results.jsonl` / `.md`）
   - 状态机持久化（`matrix_state.json`），支持断点续跑；连续 2 次失败自动停止
2. **夜间执行完成**：20260823T213717Z → 20260824T032400Z
   - **17/18 done**，唯一失败 `A2-r3`：
     `duration_complete` 但 `final_safety=false`，残留
     `corrupted_telemetry:topic_owner_probe_failed`（收尾安全门，非算法失败）
   - 掉线组 9/9 全通过：`intentional_dropout` 分类正确，剩余机 coverage delta 全 > 0
3. **绘图修复**：`coverage.png` 下方面板三条增长曲线此前被黑线遮盖/洗淡，
   已改为不透明彩色线置顶 + 黑色 fleet 线淡化虚线；18 个 run 全部重绘验证
   （commit `f31a3c2`）
4. **报告更新**：`state/current_summary.md`、`state/luna_review.md`（追加矩阵专项）、
   `experiments/matrix_results.md` 全部更新

## 最终身份链

- platform commit：`57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`
- single commit：`08fb545a78ed7f1df2e1182a0e6d7a13540a28f6`
- overlay：`range20m_omnidirectional_v1`
  - manifest `7c54d34ad5aa878a89fb07394b5efe88373fcdf848bbe0188b81b6fbdecb1f3c`（22 文件）
  - installer `8cabae8d6c8019cf49e4f3f6d836ac9c0fa7d26d6926e1140af8cc87c42ee5eb`
- 3-UAV manifest：`experiments/manifests/3uav_smoke.yaml`
  - `duration_sim_s=300`、`repetitions=3`
- 执行器：`scripts/run_overnight_matrix.py`
- 矩阵状态：`experiments/matrix_state.json`（finished_utc=20260824T032400Z）

## 已消费 approval

- 掉线实验各阶段包（D3/D5/D8/D9/D10 等，均不得复用）
- 矩阵 18 runs 每 run 独立重签包（全部消费，receipt 在 `results/approval-consumption/`）

## 已知问题与风险

1. **A2-r3 失败**：`corrupted_telemetry:topic_owner_probe_failed` 残留导致
   final safety fail；仿真完整，非算法问题。如需 18/18 口径可单独重跑。
2. **RT 偏差**：p95≈0.31（历史主机负载偏差），未放宽任何资源门。
3. **覆盖率未收敛**：300s 下 fleet ratio 0.19–0.22，未达到完整搜图（50×50 m 地图）。
4. **B 组 Jaccard 骤降**（0.08–0.26）：掉线机地图贡献丢失的预期代价，需在报告中
   明确为鲁棒性代价而非故障。
5. **C1 未执行**：最终最佳配置验证待 A/B 分析后追加。

## 三终端下一步唯一动作

- **高终端（lead-planning）**：审核本交接 + `luna_review.md` 矩阵专项；
  决定是否补跑 A2-r3 / 执行 C1；批准收尾 commit + push。
- **中终端（low-level-implementation）**：无待办代码；如需补跑请确认
  无源码漂移（hash manifest 已与工作树一致）。
- **低终端（experiment-execution）**：若批准补跑 A2-r3，用执行器
  `python3 scripts/run_overnight_matrix.py run --groups A2` 单组重跑
  （执行器会自动跳过已完成 run，仅执行失败项）。

## 禁止事项

- 复用任何已消费 approval package / runroot。
- 把 `intentional_dropout` 写成 crash/contact。
- 降低资源门（MemAvailable ≥3 GiB、swap delta ≤200,000、RT 尽力 ≥0.5）。
- 修改冻结的单机参数 / 环境 baseline。
- 在实验期间 commit/push 或切换分支（收尾 commit 除外）。

## 新会话首读文件清单

1. `AGENTS.md`
2. `handoff/TERMINAL_HANDOFF_PROTOCOL.md`
3. `state/current_summary.md`
4. `state/SESSION_HANDOFF.md`
5. `state/luna_review.md`
6. `experiments/PLAN_LOAD_BALANCING_300S.md`
7. `experiments/matrix_results.md`
8. `experiments/manifests/3uav_smoke.yaml`

```text
handoff_status: READY
handoff_model: lead-planning
handoff_command:
负载均衡矩阵 17/18 完成（唯一失败 A2-r3 为收尾安全门残留）。Luna 判定掉线鲁棒性与
MINMAX 均衡性成立。请审核 luna_review.md 矩阵专项与 matrix_results.md；决定是否
补跑 A2-r3 与执行 C1；批准收尾 commit + push（commit 格式 stage: LB-matrix closeout）。
```
