# 2-UAV diagnostic preflight execution result

- Runroot: `RUN-20260821T172635Z-2uav-preflight`
- Command: `python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml`
- Exit code: `2`
- Decision: **`PREFLIGHT_FAILED_FINAL_SAFETY_ONLY`** —— 48 项检查 **47 通过、1 失败**；
  唯一失败为 `final.safety`（uav0 occupancy 通道在最终 metrics 快照时停更 >5 s → fleet
  `telemetry_completeness=false`）。readiness/live/24 s soak/final metrics 全部通过，
  无 abort。
- Smoke trigger: not issued（本 package 只批准 diagnostic preflight）
- Active lifecycle after exit: absent —— **teardown 证据完整落盘**
  （`stop_result.json`：top_level 5 + descendants 18、`term` 23、`kill []`、
  `survivors []`、`identity_confirmed=true`、`master_port_released=true`、`clean=true`）；
  无残留进程、无 ACTIVE 文件。
- 本 runroot 为最终 append-only 产物；一次性 approval package 已消费（receipt
  `29fedcce…json` 落盘）

## Frozen identity（全部核对通过）

- Multi repo HEAD: `694a9c30aa9ee8f8f04b4f165866ded55a82aa0c` / `main`（dirty tree 由
  source hash manifest 冻结；未 commit）
- Platform repo: `57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`（tracked-clean）
- Single repo: `c01f1f5af40ec25631aa11765a0f21e06834abc4`（tracked-clean）
- Experiment manifest: `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`
- Static contract: `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`
- Source hash manifest: `a96af28ea6d8c9b032ee5b840c48f309a592e5c85de4bc1874b9eae147c1a49b`
  （12/12 OK）
- Runner: `67b6a343ea841bbfa54e23d72b6643aa22dde62c8bf47a243f83617ab760d6a2`
- `two_uav_preflight.py`: `35969b9698fcd802b87c6370ebe9c8e14e50154f2439a3093916e26e67dcd345`
- `two_uav_gt_mapper.py`: `7ea6243d1518fc5e1a30f7b33c35378b645871fb201768e0a15f5c57f6d169ae`
- `two_uav_collector.py`: `2343f0b9024878ea9a5c58d6e4cb941cd99b3950fd3a4184be355361d134aeb4`
- 公共 baseline manifest: `ce595cafba088955b38c4c9bd1d08f9af254dbfa0bf013481372a75e17980944`
- PX4 iris model template: `e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225`
- One-time approval package:
  `29fedcceda8b1d622c65909785e7dd86dc9e6b97756e679d61253942a298a799`
  （consumed；`stage: preflight`、`allowed_actions: [preflight]`、`max_uses: 1`、
  `issuance_id: preflight-20260822-post-reboot-retry-1`；启动前无 receipt、无 ACTIVE、
  环境探针 OK、负载 0.62/0.78/0.48）

## 执行结果（47/48 通过）

**通过项**：`static_preflight.json` 53/53；workspace probe 3/3；readiness 门全部通过
（双机 payload、bridges 节点、frontier）；live 检查全部通过（含唯一 TF、参数回读
16×2、logdir 隔离）；**24 s watchdog soak 通过**（"watchdog evidence complete"）；
`final.metrics` available。

**失败项**：`final.safety -> fleet safety metrics failed`。

## 唯一失败分析（供 lead 判定）

- `fleet/metrics.json`：`abort_reasons=[]`、`telemetry_completeness=false`；
  uav0 `telemetry_complete=false`、`telemetry_stale_channels=['occupancy']`；uav1
  `telemetry_complete=true`。
- **occupancy 通道自然速率 ~6.5 wall s/条**（uav0 occupancy 22→23 间隔约 2 sim s ≈
  6.5 wall s，RT≈0.358）——逼近 5 s wall freshness 阈值。
