# Current Summary

阶段：D10 node_level smoke 已完成，`final_safety_passed=true`，当前进入 D11 报告与收尾。

冻结输入：`racer-platform@57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`、
`swarmlio-single-v2@08fb545a78ed7f1df2e1182a0e6d7a13540a28f6`、
`range20m_omnidirectional_v1`，公共环境 `racer_outdoor_50x50_v1`。

## 最终 D10 smoke 结论

- runroot：`results/RUN-20260823T190024Z-3uav-smoke/`
- 结果：`exit_reason=duration_complete`，`final_safety_passed=true`，`abort_reasons=[]`
- 掉线模式：`node_level`，uav1 在 sim 60s 触发，分类 `intentional_dropout`
- 机体结果：
  - uav0：`freeze=false`、`crash=false`、`ack_timeout=0`
  - uav1：`dropout=true`、`mode=node_level`、`freeze=false`、`crash=false`
  - uav2：`freeze=false`、`crash=false`、`ack_timeout=0`
- 三机都完成了有效轨迹推进；uav2 从此前的“起点陷阱/冻结”问题中恢复

## 关键修复链

1. `sdf_map` 新增 `clearVehicleBody(pos, radius=0.8)`，消除共享地图把机体扫成障碍的误标
2. `planTrajToView()` 在规划前先清理本机体素，A* 不再把起点判死
3. collector 侧 `ack_timeout` 改为可恢复语义，避免 pos_cmd / ack 时序竞态误杀
4. `node_level` 掉线模式在 D10 中完成最终验证

## 当前状态

- D9：已通过
- D10：已通过
- D11：已完成（报告与收尾，见 `state/luna_review.md`）
- 本轮掉线实验 Route A 已闭环（D0–D11）

## 备注

- 本轮推送已完成，且只推送了可推送内容
- 每个实验 run 固定产出 `grid_path.png` + `point_cloud.png`（collector 收尾自动生成）
- 后续若需要新增实验，应重新签发新的 approval package，不能复用已消费包
