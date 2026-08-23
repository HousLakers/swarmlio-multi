# SESSION_HANDOFF

## 当前目标

掉线实验 Route A（D0–D11）已完成并闭环。本交接描述最终状态、身份链和后续边界，
供下一轮会话直接接续。

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
  - runroot `results/RUN-20260823T190024Z-3uav-smoke/`
  - `exit_reason=duration_complete`、`final_safety_passed=true`、`abort_reasons=[]`
  - uav1 掉线（node_level，sim 86.65s，三节点全杀）分类 `intentional_dropout`
  - 剩余机继续：uav0 +7,461、uav2 +10,212 voxels
  - 三机 freeze=false / crash=false / ack_timeout=0
- D11 报告与收尾：`state/luna_review.md` 按掉线模板撰写；`current_summary.md` 更新；
  固定交付 `grid_path.png` + `point_cloud.png`（collector 自动生成）。

## 最终身份链

- platform commit：`57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`
- single commit：`08fb545a78ed7f1df2e1182a0e6d7a13540a28f6`
- overlay：`range20m_omnidirectional_v1`
  - manifest `7c54d34ad5aa878a89fb07394b5efe88373fcdf848bbe0188b81b6fbdecb1f3c`（22 文件）
  - installer `8cabae8d6c8019cf49e4f3f6d836ac9c0fa7d26d6926e1140af8cc87c42ee5eb`
- 3-UAV manifest：`experiments/manifests/3uav_smoke.yaml`
  - SHA-256 `d9a64bf7b469ef85954fffdb09e7c9143b8b6b72b18b735477852a0e0265ebfe`
  - `dropout.mode=node_level`（D10 最终版本）
- 3-UAV source hash manifest：`config/3uav_source_hashes.sha256`
  - SHA-256 `e4c79a5ce232254199ea319773cc28eb7955db909e5a880f24f226b190048ec9`
- 已消费 approval：`dropout-smoke-20260823-3uav-D10-node_level`（不得复用）

## 已知偏差（不阻断掉线语义结论）

- RT factor：全程实测 p50 < 0.5（历史偏差，掉线语义 ≠ 实时性对比）。
- ready MemAvailable：2.76 GiB < 3 GiB 门限（3-UAV 栈 ≈9.3 GiB，16 GB 主机边界）。
  若需正式 PASS 口径，须在资源更充裕主机复跑 preflight + smoke。
- 120 sim-s 内无 `completion` 触发（探索未收敛，属地图规模正常现象）。

## 固定交付约定（新增）

- 每个实验 run 的 collector 收尾自动输出 `grid_path.png`（top-down 栅格路径）与
  `point_cloud.png`（点云），保存在对应 runroot。

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
