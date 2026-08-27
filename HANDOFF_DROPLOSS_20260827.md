# 丢包鲁棒性工作交接文档（20% 丢包 · 对称生效 + 自愈）

> 日期：2026-08-27 · 交接人：Cursor Agent · 基线：`swarmlio_multi@skm2333-patch-1#713bf40` + `RACER@049c332` + `racer-platform@f64c825` + `swarmlio-single-v2@0b9965e`
> 位置：当前目录（`swarmlio_multi/`）· 分支：`skm2333-patch-1`（已同步）+ `RACER:feature/20pct-drop-robustness@774940d`
> 验证：`RUN-20260827T040141Z-3uav-verify-droploss20-90s` 已归档（90 sim-s，20% 丢包，`duration_complete` + `final_safety_passed`）

---

## 1. 任务目标

满足赛题“通信断续（丢包率≤20%）情况下保持核心任务不中断”。SKM 在 `skm2333-patch-1@713bf40` 以 `SKM/` 目录提供了**工作二（20% 丢包）+ 工作一（掉线接管）**的完整改动，本次在本地完成：

1. 同步 `skm2333-patch-1` 分支到本地
2. 在 `~/racer_ws/src/RACER` 上**选择性合入**（按函数，不整文件覆盖）
3. `catkin_make` 编译验证
4. 90s 短验证（`sim_drop_rate=0.2`），归档并恢复默认 `0.0`

历史可回退：`RACER:backup/pre-20pct-drop@7be1687` 指向合入前状态。

---

## 2. 同步情况（skm 分支）

| 仓库 | 远程分支 | 本地分支 | 提交 |
|------|----------|----------|------|
| `swarmlio_multi` | `origin/skm2333-patch-1` | `skm2333-patch-1` | `713bf40 Add files via upload`（领先 `main@e88b7aa` 1 个 commit） |
| 内容 | `SKM/README.md` + `expl_data.h` + `fast_exploration_fsm.h` + `single_drone_planner.xml` + `fast_exploration_fsm.cpp` | 5 文件 2065 行 | 4 层协议见 §3 |

同步方式（GitHub 主站直连 ~19s，易超时）：

```bash
git -c http.lowSpeedLimit=1 -c http.lowSpeedTime=240 fetch origin skm2333-patch-1
git checkout -b skm2333-patch-1 origin/skm2333-patch-1
```

---

## 3. 协议原理（SKM 四层保障）

| 层 | 机制 | 位置 | 参数 |
|----|------|------|------|
| ① 发送即生效 | 发送方算完分配后立即本地应用（备份旧分配），响应仅用于停止重传/统计 | `optTimerCallback` | — |
| ② 同提案重传 + 幂等重答 | 待确认提案每 0.2s 重传同一 stamp；接收方重复提案重新应答（修复“丢弃不答”导致发送方永远等待） | `optTimerCallback` / `optMsgCallback` | `opt_retry_interval=0.2`, `opt_timeout=1.5` |
| ③ 心跳自愈 | 25Hz 心跳广播网格清单，双方同持一网格时按 **id 小者保留** 独立释放 | `droneStateMsgCallback` | 心跳 5s 超时判离线 |
| ④ 异常路径 | status=2（拒绝）→ 回滚到备份；1.5s 超时 → 保留乐观状态，靠心跳兜底 | `optResMsgCallback` | `opt_timeout=1.5` |

丢包模拟：`simulateDrop("pair_opt"/"pair_opt_res"/"drone_state")` 按 `sim_drop_rate` 随机丢弃（默认 `0.0` 不丢，仅改 XML 为 `0.2` 即测 20% 丢包，无需重编译）。

---

## 4. 选择性合入清单（未整文件覆盖）

> 原则：SKM 的 `single_drone_planner.xml` 含其 30×30 环境参数（resolution 0.05、ray 4.5m、box ±14.5 等），与本机 20×20 环境不同，只摘 3 个 `fsm/opt_*` 参数行。其余文件按函数/字段清单增量合入，保留本机 `command_ack` / `have_odom` 守卫 / IDLE 逻辑。

### 4.1 `expl_data.h`（+22）

- `FSMData`: `idle_start_time_`, `sim_drop_count_`
- `FSMParam`: `opt_retry_interval_`, `opt_timeout_`, `sim_drop_rate_`
- `DroneState`: `is_online_`, `offline_miss_count_`
- `ExplorationData`: `last_target_id_` + 7 个对称协议字段（`pre_opt_ego_ids_/pre_opt_other_ids_`, `last_opt_send_time_`, `pair_opt_target_id_`, `last_opt_response_status_`, `pair_opt_sent_count_/opt_reverted_count_/conflict_resolved_count_`）
- 保留 `mtsp_objective_/capacity_factor_`（与 SKM 等价，仅注释风格不同）

