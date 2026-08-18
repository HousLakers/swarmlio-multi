# SwarmLIO Multi-UAV Agent Workspace

多机调试编排层：共享工作树、任务包、状态摘要、事件账本和受限监控接口。
不复制或修改 `swarmlio-single` 源码。

公共环境同步见 [PLATFORM_ENVIRONMENT.md](PLATFORM_ENVIRONMENT.md)，当前固定使用
`racer-platform` commit `57c1f34`。环境配置完成不等于多机实验已经批准；仍需完成
2-UAV preflight、manifest 和 sol 审批。

第一步：填写 `handoff/SINGLE_UAV_BASELINE.md`，完善
`experiments/manifests/2uav_smoke.yaml`，再创建任务：

```bash
python3 scripts/create_task.py two-uav-smoke
python3 scripts/monitor_experiment.py --once
```
