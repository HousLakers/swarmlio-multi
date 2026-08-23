# 单机掉线实验：Route A 可执行任务清单

状态：`APPROVED_V1 / sol 已于 2026-08-23 批准`
参考：`handoff/DROPOUT_EXPERIMENT_WORKFLOW.md`（语义）、`state/luna_review.md`
（RUN-20260822T173640Z-2uav-smoke 已通过：RT p50=0.41 未达标，uav1 freeze=晚期规划停滞）。
终端：高=lead-planning，中=low-level-implementation，低=experiment-execution/result-reporting。
路线：A = 先 runner 级 fault injection → 2-UAV rehearsal 验证语义 → 再扩 3-UAV 正式掉线 smoke。
交接：所有阶段交接遵循 `handoff/TERMINAL_HANDOFF_PROTOCOL.md`（即时交接 + 刷新文档）。
提交：每个阶段完成后必须 commit + push origin main，格式 `stage: <阶段ID> <终端>: <一句话>`；
只提交该阶段交付物，不提交原始日志/点云/build/整个 results。

## 任务总览

| 任务 | 阶段 | 终端 | 状态 |
|---|---|---|---|
| D0 | 语义冻结 | 高 | ✅ 本清单批准时完成 |
| D1 | runner dropout 事件 | 中 | ⬜ |
| D2 | collector dropout 分类 v1 | 中 | ⬜ |
| D3 | 2-UAV 掉线 rehearsal | 低 | ⬜ |
| D4 | collector 分类强化 + 报告字段 | 中 | ⬜ |
| D5 | 三机参数化（runner/preflight/collector） | 中 | ⬜ |
| D6 | 3-UAV config/launch/manifest 新建 | 中 | ⬜ |
| D7 | 3-UAV static 校验 + self-test | 中 | ⬜ |
| D8 | 3-UAV diagnostic preflight | 低 | ⬜ |
| D9 | 3-UAV 掉线 smoke（control_chain） | 低 | ⬜ |
| D10 | 3-UAV 掉线 smoke（node_level 最终验证） | 低 | ⬜ |
| D11 | 报告与收尾 | 低→高 | ⬜ |

---

## D0：冻结掉线语义（高终端，本文件批准时完成）

- 输入：`handoff/DROPOUT_EXPERIMENT_WORKFLOW.md` v1
- 动作：批准 0.1 术语隔离、0.2 三种模式、0.3 默认对象/时机、0.4 成功/失败标准
- 产出：本文件 + 工作流文件被 sol 标注 `APPROVED`
- 成功标准：无未决语义，成功标准可被 runner 断言
- 交接：→ 中终端 D1
- **sol 签批记录（2026-08-23）**：本清单已由 sol 批准为 `APPROVED_V1`；
  `DROPOUT_EXPERIMENT_WORKFLOW.md` 已冻结为 `FROZEN_V1`；D1 任务包同步签发。

## D1：runner dropout 事件（中终端）

- 输入：`sol_plan.md` 掉线任务包；manifest `2uav_smoke.yaml` 需加 `dropout:` 段
- 动作：
  1. `two_uav_runner.py` 增加 `dropout` 配置解析（enabled/vehicle/mode/trigger_sim_s）
  2. `action_launch` 的 `monitor_until` 循环中，当 sim 到达 `trigger_sim_s` 且未触发过，
     执行白名单 fault injection（kill 目标进程集合，按 mode 区分）
  3. 触发时写入 `fleet/dropout.json`（vehicle/mode/sim_s/wall_s/pids）
  4. dropped UAV 的残余进程加入 `stop_active` 的回收名单（不成为 survivors）
  5. self-test 覆盖：触发时机、mode 进程集合、重复触发禁止、dropout 后 abort 路径
- 产出：`two_uav_runner.py` diff、self-test 通过输出、`state/terra_implementation.md`
- 禁止：临时 shell kill；修改安全门阈值
- 交接：→ 高终端审核；审核通过 → D2

## D2：collector dropout 分类 v1（中终端）

- 输入：D1 后的 runner；`two_uav_collector.py`
- 动作：
  1. collector 读 `fleet/dropout.json`（同 runroot）
  2. 对 dropped UAV 标记 `dropout=true`、`dropout_mode`、`dropout_sim_s`
  3. 该机 metrics 中 `crash/freeze/contact` 判定在掉线后跳过（避免误判）
  4. telemetry 记录中标注 dropout 断点
- 产出：`two_uav_collector.py` diff、self-test
- 交接：→ 高终端审核 → D3

## D3：2-UAV 掉线 rehearsal（低终端）

- 输入：D1/D2 通过；高终端签发 `dropout-rehearsal` approval package（一次性）
- manifest：`2uav_smoke.yaml` 增加 `dropout: {enabled: true, vehicle: uav1, mode: control_chain,
  trigger_sim_s: 60}`
- 动作：只执行白名单 `launch`，等待 duration 结束，保存 runroot
- 产出：runroot `RUN-*-2uav-dropout-rehearsal`、`execution_result.md`
- 成功标准（对照工作流 0.4）：
  1. `fleet/dropout.json` 存在且完整
  2. uav0 掉线后不 abort、无 crash/contact，coverage 继续增长
  3. uav1 标记 `intentional_dropout` 而非 crash
  4. teardown clean，无 survivors
  5. 资源门前后保持
- 交接：→ 低终端 result-reporting 写 luna → 高终端审核
- 若失败：回到高终端判定（分类 bug → D4；注入 bug → D1；语义问题 → D0）

## D4：collector 分类强化 + 报告字段（中终端）

