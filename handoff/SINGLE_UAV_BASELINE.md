# 单机到多机交接摘要

生成依据：

- 单机 `project_state.md`，记录最终 `3×8×600 s` 三臂证据矩阵及 LE8-E 节点基线决策；
- `New_report/单机复现与AI交接手册.md`；
- `New_report/FINAL_SINGLE_UAV_REPORT_MATERIALS_20260812/`。

## 1. 交接结论

单机结果可以作为多机中每架无人机的节点级能力基线，但不能外推为 fleet-level coverage、任务时间、完成率、负载均衡、地图一致性、通信鲁棒性或机间安全结论。

可迁移到每架 UAV 的能力包括：

- 低速触发和 planner-native recovery；
- reachable-target / A* 可达性筛选；
- 轨迹安全检查和 live collision checker 语义；
- failed-target memory、repeat-frontier 和 gain-aware 排序上下文；
- action bridge、gate、telemetry 和 health state；
- 每架 UAV 独立的完成、冻结、crash、contact 和 coverage 记录。

多机必须重新测量：

- hgrid/静态或动态分区；
- 异步共享地图与地图一致性；
- 重复覆盖率；
- 任务负载均衡；
- 机间最小距离和接触；
- 通信延迟、丢包和算力竞争；
- 一架 UAV 失败时其余 UAV 是否继续。

## 2. 推荐节点级参考

交接手册和最终报告共同确认 LE8-E 作为每机参考配置：固定室内地图、GT 同步注册、600 s 规划实验。
LE8-E 在最终三臂×8×600 s矩阵中为推荐节点基线；独立扩展仍出现晚期冻结和浅接触风险。因此它是有边界的节点基线，不是无条件安全保证。

最终证据矩阵包含三个对照臂，但这不改变多机采用 LE8-E：

- `le8i_safe_unknown_tolerant`：安全对照；
- `le8g_high_coverage_reference`：性能对照；
- `le8e_reliability_reference`：最终采用的节点级参考。

三臂矩阵是单机最终证据，不能外推为多机 fleet 结论；每个结论仍须绑定 runroot、gate JSON 和最终汇总文件。

## 3. 必须保留的运行语义

- 规划比较使用 GT 同步注册；不能将 GT 规划结果与 Swarm-LIO 感知结果混入同一统计矩阵。
- `inflation=0.35` 是 LE8-E 参考值；不能因多机首轮失败直接改成 0.50。
- progress guard、global trajectory guard 默认关闭，`reject_unknown=false`；这些是 LE8-E 节点基线的固定运行合同。
- `reject_unknown=true` 禁止作为默认安全修复；RACER 探索未知空间时会造成 rejection/failure-memory 自激。
- L（low-speed）是已验证的直接动作入口；F（planner-fail）和 W（wander/repeat-low-gain）主要作为上下文和排序约束。
- 终点可达不等于执行一定产生进展；必须保留实际 A* 路径和执行 telemetry。
- 物理 Gazebo contact 必须与 planner 的 predictive collision/replan 分开计数。

## 4. 交接前置门

新多机项目必须先完成：

1. 迁移前后源码、XML、参数和运行脚本 manifest；
2. GT、topic、namespace、TF、接触、地图、前沿、轨迹和评分链路 smoke；
3. 2-UAV preflight；
4. 每架 UAV 独立 telemetry 和健康状态；
5. 2-UAV 短 smoke，再决定是否进入正式时长；
6. 未经批准不得开展新参数搜索、LIO/GT 混合比较或多机性能外推。

公共环境合同：`racer-platform` commit `57c1f34`（LE8E 宿主机运行冒烟已验证）。
多机源码和脚本只能在确认该平台版本后继续接入。

## 5. 关键单机资产

- 全项目时间线：单机项目的 `project_state.md`；
- 复现和迁移规则：`New_report/单机复现与AI交接手册.md`；
- 单机报告材料：`New_report/FINAL_SINGLE_UAV_REPORT_MATERIALS_20260812/`；
- 最终采用基线脚本：`run_e2l_le8e_primary_8x600.sh`；
- 终局三臂证据脚本：`run_e2l_le8i_overnight_randomized_3arm_8x600.sh`；
- runtime gate：`e2l_runtime_param_gate.py`；
- 机制验证：`verify_e2l_le8f_patch.py`、`verify_e2l_le8g_patch.py`、`verify_e2l_le8h_patch.py`。

## 6. 新对话首读文件

新 Codex 对话先读取：

1. `AGENTS.md`；
2. `handoff/SINGLE_UAV_BASELINE.md`；
3. `state/current_summary.md`；
4. 最新任务包和 runroot。

除非发生争议或需要追溯，不要默认读取单机完整 `project_state.md`。

## 7. 当前 20 m 全向节点候选

LE8-E 仍是历史节点参考；当前进入多机的节点候选是在同一公共平台上应用
`platform_overlays/range20m_omnidirectional_v1` 后的 20 m 水平全向配置。单机 v8
smoke 全门 PASS；功能长测达到 97.56% coverage 后由用户早停，正式结论为
`FUNCTIONAL_VALIDATION_PASS / FORMAL_ENDURANCE_INCOMPLETE`。它只允许作为节点候选，
不构成 fleet 结论。

多机接入以 `handoff/SINGLE_TO_MULTI_TRANSFER_20260820.md` 为正式入口。必须同时固定：

- `racer-platform@57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`；
- `swarmlio-single@c01f1f5af40ec25631aa11765a0f21e06834abc4`；
- overlay manifest SHA-256
  `80d0d06a5a9b3722804c28d3efc6ace9a71d5955b26f8124e12bf3579e0d9529`；
- installer SHA-256
  `7e2280d5d0ba88ee501764ab5b5ccc3f3724d5b6abf39704badc7a8976349151`。

不得把 2-UAV manifest 的节点候选改回裸 LE8-E 后仍声称在验证本次视野/视角调整。
