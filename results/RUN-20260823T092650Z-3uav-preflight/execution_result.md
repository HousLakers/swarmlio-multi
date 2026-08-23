# Execution result: RUN-20260823T092650Z-3uav-preflight（3-UAV diagnostic preflight — FAIL）

- 命令：`python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/3uav_smoke.yaml`
- exit_code：2
- 结论：**preflight FAIL（live 阶段资源门不通过）**；静态检查全通过，失败为环境性（内存不足），
  非 hash/namespace/参数/代码问题。

## 不可变身份

- manifest：`experiments/manifests/3uav_smoke.yaml`，SHA-256 `2232cb58445e7bd765e9747443dd3296532fd10a8f3afd0ae1e8fad6262ef26b`
- source hash manifest：`config/3uav_source_hashes.sha256`，SHA-256 `494aafa41bc825b700d5d04e023b3ab4609c6d96693b494c9d8f9e4835dc05e4`（逐文件校验全过）
- approval package：`state/3uav_approval.yaml`，SHA-256 `ee8a97ea9ec67f60fb1f2cc8ce3ac6a8cfc0126926ed1ef593eba79ad9911fbc`
- issuance_id：`3uav-preflight-20260823-2`（**已消费**，receipt 见 results/approval-consumption/）
- runner：`scripts/two_uav_runner.py` SHA-256 `735a266b979870b757bbd771a3c09ca23a7b031259bdfb1f542540f2cf5e8f70`

## 检查结果

| 阶段 | 结果 |
|---|---|
| static_preflight（55 项） | ✅ **全通过**（3-UAV contract/uav_count=3、命名空间与 topic 隔离、端口隔离、launch XML well-formed、wiring uav0/1/2、参数回读、source hash 全匹配） |
| 资源门 startup | ✅ MemAvailable 11.5 GiB ≥ 8 GiB、load1 2.25、swap 0/0 |
| **资源门 ready/running** | ❌ **MemAvailable 1.72 GiB < 3 GiB；swap_out=2939** |
| live_preflight 检查 | ❌ final.metrics timeout、final.safety timeout、preflight.runtime fail |

## 失败根因（环境性：主机内存容量不足）

- 本机总内存 15 GB，3-UAV 栈满载 RSS ≈ 10.4 GB：
  gazebo 7.55 GB（3 机 world）+ racer 2.58 GB + bridges 0.18 GB + gt_mapper 0.14 GB；
- 叠加系统与编辑器等开销后，运行期 MemAvailable 仅 1.72 GB，触发 running ≥ 3 GiB 硬门；
- 随之出现 swap 活动（swap_out 2939 页），collector 进程被饿死（0 CPU ticks、空日志），
  final.metrics / final.safety 超时；
- 对照：2-UAV 栈满载 ≈ 7 GB，运行期 MemAvailable ≈ 4.6–4.8 GiB，可稳过 3 GiB 门；
  3-UAV 增量约 +3.5 GB 即越过阈值。

## 已排除的失败因素

- 代码/runner：approval_guard 正确绑定新 hash，allowlist 修复生效（D8 修复验证）；
- 静态合同：3-UAV manifest、static.yaml、launch 文件、wiring 全部静态核验通过；
- 非参数漂移：source hash manifest 494aafa4 与 package 一致，逐文件校验全过。

## 对后续流程的影响（供 sol 决策）

- package `3uav-preflight-20260823-2` 已消费，**不可复用**（approval_already_consumed 硬门）；
- 在本机内存不变的前提下，3-UAV preflight 无法通过 running ≥ 3 GiB 门——重复执行会重复失败
  并继续消耗一次性 package；
- 可选出路（高终端裁决，均需相应源码/环境变更后由中终端更新 source hash、sol 重签 package）：
  1. 增加物理内存/交换策略调优后重跑；
  2. 降低 3-UAV 栈内存占用（如 Gazebo world 简化、传感器降频、降分辨率）；
  3. 调整 running 门限（不推荐——门限是 3-UAV 实验的既有合同约束）。