- 输入：D3 结果、luna 反馈
- 动作：
  1. 强化 `intentional_dropout` vs `unexpected_loss` vs `telemetry_missing` 区分
  2. metrics 增加 `surviving_uavs_continue`、`post_dropout_coverage_delta`
  3. freeze 判定联合 pos_cmd 活跃（修复 RUN-20260822T173640Z smoke 中 uav1 晚期悬停误标）
- 产出：collector/runner diff、self-test、terra 记录
- 交接：→ 高审核 → D5

## D5：三机参数化（中终端）

- 输入：现有 `two_uav_runner.py`/`two_uav_preflight.py`/`two_uav_collector.py`
- 动作：将 `uav_count` 从脚本硬编码改为由 manifest/config 驱动
  （vehicle 循环、topic 映射、端口、日志子目录全部由 `config.vehicles` 列表推导）
- 成功标准：2-UAV manifest 行为不变（向后兼容）；self-test 覆盖 uav_count=2 和 =3
- 产出：脚本 diff、self-test 输出、terra 记录
- 交接：→ 高审核 → D6

## D6：3-UAV config/launch/manifest 新建（中终端）

- 输入：D5 参数化；`config/2uav_static.yaml`、`launch/2uav_*.launch`
- 动作：
  1. 新建 `config/3uav_static.yaml`（uav_count=3，uav2 加入：namespace /uav2、racer_id 3、
     mavlink_system_id 3、ports 14542/14582/14562/4562/5602/14532、初始位姿避开 uav0/uav1）
  2. 新建 `launch/3uav_px4_sitl.launch`、`launch/3uav_racer.launch`、`launch/3uav_bridges.launch`
     （复用 D5 参数化模板）
  3. 新建 `experiments/manifests/3uav_smoke.yaml`（uav_count=3，duration_sim_s 视资源定，
     初始建议 120；dropout 段含 uav1 默认）
  4. 更新 `config/3uav_source_hashes.sha256`（新 source-hash manifest）
  5. `worlds/` 评估是否需要 3 个出生点（不扩世界尺寸则位姿在 50×50 内放置）
- 成功标准：3-UAV 静态契约 self-test 通过；identity 链完整
- 产出：新 config/launch/manifest、hash manifest、terra 记录
- 交接：→ 高审核 → D7

## D7：3-UAV static 校验 + self-test（中终端）

- 输入：D6 产物
- 动作：运行 `three_uav_preflight --mode static`（或参数化后 preflight 的 static 模式）、
  py_compile、self-test、`git diff --check`
- 成功标准：static 全部通过、self-test 通过
- 产出：验证证据、terra 记录
- 交接：→ 高审核；合格后签发一次性 3UAV preflight package → D8

## D8：3-UAV diagnostic preflight（低终端）

- 输入：高签发 approval（一次性）；`experiments/manifests/3uav_smoke.yaml`
- 动作：只执行白名单 `preflight`
- 成功标准：static + live 通过；资源门通过（MemAvailable 启动 ≥8 GiB、运行 ≥3 GiB、
  swap 零活动、RT 尽力 ≥0.5）
- 产出：runroot `RUN-*-3uav-preflight`
- 交接：→ 高审核；通过后签发 3UAV dropoout-smoke package → D9

## D9：3-UAV 掉线 smoke（control_chain）（低终端）

- 输入：高签发 approval；manifest `dropout: {enabled: true, vehicle: uav1,
  mode: control_chain, trigger_sim_s: 60}`
- 动作：白名单 `launch`，保存 runroot
- 成功标准：工作流 0.4 全部 1-7 项（control_chain 模式）
- 产出：runroot `RUN-*-3uav-dropout-smoke-control`
- 交接：→ 低终端写 luna → 高审核
- 若通过 → D10；若失败 → 高终端判定返工

## D10：3-UAV 掉线 smoke（node_level 最终验证）（低终端）

- 输入：D9 通过；高签发 approval；manifest `dropout.mode: node_level`
- 动作：白名单 `launch`，保存 runroot
- 成功标准：工作流 0.4 全部 1-7 项（node_level 最严模式）
- 产出：runroot `RUN-*-3uav-dropout-smoke-nodep`（最终证据）
- 交接：→ 低终端写 luna → 高审核

## D11：报告与收尾（低→高）

- 低终端：按工作流第 5 节掉线模板写 `state/luna_review.md`
- 高终端：审核证据 → 一次性更新 `project_state.md`/`current_summary.md`/`SESSION_HANDOFF.md`
  → 收尾 commit `Finalize RUN-...: 3uav-dropout-smoke pass`
- 禁止：把 intentional dropout 写成 crash；外推单机/双机结论到 fleet 性能

---

## 资源预判（Route A 关键风险）

- 3-UAV 栈 RSS ≈ 9.3 GiB（Gazebo + 3×racer + bridges），MemAvailable ≈ 4.4 GiB（余量 1.4 GiB）
- RT 预计 0.25-0.30（现 2-UAV 已 0.41）；掉线注入本身开销 < 0.1 GiB
- 若 D8 preflight RT < 0.5：记录为已知偏差，不阻断掉线实验（掉线语义实验 ≠ 实时性对比）
- 若 MemAvailable 跌破 3 GiB：fail-closed，按工作流第 4 节硬门处理，不放宽

## 禁止项汇总

- 低终端不得在掉线实验中临时 kill（必须 runner 白名单事件）
- 任何终端不得复用已消费 approval package
- 掉线实验不得降低 MemAvailable/swap/RT/freshness 门限
- 掉线对象、模式、时机改变必须回高终端 D0 语义层批准
- 未获高终端批准前不得启动 D3/D8/D9/D10 任何实验