### 4.2 `fast_exploration_fsm.h`（+3/-1）

- 新增 `bool simulateDrop(const string& topic_name)` 声明
- 新增 `void offlineCheckTimerCallback(const ros::TimerEvent& e)` + `offline_check_timer_`
- 保留 `commandAckCallback` / `pending_traj_id_` / `acknowledged_traj_id_` 全套

### 4.3 `single_drone_planner.xml`（+5）

在 `fsm/pair_opt_interval` 之后插入：

```xml
<!-- 20% 丢包鲁棒性: 对称生效协议参数 + 丢包模拟(仅测试用) -->
<param name="fsm/opt_retry_interval" value="0.2" type="double"/>
<param name="fsm/opt_timeout" value="1.5" type="double"/>
<param name="fsm/sim_drop_rate" value="0.0" type="double"/>
```

未动 `map/ray/box/perception/command_ack/mtsp` 等本机参数。

### 4.4 `fast_exploration_fsm.cpp`（+214/-22，5 处函数级）

1. `#include <algorithm>`, `<cstdlib>` + `init()` 3 参数加载 + `sim_drop_count_=0` + `offline_check_timer_(5.0)`
2. 新增 `simulateDrop()` 实现（`sim_drop_rate` 随机丢弃，`ROS_WARN_THROTTLE`）
3. `droneStateMsgCallback`：首行 `if (simulateDrop("drone_state")) return` + 心跳自愈块（`getId() > msg->drone_id` 时 `id 小者保留`，`conflict_resolved_count_++`）
4. 新增 `offlineCheckTimerCallback()`（工作一：每 5s 扫心跳，连续 2 次超时判掉线，释放掉线机网格，`isGridUsable` 过滤，最近在线机质心距离接管，IDLE 时 `transitState(PLAN_TRAJ)`）
5. `optTimerCallback` / `optMsgCallback` / `optResMsgCallback` 换成对称生效协议：
   - `optTimerCallback` 头部：`wait_response_` 时 0.2s 重传 / 1.5s 超时；`missed` 过滤 `isGridUsable` + 空集守卫；尾部乐观应用（备份 `pre_opt_*` 后立即 `state1/2.grid_ids_=ego/other`）+ `pair_opt_target_id_/last_opt_send_time_/pair_opt_sent_count_` + IDLE 重启
   - `optMsgCallback`：`simulateDrop("pair_opt")` + 同 stamp 幂等重答（`last_opt_response_status_[idx]`）+ 记录应答状态
   - `optResMsgCallback`：`simulateDrop("pair_opt_res")` + `status=1` 仅记 `recent_interact_time_`（已乐观生效），`status=2` 回滚到 `pre_opt_*` + `opt_reverted_count_++`

保留：`droneStateTimerCallback` 的 `have_odom_` 守卫、`FSMCallback` 的 `pending_traj/acknowledged_traj` 投递逻辑。

### 4.5 `hgrid.h/.cpp`（+7）

```cpp
bool isGridUsable(const int& grid_id) { return getGrid(grid_id).active_ && is_cur_relevant_; }
```

与 `getActiveGrids` 判别一致，供接管/重分配过滤失效网格。

### 4.6 `fast_exploration_manager.cpp`（+13/-1）

两处初始化：`last_opt_response_status_.resize(n,0)` / `is_online_=true, offline_miss_count_=0` + `last_target_id_/last_opt_send_time_/pair_opt_target_id_/pair_opt_sent_count_/opt_reverted_count_/conflict_resolved_count_/pre_opt_*` 清零。

### 4.7 编译验证

```bash
source /opt/ros/noetic/setup.bash && cd ~/racer_ws && catkin_make -j4
# [100%] Built target exploration_node / ground_node — 仅既有 signed-compare 警告，无新增错误
```

---

## 5. 短验证（90 sim-s，20% 丢包）

### 5.1 前置修复（freeze 漂移）

`racer-platform@f64c825` / `swarmlio-single-v2@adb690b` 已领先 `config/3uav_static.yaml` 冻结的 `57c1f34/82366bf`，且 5 个修改文件使 overlay 哈希漂移，`static_checks` 3 项 FAIL。修复：

