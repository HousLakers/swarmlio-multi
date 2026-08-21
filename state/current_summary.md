# Current Summary

阶段：2-UAV 静态接入和 live preflight 已通过；首次 120 sim s smoke 在 sim 32.39
fail-closed 中止。当前为 `SMOKE_FAIL_DIAGNOSIS / NO_ACTIVE_APPROVAL`，不得重试实验。

冻结输入：`racer-platform@57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`、
`swarmlio-single@c01f1f5af40ec25631aa11765a0f21e06834abc4`、
`range20m_omnidirectional_v1` 和公共环境 `racer_outdoor_50x50_v1`。

有效 preflight：`results/RUN-20260821T082048Z-2uav-preflight/`，静态 53/53、live 48/48、
8/8 节点、双机 payload/TF/owner/参数/日志和 final safety 全通过。

失败 smoke：`results/RUN-20260821T083254Z-2uav-smoke/`，`exit_reason=abort_requested`。
uav0 trajectory 1、pos_cmd/ACK 278/278、移动 3.38 m；uav1 trajectory/pos_cmd/ACK 全 0、
freeze=true。直接 abort 是事件型 trajectory 被错误按 5 s 连续 freshness 监管；真实问题还
包括 uav0 A* timeout/no path 与 uav1 起点处于 inflated occupancy。peer-body LiDAR 回波污染
共享地图只是待诊断假设，尚未证实。RT factor≈0.339。

下一步唯一动作：由 lead 按 `state/sol_plan.md` 第 19 节向 Terra 签发最小修复任务：
collector trajectory event/presence 分类、GT mapper 近机点诊断/有证据的紧致机体剔除、
runner 每机 command 链最终有效性门。只做离线验证，完成后重新审核并先签发新的单次
preflight；不得直接 smoke。

已消费且禁止复用：preflight package `57a21fa5…b9fa4`、smoke package
`3986a46c…0038`。当前无有效 approval package。禁止现场调参、修改冻结单机参数、复用
runroot/package、长跑、参数搜索或把本轮写成 fleet PASS。
