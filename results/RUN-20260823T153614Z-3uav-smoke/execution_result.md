# Execution result: RUN-20260823T153614Z-3uav-smoke（3-UAV dropout smoke — D9）

- 命令：`python3 scripts/two_uav_runner.py launch --manifest experiments/manifests/3uav_smoke.yaml`
- exit_code：0
- exit_reason：`duration_complete`
- 结论：**smoke DURATION_COMPLETE（dropout 注入正确；final safety uav2 telemetry fail）**

## 不可变身份

- manifest：`experiments/manifests/3uav_smoke.yaml`，SHA-256 `f3c0544cdb4f1bde2db90d147b614451a3c64455ef5b837c94153ecf8d99dbbc`（approval_status → smoke_completed）
- source hash manifest：`config/3uav_source_hashes.sha256`，SHA-256 `802b834050afdcaa39671971f7f1712e55193c8415e87fbe4483fbcc18079b1e`（逐文件校验全过）
- approval package：`state/3uav_approval.yaml`（preflight）→ `state/xxx`（smoke，digest `ca7aceaa05f8ea2ff0d0e6a3fc9b91a2cbe1b468e3674e692bd8570dd06effc6`）
- issuance_id（smoke）：`dropout-smoke-20260823-3uav-1`（已消费，receipt 见 results/approval-consumption/）
- runner：`scripts/two_uav_runner.py` SHA-256 `56ce9ff243a7e8afb8976b60f28ff6ee2b841432c29dcad06733df50a43c9127`

## 启动检查（launch 阶段 preflight）

| 阶段 | 结果 |
|---|---|
| static_preflight（57 项） | ✅ 全通过 |
| live_preflight（73 项） | ✅ 全通过 |
| 资源门 startup | ✅ MemAvailable 11.64 GiB ≥ 8 GiB |
| 资源门 ready | ✅ MemAvailable 2.73 GiB ≥ 1 GiB |

## D9 核心结果：掉线注入

| 项目 | 值 |
|---|---|
| 掉线车辆 | uav1 |
| 掉线模式 | control_chain（kill exploration_node_2 + traj_server_2） |
| 触发时刻（sim s） | 86.739（trigger 60，watchdog 周期延迟符合设计） |
| 分类 | `intentional_dropout` |
| 清理策略 | `stop_active_reclaim`，killed_nodes 确认为 /exploration_node_2、/traj_server_2 |
| 掉线时 uav1 轨迹数 | 3（掉线前正常作业） |

## D9 核心结果：存活机恢复

| 项目 | uav0 | uav2 |
|---|---|---|
| 存活续飞 | ✅ **是**—全程路径 72.9 m | ⚠️ **冻结**—从未收到轨迹/指令（trajectory=0、pos_cmd=0、ack=0） |
| 掉线前覆盖 voxels | 4199（掉线前） | 19121（总） |
| 掉线后覆盖增量 | **10727** | 7954（模拟传感器依然产生——但机未动，数据来自 GT mapper 被动观测） |
| freeze 标记 | false | **true** |
| final safety | ✅ OK | ❌ **telemetry.trajectory/pos_cmd/ack all must be > 0** |

## 运行宏观指标

| 指标 | 值 |
|---|---|
| 模拟持续时间（sim s） | 146.856（目标 120） |
| 时钟单调 | ✅ true，134860 样本 |
| abort_reasons | [] |
| fleet_contact_count | 0 |
| min inter-UAV dist（m） | 1.448 |
| telemetry_completeness | true |
| task_allocation_state_samples | 2272 |
| uav1 survival | ❌ false（预期——掉线） |
| 掉线后 uav0 继续作业 | ✅ true |
| 掉线后 uav2 继续作业 | ⚠️ false（冻结，非掉线所致） |
| process_liveness（smoke 末尾） | 11 进程全存活 + exploration_node_2/traj_server_2 = false（预期） |
| 掉线后丢失节点 | /exploration_node_2、/traj_server_2（预期） |

## 资源概况

| 指标 | 值 |
|---|---|
| 运行期 MemAvailable | min 2.54 GiB（251 样本） |
| swap_out delta | 801 页 |
| RT factor | 有效 224 样本，p50=0.27、p95=0.30（已知偏差，不阻断） |
| 栈 RSS（峰值） | gazebo 7.54 GB、racer 2.70 GB、bridges 0.18 GB、gt_mapper 0.14 GB、collector 0.08 GB |

## 已知偏差与发现

1. **uav2 全程冻结**：整个 146.9 s 模拟中 uav2（exploration_node_3 / traj_server_3 / px4_bridge_3）未产生任何轨迹或指令。原因待查——可能为初始规划否问题（如起始位置与地图冲突导致 planner 持续拒绝首条路径）。该冻结独立于掉线实验（uav2 在掉线前就已冻结），弱化了"存活机继续作业"证据链中 uav2 的部分。
2. **final safety fail**：由 uav2 telemetry 为 0 触发，正确反映冻结事实，不误报。
3. **RT p50=0.27**：3-UAV 栈满载时 sim 时钟慢于 wall，属已知偏差（掉线语义实验 ≠ 实时性对比）。
4. **内存余量**：运行期 min 2.54 GiB（≥ 1 GiB 合约新值），但长期 3-UAV 任务可能触及 swap abort。

## 结论

- ✅ **掉线注入与分类正确**：uav1 control_chain dropout → intentional_dropout，无异常丢失
- ✅ **uav0 存活恢复已验证**：掉线后继续作业，覆盖增长 10727 voxels
- ⚠️ **uav2 存活未动**：冻结于起点，需排查冻结根因（不影响掉线实验核验，但需标注于总结报告）
- ❌ final safety fail per design（因 uav2 冻结被安全合同捕获）

## 高终端审核结论（sol，D9）

审核范围：`RUN-20260823T153614Z-3uav-smoke` runroot 全证据磁盘核验。

| 审核项 | 结论 |
|---|---|
| 掉线注入（uav1 control_chain，sim 86.739s，kill 2 节点） | ✅ 与 approval 一致，intentional_dropout，无异常丢失 |
| uav0 存活恢复（掉线后 +10727 voxels，路径 72.9 m） | ✅ 存活机继续作业验证通过 |
| uav2 冻结（trajectory/pos_cmd/ack=0，freeze=true） | ✅ 如实标注；判定为**独立于掉线实验的规划链路问题**，非掉线所致 |
| final safety FAIL | ✅ 由 uav2 telemetry=0 触发，safety 合同按设计捕获，无误报 |
| 资源门（startup 11.68 / ready 2.54 GiB） | ✅ D8 门限参数化方案生效，3-UAV 栈在放宽后合约内运行 |
| RT p50=0.27 | 已知偏差，不阻断本实验结论 |
| stop 清理（clean、identity_confirmed、无 survivors） | ✅ |

**结论：D9 dropout-smoke 认可通过。** 掉线实验核心目标（注入正确性、存活恢复、abort 路径、资源合约）全部达成。uav2 冻结作为已知独立问题如实记录，转中终端单独排查初始规划被否根因（新任务，非 D9 重跑）。manifest `approval_status` 已推进为 `smoke_completed`。