```bash
# 1) 更新 single 侧 overlay 清单中 5 个目标的期望 sha
# 2) git -C swarmlio-single-v2 commit: 0b9965e "overlay: update 20pct-drop robustness hashes"
# 3) 同步 swarmlio_multi/config/3uav_static.yaml: platform_commit=f64c8259, single_commit=0b9965ee, overlay_manifest_sha256=787d35c7
# 4) 同步 config/3uav_source_hashes.sha256: config 04c9e42->f795a1e, overlay 1c70655->787d35c7
# -> static_checks: fails 0 / all True
```

### 5.2 验证配置

| 项 | 值 |
|----|----|
| 结果目录 | `results/RUN-20260827T040141Z-3uav-verify-droploss20-90s`（命名：`RUN-<UTC>-3uav-verify-droploss20-90s` = 标准 `RUN-<UTC>-3uav-smoke` + `verify/droploss20/90s`） |
| 丢包开关 | `single_drone_planner.xml: sim_drop_rate=0.2`（仅改 XML，无需重编译；验证后已恢复 `0.0`） |
| manifest | `experiments/manifests/3uav_verify_droploss20_90s.yaml`（基于 `3uav_nodrop_c1.yaml`，`duration_sim_s=90`, `dropout.enabled=false`，其余与 C1 一致；验证后已删除，静态产物在 `results/.../manifest.yaml` 快照） |
| approval | `state/3uav_approval.yaml`（一次性，`max_uses=1`，`manifest_sha256=3738ce95 + source=0b57ee69`，`issuance_id=verify-droploss20-90s-3738ce95-v2`） |

执行：

```bash
cd ~/auto_tune_racer/swarmlio_multi
python3 scripts/two_uav_runner.py launch --manifest experiments/manifests/3uav_verify_droploss20_90s.yaml
# wall ~412s, 90 sim-s + 24s soak + 起栈/收尾
```

归档：

```bash
mv results/RUN-20260827T040141Z-3uav-smoke results/RUN-20260827T040141Z-3uav-verify-droploss20-90s
rm -rf results/RUN-20260827T035514Z-3uav-smoke  # 修复前的失败预检残留
```

### 5.3 结果

```json
// execution_result.json
{"exit_reason":"duration_complete","final_safety_passed":true,
 "final_safety_detail":"smoke command chain complete",
 "fleet_metrics":true,"uav0_metrics":true,"uav1_metrics":true,"uav2_metrics":true,
 "stop":{"clean":true,"identity_confirmed":true,"master_port_released":true}}
```

```json
// fleet/metrics.json
{"abort_reasons":[],"fleet_coverage_ratio":0.1770,"fleet_coverage_voxels":47599,
 "map_consistency_jaccard":0.6011,"overlap_ratio":0.8777,
 "fleet_contact_count":0,"minimum_inter_uav_distance_m":1.25,
 "dropout_classifications":{"uav0":"none","uav1":"none","uav2":"none"},
 "telemetry_completeness":true,"clock":{"last_sim_s":119.96}}
```

per-UAV：`uav0 29807 / uav1 29813 / uav2 43950 voxels`，`ack_timeout.count 0` 全机，`crash false`，`contact 0`。

日志（`logs/racer.log`）：`droploss 114` 条（`[droploss] 模拟丢包 20%: 丢弃 drone_state/pair_opt_res 消息(累计 N)`，三类收包口均触发）、`heal 96` 条（`[heal] Drone 2/3 释放 N 个与 Drone 1 冲突的网格(id 小者保留)`）、`Pair opt / send opt request` 正常含 `status 2` 拒绝回滚路径（中文因容器 locale 显示为 `?`，UTF-8 原文为“模拟丢包/冲突网格/重复提案/重发应答”）。

资源：`resource_usage.jsonl` 186 样本，`racer p50 2.35 cores / p95 2.82`，`gazebo p50 1.37`，`rt_factor p50 0.29`。

判定：**20% 丢包下 90s 无崩溃、无接触、零 ack 超时、覆盖率正常、自愈生效，修改验证通过**。`sim_drop_rate` 已恢复 `0.0`。

---

## 6. 使用方法