- **全 run 7 行周期 telemetry 均 `complete: true`**（occupancy 计数 8→23 持续增长、
  stale 恒空）；**仅在停栈时 collector 最终 metrics 快照**（shutdown 时刻，最后一条
  occupancy >5 s 前）标记 stale → 最终 safety 失败。
- 无 abort、无 crash、8/8 进程存活、TF 唯一父 `world`、contact 0、coverage available
  （uav0 2564 / uav1 2725 voxels）。
- 归类：本类问题第四次出现（run 5 frontier → smoke trajectory → 本轮 occupancy）——
  低速率/事件驱动通道 vs 5 s 连续 freshness 合同的边界。occupancy 在无 goal preflight
  下按 frozen contract 属连续通道；其自然速率逼近阈值使**最终快照**时机敏感。是否调整
  合同/发布行为由 Sol/lead 判定（执行器不修改任何代码/参数）。

## wall/sim 与 teardown

- wall/sim：sim `13.26 → 25.27`（12.01 sim s）/ wall 33.5 s，**RT ≈ 0.358**（负载正常）。
- teardown 证据（`stop_result.json`）：`top_level` 5、`descendants` 18、`term` 23、
  `kill []`、`survivors []`、`identity_confirmed=true`、`master_port_released=true`、
  `clean=true`——descendant-closure teardown 完整生效并落盘。

## Artifact hashes

- `manifest.yaml`:
  `75aececfaaa99137ddc1862dd28dbd4b99cb02336580a9b606d3ba391eb81d46`
- `2uav_static.yaml`:
  `415c9961cae6eb999ed18330ee84bac4881150aef5c76b44798090512a9d465e`
- `2uav_approval.yaml`:
  `29fedcceda8b1d622c65909785e7dd86dc9e6b97756e679d61253942a298a799`
- `runtime_environment.json`:
  `b2eba3e7b19e35990703e754758301260c3e883edcc3ce520a2a97ecbf982b34`
- `workspace_environment_probe.json`:
  `0407d96611464f335ab30dc8127be7d39ea0e065ca6e55b475d3eff1e89a4577`
- `process_specs.json`:
  `bef86cb921f9cf0cbfd621f5d06bfba46453f0bb9847d04563b635357339c36e`
- `static_preflight.json`:
  `ad1e4b937e1df7d966186ccae2d262e9c04861723c339aafc0bfff319f534091`
- `live_preflight.json`:
  `8df63151df3df060a94f60e55c5aa5df3e1e62d0dfaa5e6686d4012a341ecc19`
- `stop_result.json`:
  `f26e9fccbd4f20de9ca2da9229ded214a21e82d2e529d1a5f71da522faa620c4`
- `uav0/metrics.json`:
  `4a74d263b7c043f47f2d65afff012f73797264feada38f326a80b4f6d121adcd`
- `uav1/metrics.json`:
  `fbe1c382148ca13f3a053bc2a7cd6df2abe3eae9518d7e71f53cb8b0441777d7`
- `fleet/metrics.json`:
  `a3844e629644b5eaa3ff5d30577c0bdeac5d5d82e4750e92bc2283e96d62e980`
- `fleet/telemetry.jsonl`:
  `b9f6e2cdbdb51ad6013751cec6e41e9a70eb05c5abbf3dc4ddc4cd98499f483b`
- `uav0/telemetry.jsonl`:
  `aa44f086aadb4b8d2123e6d8669d4c1b3510e5b34c3b1b518bd7de53cd94f5bb`
- `uav1/telemetry.jsonl`:
  `b24235e95c5abf9a6ffe9db675b2abcb8579f0ea33683a2ce23d645de339a1d9`

## Next gate

47/48 通过、唯一失败为最终快照的 occupancy freshness 边界（合同判定归 lead）。package
已消费，runroot 为最终产物。按交接指令交回 lead-planning 审核；不得执行 smoke、不得
同包重试、不得修改任何代码/参数。
