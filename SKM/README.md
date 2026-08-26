# SKM：20% 丢包鲁棒性（工作二）—— 对称生效 + 自愈协议

> 由 SKM 提供，供队友同步。目标：满足赛题"通信断续（丢包率≤20%）情况下保持核心任务不中断"。
> 对应代码基线：RACER `049c332`（与 racer-platform 冻结基线一致）。

## 一、改动文件（4 个，相对 RACER 根路径）

| 文件 | 工作二改动点 | 备注 |
|------|-------------|------|
| `swarm_exploration/exploration_manager/src/fast_exploration_fsm.cpp` | ① `optTimerCallback`：**发送即生效（乐观应用+备份）**、待确认提案**同 stamp 周期重传**（0.2s）+ 超时（1.5s）；② `optMsgCallback`：同 stamp 重复请求**幂等重答** + 丢包模拟入口；③ `optResMsgCallback`：status=2 **回滚**到提案前分配 + 丢包模拟入口；④ `simulateDrop()`（丢包模拟实现）；⑤ 3 个参数加载（fsm/opt_retry_interval、opt_timeout、sim_drop_rate） | ⚠️ 同文件还含**工作一（掉线任务重分配）**：`offlineCheckTimerCallback` 的掉线释放+最近在线机接管、`droneStateMsgCallback` 的心跳冲突自愈（id 小者保留）。建议按函数选择性合入，不要整文件覆盖 |
| `swarm_exploration/exploration_manager/include/exploration_manager/fast_exploration_fsm.h` | `simulateDrop` 声明 | 纯净 |
| `swarm_exploration/exploration_manager/include/exploration_manager/expl_data.h` | FSMParam 新增 `opt_retry_interval_/opt_timeout_/sim_drop_rate_`；FSMData 新增 `sim_drop_count_`；ExplorationData 新增对称协议字段（`pre_opt_ego_ids_/pre_opt_other_ids_`、`last_opt_send_time_`、`pair_opt_target_id_`、`last_opt_response_status_`、`pair_opt_sent_count_/opt_reverted_count_/conflict_resolved_count_`） | ⚠️ 同文件也含工作一字段（DroneState 的 `is_online_/offline_miss_count_`）与负载均衡字段（`mtsp_objective_/capacity_factor_`） |
| `swarm_exploration/exploration_manager/launch/single_drone_planner.xml` | 新增 3 个参数：`fsm/opt_retry_interval=0.2`、`fsm/opt_timeout=1.5`、`fsm/sim_drop_rate=0.0` | ⚠️ 本文件还含负载均衡参数（mtsp_objective/capacity_factor）与本机环境参数（sdf 分辨率/地图盒/感知距离等，与本机 30×30 环境绑定）。**建议只摘出 3 个 fsm/opt_* 参数行**，不要整文件覆盖 |

## 二、协议原理（四层保障）

1. **发送即生效**：发送方算出分配后立即本地应用（备份旧分配），响应只用于停止重传/统计，不再决定生效时机——"响应包丢失"不再产生双方所有权分歧；
2. **同提案重传 + 幂等重答**：待确认提案每 0.2s 重传同一 stamp；接收方对重复提案重新应答（修复原"重复请求丢弃不答"导致发送方永远等不到响应）；
3. **心跳自愈**：25Hz 心跳广播各机网格清单；双方同时持有同一网格时按 **id 小者保留** 释放（双方独立得出相同结论）；无人认领网格经 findUnallocated/pair-opt 自动重分配；
4. **异常路径**：明确拒绝（status=2）→ 回滚；1.5s 超时 → 保留乐观状态、靠心跳自愈兜底。

## 三、合入方法（重要）

1. 本文件是我们本机环境的版本，其中 fsm.cpp / expl_data.h / planner.xml **同时含工作一（掉线接管）、负载均衡参数化与本机环境参数**，队友若已有自己的单机机制版本，请**按"一、改动文件"表格中的函数/字段清单选择性合入**，避免整文件覆盖丢你自己的改动；
2. 若你的 RACER 基线与 `049c332` 一致且未改过这些文件，可直接替换；
3. 合入后重新编译：`cd ~/racer_ws && catkin_make`（通过 `Built target exploration_node` 即成功）。

## 四、验证方法

1. 默认 `fsm/sim_drop_rate=0.0`（不丢包，正常比赛运行不受影响）；
2. 演示/测试 20% 丢包：把 `single_drone_planner.xml` 中 `fsm/sim_drop_rate` 改为 `0.2`（**仅改 XML，无需重编译**），在 pair_opt / pair_opt_res / drone_state 三个收包处按 20% 概率随机丢弃；
3. 预期日志：`[droploss] 模拟丢包 20%...`、`[heal] Drone X 释放 N 个与 Drone Y 冲突的网格(id 小者保留)`、`[opt] ... 重传提案...`；
4. 判定：300s 完整运行、无崩溃、覆盖率不低于 0% 丢包基线的 95%、无永久性重复覆盖/任务遗漏。

## 五、已在本机的验证数据

| 轮次 | 丢包率 | map_coverage | 说明 |
|------|--------|--------------|------|
| A | 0% | 0.641 | 含 75s 单机掉线接管测试 |
| B | **20%**（累计丢 2600+ 条） | **0.722** | 自愈 31 次、掉线接管正常、零崩溃 |

（0% 丢包基线历史数据 0.657~0.673；20% 丢包覆盖率保持 ≥95%。）

## 六、配套说明

- 本目录下 4 个文件与我们的工作一（掉线任务重分配，含 msg int32 修复、越界守卫、最近在线机接管）是同一套工作区代码；如队友需要工作一的完整文件清单，另行提供。
- 三方合并中间产物（base/ours/theirs/merged）与回归验证记录保存在 SKM 本地（未上传）。