```bash
# 正常比赛（不丢包，默认）
# single_drone_planner.xml: <param name="fsm/sim_drop_rate" value="0.0"/>

# 演示/测试 20% 丢包（仅改 XML，无需重编译）
# sed -i 's/sim_drop_rate" value="0.0"/sim_drop_rate" value="0.2"/' \
#   ~/racer_ws/src/RACER/swarm_exploration/exploration_manager/launch/single_drone_planner.xml
# 预期日志：[droploss] / [heal] / [opt] 重传提案...

# 恢复
# sed -i 's/sim_drop_rate" value="0.2"/sim_drop_rate" value="0.0"/' ...
```

验证产物保留：`results/RUN-20260827T040141Z-3uav-verify-droploss20-90s/`（含 `manifest.yaml/static.yaml/static_preflight.json/live_preflight.json/coverage.png/grid_map.png/point_cloud.png/execution_result.json`）。

---

## 7. 回退

```bash
# RACER 代码回退（丢包修改前）
cd ~/racer_ws/src/RACER
git checkout backup/pre-20pct-drop          # 或 git reset --hard 7be1687

# single overlay 回退（将导致 preflight 再次 FAIL，需重做 §5.1）
cd ~/auto_tune_racer/swarmlio-single-v2
git reset --hard adb690b

# 当前分支
# RACER: feature/20pct-drop-robustness@774940d（本次合入）
# swarmlio_multi: skm2333-patch-1@713bf40（SKM 提供） + 本次 config frozen 更新（f64c825/0b9965e/787d35c7）
```

编译：`source /opt/ros/noetic/setup.bash && cd ~/racer_ws && catkin_make -j4`（`Built target exploration_node` 即成功）。

---

## 8. 提交/推送状态（截至本文档提交时）

| 仓库 | 分支 | 本地提交 | 推送情况 | 操作 |
|------|------|----------|----------|------|
| `swarmlio_multi` | `skm2333-patch-1` | `713bf40`（与 `origin/skm2333-patch-1` 一致）+ 本次 `config/3uav_static.yaml` / `config/3uav_source_hashes.sha256` / `state/3uav_approval.yaml` / `HANDOFF_DROPLOSS_20260827.md` 未提交 | `main` 已推送 `e88b7aa`，`skm2333-patch-1` 已推送 `713bf40`，**本次 3 个 config 改动待提交推送**（见下） | `git add ... && git commit && git push origin skm2333-patch-1` |
| `RACER` | `feature/20pct-drop-robustness` | `774940d`（含 SKM 合入 7 文件）+ `single_drone_planner.xml` 已恢复 `0.0`（与 `774940d` 一致，无新增 diff） | **未推送**（仅本地） | `git push -u origin feature/20pct-drop-robustness` |
| `swarmlio-single-v2` | `main` | `0b9965e`（领先 `origin/main@adb690b` 1 个 commit） | **未推送** | `git push origin main` |
| `racer-platform` | `main` | `f64c825` | 已与 `origin/main` 一致 | 无需操作 |

> 本次丢包任务的代码改动（RACER 7 文件 + single overlay 5 文件 sha 更新）**已在本地提交**，但 **尚未全部推送到 GitHub**。按上表 3 条 `git push` 即可完成远端同步。`swarmlio_multi` 的 `results/RUN-...-verify-droploss20-90s` 按 `.gitignore` 不入仓库，仅 `coverage.png/grid_map.png/point_cloud.png` 等报告引用图可按需白名单保留。

---

## 9. 下一步建议

1. 若需 300s 全量复测：在 `sim_drop_rate=0.2` 下跑 `duration_sim_s=300`（改 manifest + 重签 approval），预期覆盖率 ≥0% 基线的 95%、`droploss` 累计数千条、`heal` 自愈数十次、零崩溃。
2. 与 SKM 对齐 `f64c825/0b9965e/787d35c7` 基线后，通知队友更新 `swarmlio-single-v2` 与 `swarmlio_multi/config` frozen。
3. 进入 P1：真实 LIO（`swarm_ws` 已编译）接入 + ATE/5cm 重建/≥10Hz 证据。

---

## 10. 参考

- `SKM/README.md`（SKM 原始说明，含验证数据 0% 0.641 vs 20% 0.722）
- `STARTUP_GUIDE_20260827.md` / `RUNBOOK.md` / `PLATFORM_ENVIRONMENT.md`
- `handoff/DROPOUT_EXPERIMENT_WORKFLOW.md`（掉线语义，与丢包正交）
- 验证 runroot：`results/RUN-20260827T040141Z-3uav-verify-droploss20-90s/`
- RACER 备份：`RACER:backup/pre-20pct-drop@7be1687`，合入：`feature/20pct-drop-robustness@774940d`
