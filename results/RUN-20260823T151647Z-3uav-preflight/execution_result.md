# Execution result: RUN-20260823T151647Z-3uav-preflight（3-UAV diagnostic preflight — PASS）

- 命令：`python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/3uav_smoke.yaml`
- exit_code：0
- 结论：**preflight PASS**（static 57/57 + live 全通过 + 资源门按合约新值通过）

## 不可变身份

- manifest：`experiments/manifests/3uav_smoke.yaml`，SHA-256 `2232cb58445e7bd765e9747443dd3296532fd10a8f3afd0ae1e8fad6262ef26b`
- source hash manifest：`config/3uav_source_hashes.sha256`，SHA-256 `b5b0f2d4d331af1de31e1cbade5cce38f0a7e2b580afd939b9d08b460ff9259f`（逐文件校验全过）
- approval package：`state/3uav_approval.yaml`，SHA-256 `de2db38c7318bd4ebdca89475976f811baaddfb217baa7a96e82e6f8d3a9061e`
- issuance_id：`3uav-preflight-20260823-3`（已消费，receipt 见 results/approval-consumption/）
- 合约变更：`resource_running_mem_available_gib: 3 → 1`；PX4 恢复默认 daemon 模式（interactive 回退）

## 检查结果

| 阶段 | 结果 |
|---|---|
| static_preflight（57 项） | ✅ **全通过** |
| live_preflight | ✅ **全通过**（required_topics、clock 单 publisher、use_sim_time、TF 三边、uav0/1/2 payload 各 5 通道、logdir/readback、watchdog_soak、final.metrics、final.safety） |
| 资源门 startup | ✅ MemAvailable 12.58 GiB ≥ 8 GiB、load1 1.02、swap 0 增长 |
| 资源门 ready | ✅ **MemAvailable 2.73 GiB ≥ 1 GiB（合约新值）**、load1 5.92、swap_out delta 794 页（门限内） |
| 运行期内存 | ✅ min 2.41 GiB ≥ 1 GiB（49 样本） |
| teardown | ✅ clean、survivors=[ ]、kill=[ ]、identity_confirmed=true |

## Fleet 运行核验（预检短程，sim≈24.9 s）

- 11 进程全存活：exploration/px4_bridge/traj_server ×3 + collector + gt_mapper；topic owners 覆盖 3 机全部关键通道
- abort_reasons=[]、contact=0、min inter-UAV dist=1.416 m、telemetry_completeness=true、clock monotonic
- dropout_classifications 全部 none（preflight 不触发掉线）

## 已知偏差（不阻断）

- RT factor：有效样本 23 个，p50=0.00（栈启动窗口期 sim 时钟未起步）、p95=1.97；
  预检为短程，RT 为尽力指标，按指令不阻断。3-UAV 满载 gazebo RSS 仍约 7.5 GB，运行期
  可用内存 min 2.41 GiB，余量紧张但符合合约新值。

## 对后续流程的影响（供 sol 决策）

- package `3uav-preflight-20260823-3` 已消费；3-UAV preflight 通过。
- 下一步：高终端签发 3UAV dropout-smoke approval → 低终端执行 D9 三机掉线 smoke。
- 建议（非阻断）：正式 3-UAV smoke 运行时留意内存余量（min 2.41 GiB），若出现 swap
  持续增长触发 abort 策略，需在 D9 前再评估；本机 15 GB 内存对 3-UAV 满栈偏紧。
