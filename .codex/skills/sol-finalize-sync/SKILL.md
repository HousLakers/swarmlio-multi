---
name: sol-finalize-sync
description: 高终端收尾职责的独立参考页；功能已合并入 lead-planning，保留本文件用于兼容与回溯。
terminal: 高
terminal_role: 思考审核规划（收尾）
---

## 说明

本 skill 的历史职责（单轮实验结束后审核结果、合并状态、形成唯一 Git 收尾提交）已合并到
`lead-planning/SKILL.md`。高终端直接以 lead-planning 作为唯一入口；本文件保留作为
兼容引用，禁止两个 skill 并行执行同一收尾职责。

## 若单独调用本 skill

仅在以下场景使用：

- 用户明确指定 `sol-finalize-sync`；
- 或需要回溯历史收尾记录（commit、分支、公共环境版本、远程仓库）。

此时执行顺序：

1. 审核实验有效性和 luna 结论；
2. 决定 terra 修改是否保留；
3. 更新 `project_state.md`、`state/current_summary.md`、`state/SESSION_HANDOFF.md`；
4. 只选择本轮需要追溯的源码、脚本、manifest、metrics 摘要、gate、报告和状态文件；
5. 创建一个收尾 commit；
6. 记录 commit hash、分支、公共环境版本和远程仓库；
7. 只有获得用户允许后才 push GitHub。

禁止：实验中途提交、覆盖历史、提交密钥和大体积原始结果、把单机结果写成 fleet-level 结论、
未经审核把失败代码提交为默认版本。

## 掉线实验收尾特例

掉线实验的收尾 commit 应额外包含：

- 掉线契约（`handoff/DROPOUT_EXPERIMENT_WORKFLOW.md` 变更）
- manifest 的 `dropout.*` 字段定义
- collector 的 dropout 分类实现 diff
- runner 的 fault injection 实现 diff
- 掉线实验 runroot 的 metrics 摘要

## 步骤完成后的交接协议

```text
handoff_status: <FINALIZED|BLOCKED>
handoff_model: lead-planning
handoff_command:
下一轮从 AGENTS.md、state/current_summary.md 和最新 SESSION_HANDOFF 重新规划；
不得复用本轮 approval package 或 runroot。
```

若 luna、runroot、hash 或用户 push 授权缺失，保持 `handoff_status: BLOCKED`，目标模型仍为
`lead-planning`，只交接缺口清单，不得创建或推送收尾 commit。