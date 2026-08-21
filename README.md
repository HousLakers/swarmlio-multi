# SwarmLIO Multi-UAV Agent Workspace

多机调试编排层：共享工作树、任务包、状态摘要、事件账本和受限监控接口。
不复制或修改 `swarmlio-single` 源码。

公共环境同步见 [PLATFORM_ENVIRONMENT.md](PLATFORM_ENVIRONMENT.md)，当前固定使用
`racer-platform` commit `57c1f34`。环境配置完成不等于多机实验已经批准；当前 2-UAV
preflight 已通过，但首次 smoke 在 sim 32.39 fail-closed 中止，仍需完成最小诊断修复和
新的 preflight 审批。

当前单机 20 m 水平全向候选的冻结 commit、overlay hash、证据边界、导入顺序和
2-UAV 门禁见
[handoff/SINGLE_TO_MULTI_TRANSFER_20260820.md](handoff/SINGLE_TO_MULTI_TRANSFER_20260820.md)。
该文档是新多机会话的首要入口；单机结果只作为每节点 baseline。

第一步：读取 `state/current_summary.md` 和 `state/SESSION_HANDOFF.md`。当前 manifest
已经接入 approval-gated runner，但没有任何有效 approval package；不得直接运行
preflight 或 smoke。下列任务接口也不能视为实验批准：

```bash
python3 scripts/create_task.py two-uav-smoke
python3 scripts/monitor_experiment.py --once
```
