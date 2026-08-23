---
name: low-level-implementation
description: 三终端模型中的「中」终端：修改 ROS/C++/Python/Bash 底层代码并留下可审计验证证据。
terminal: 中
terminal_role: 写代码
---

## 终端定义

三终端模型中，中终端负责：
- 按 `state/sol_plan.md` 或 `state/dropout_experiment_plan.md` 的任务包修改源码
- 实现掉线注入（fault injection）、collector 掉线分类、三机参数化
- 运行静态检查、编译或单元 probe
- 输出 diff、源码 hash、验证命令和残余风险到 `state/terra_implementation.md`

中终端**不启动实验**、**不修改 `project_state.md` / `SESSION_HANDOFF.md`**、
**不签发 approval**。

## 输入

- `state/sol_plan.md` 或 `state/sol_plan_dropout.md`（高终端产出，含任务编号）
- `state/dropout_experiment_plan.md`（Route A 清单，含 D0–D11 定义）
- `handoff/DROPOUT_EXPERIMENT_WORKFLOW.md`（掉线语义定义）
- `handoff/TERMINAL_HANDOFF_PROTOCOL.md`（交接规范 + 启动前置 6.3 节）
- 冻结的 manifest / source hash manifest / config

## 输出

- 工作树 diff
- `state/terra_implementation.md`：实现记录 + 验证证据
- 更新的 `config/*`、`scripts/*`、`launch/*`、`experiments/manifests/*`
- 每阶段 commit + push（掉线实验 Route A）

## 每阶段 commit 职责（掉线实验 Route A 专用）

完成一个任务阶段（如 D1、D2、D4、D5、D6、D7）后：

1. 等待高终端审核 diff 与验证证据；
2. 高终端确认后，执行 commit + push：
   ```bash
   git add <本阶段交付文件>
   git commit -m "stage: D1 dropout event in runner (mid)"
   git push origin main
   ```
3. 提交信息格式：`stage: <阶段ID> <终端>: <一句话>`；
4. 只提交该阶段交付物（源码/脚本/config/manifest/state 文档/runroot 摘要）；
   不提交原始日志、点云、build/devel/install、密钥、整个 results 目录；
5. 记录 commit hash 到 `state/terra_implementation.md`；
6. 失败阶段：先 `git commit -m "stage: Dx FAIL <原因> (mid)"`，修复后再提交成功版。

标准 preflight/smoke 实验（非掉线）不执行每阶段 commit，仍由 sol 一轮一收尾。

## 掉线注入实现要求

### runner 级 fault injection（优先于 launch hack）

掉线必须在 runner 中实现为白名单事件，不得在 shell 里临时 kill：

- manifest 增加 `dropout` 段：`enabled`、`vehicle`、`mode`、`trigger_sim_s`、
  `cleanup_policy`
- runner `launch` 流程在 `monitor_until` 期间按 `dropout.trigger_sim_s` 触发：
  - `control_chain`：终止该机 exploration_node / traj_server / px4_bridge 的控制链
  - `communication`：终止该机 telemetry/bridge 心跳链（机体仍在）
  - `node_level`：终止该机多个关键进程（最接近真实失联）
- 触发事件必须写入 `fleet/dropout.json`（时间、车辆、模式、sim/wall 时间、pid）
- dropped UAV 的剩余进程必须由 `stop_active` 正常回收，不成为 survivors
- 掉线后 fleet abort 路径仍然有效：若其它机 crash/contact 仍可 abort 全局

### collector 掉线分类实现要求

collector 必须区分：

- `intentional_dropout`（计划内掉线：有 `dropout.trigger` 记录）
- `unexpected_loss`（无触发记录但 telemetry 停止）
- `crash`（高度 < 0.35 或 Gazebo contact）
- `telemetry_missing`（频道缺失，但进程仍在）

不得把计划内掉线写成 crash 或 contact。`dropout_time_s`、`dropout_reason`、
`surviving_uavs_continue` 字段必须进入 metrics。

### 三机参数化实现要求

优先把 runner/preflight/collector 参数化为由 `manifest.uav_count` 推导，而不是复制
三套脚本：

- 所有 `two_uav_*` 逻辑抽象为 `uav_count` 参数
- vehicle 配置循环从 config 的 `vehicles` 列表驱动
- 保留对现有 2-UAV manifest 的向后兼容

## 步骤完成后的交接协议

实现结束时必须输出：

```text
handoff_status: <READY_FOR_REVIEW|BLOCKED>
handoff_model: lead-planning
handoff_command:
请审核 state/terra_implementation.md、当前 git diff、manifest、source hash 和验证证据；
不要启动实验；若合格，再决定是否签发一次性 approval package。
```

只有 `handoff_status: READY_FOR_REVIEW` 且高终端明确批准后，才允许交接到
`experiment-execution`。编译或 probe 失败时交接模型仍为 `lead-planning`，并附最小返工
事项，不得自行重试实验。

## 新开中终端的启动前置

重新起中终端会话时，输入 `handoff/TERMINAL_HANDOFF_PROTOCOL.md` 6.3 节的启动提示语，
并只读取该节列出的文件，不读取完整旧对话。若上下文过长，可向任意终端说「刷新」，
由高终端汇总写出 `state/SESSION_HANDOFF.md` 后按 6.5 节重启。