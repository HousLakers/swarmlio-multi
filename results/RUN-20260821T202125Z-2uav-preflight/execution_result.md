# 2-UAV diagnostic preflight execution result

- Runroot: `RUN-20260821T202125Z-2uav-preflight`
- Command: `python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml`
- Exit code: `2`
- Decision: **`PREFLIGHT_FAILED_RESOURCE_GATE_SWAP`** —— 新资源门（compute-overlay
  修改引入）在运行中检测到 **swap-in 活动** → fail-closed 拒绝
  （`running resource gate failed: swap activity observed`）。静态 **55/55** 与 workspace
  probe 通过；失败属资源/基础设施类（内存不足换页），非代码回归。
- Smoke trigger: not issued（本 package 只批准 preflight）
- Active lifecycle after exit: absent —— 无残留进程、无 ACTIVE 文件、端口释放
  （`stop_result.json` 未落盘：失败于 start_stack running-gate 阶段、ACTIVE 未写入，
  与既往 start_stack 失败路径一致）。
- 本 runroot 为最终 append-only 产物；一次性 approval package 已消费（receipt
  `be77efb9…json` 落盘）

## Frozen identity（全部核对通过）

- Multi repo HEAD: `694a9c30aa9ee8f8f04b4f165866ded55a82aa0c` / `main`（dirty tree 由
  source hash manifest 冻结；未 commit）
- Platform repo: `57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`（tracked-clean）
- Single repo: `c01f1f5af40ec25631aa11765a0f21e06834abc4`（tracked-clean）
- Experiment manifest: `5cc07755cb46cfb13fda34fa96b9e528766340541c8eb919f62f7a000381e3c5`
- Static contract: `a0fb9077b67d48cf30ed233a886954966e57df331c73c3f8f2ffa6958b44faed`
- Source hash manifest: `b275c3e06238b9e7a00653bd3b2439e893b47d947b7f085c64fa3974fb25c99a`
  （12/12+3 OK）
- `two_uav_runner.py`（资源门）:
  `4ee36556e0cf5ddefa9bed7cf753e5ca00cd13512c69d6600e18e101fe03b8f1`
- `two_uav_preflight.py`: `0739418767fa19bc35ecd302d7feb5c8feebe9c2578f1ad733b28cf3ae840ccd`
- `two_uav_collector.py`: `1685dcd64a442423fd3c00d4c1062e84e2fa667f01e2aee1009e195a7ad36eca`
- `two_uav_gt_mapper.py`: `c90383cb1083b554e50355405353d5a5e3ed3ce9a586a2d30962f8fc40a5c4e9`
- `px4_bridge.py`: `b673080c46916790431f257aea1a27fa8616adeb6b409fe22968e0316b57f34f`
- 公共 baseline manifest: `ce595cafba088955b38c4c9bd1d08f9af254dbfa0bf013481372a75e17980944`
- PX4 iris model template: `e8ae6d24c7d85124326db2f795aa72286772da3520110419919a897527d73225`
- One-time approval package:
  `be77efb9fe8689b30a54ed83183e3dda30e3e2ad923aac534389288f16eb0d26`
  （consumed；`stage: preflight`、`allowed_actions: [preflight]`、`max_uses: 1`、
  `issuance_id: preflight-20260822-compute-overlay-010m-1`；启动前无 receipt、
  无 ACTIVE、环境探针 OK、启动负载 2.29/1.10/0.87）

## 执行过程（至资源门失败）

1. `static_preflight.json`: **passed: true**，**55/55**（新静态检查生效）；workspace
   probe 3/3。
2. `resource_capacity_startup.json`: **ok: true**（load1=2.01、MemAvailable=13.63 GB、
   swap_in=29491、swap_out=221525）——启动资源门通过。
3. 栈启动（gazebo/gt_mapper/bridges/racer/collector 进程拉起），`resource_usage.jsonl`
   开始采样。
4. **running 资源门失败**：`resource_capacity_ready.json` **ok: false** —— 运行中
   load1=3.49、MemAvailable 降至 **6.88 GB**（13.63→6.88）、**swap_in 29491→29619
   （+128）** → "swap activity observed" → fail-closed 拒绝。
5. 停栈：无残留进程、无 ACTIVE 文件。

## 失败分析（供 lead 归因）

- **根因上下文**：双机全栈内存占用 ~12 GB（上轮 resource profile：racer RSS 7.2 GB +
   gazebo 5.2 GB，MemTotal 16.17 GB）——运行中 MemAvailable 跌破 ~7 GB 并出现
   swap-in → 新资源门按设计 fail-closed 拦截（防止内存不足条件下继续运行导致
   mavros/odom/occupancy 类二次失败）。
- 直接回应此前算力/内存问题：**16 GB 内存不足以舒适运行双机全栈**（栈 ~12 GB + 系统
  与其他进程）；资源门现在是显式的第一道防线。
- 属基础设施/资源类失败，非代码回归；fail-closed 行为正确。

## Artifact hashes

- `manifest.yaml`:
  `5cc07755cb46cfb13fda34fa96b9e528766340541c8eb919f62f7a000381e3c5`
- `2uav_static.yaml`:
  `a0fb9077b67d48cf30ed233a886954966e57df331c73c3f8f2ffa6958b44faed`
- `2uav_approval.yaml`:
  `be77efb9fe8689b30a54ed83183e3dda30e3e2ad923aac534389288f16eb0d26`
- `runtime_environment.json`:
  `d58fb14ff315f0e7c6da417573a7f0340a3412e09480662d1d623b4bc07667dd`
- `workspace_environment_probe.json`:
  `0407d96611464f335ab30dc8127be7d39ea0e065ca6e55b475d3eff1e89a4577`
- `process_specs.json`:
  `1061f9b794dd6468e87e8a9966bbc8f3209b046bc4cc4582884d2b741a673dae`
- `static_preflight.json`:
  `e511e364b2b718117f9e4538376b053567200ea338b240f51daa3a7091fc09ab`
- `live_preflight.json`:
  `0d2f13953f4475055b251770760fb421c4a6f6d632398e0a9f783c288bdfb663`
- `resource_capacity_startup.json`:
  `31bf5bdd46caa5a8f68b7633af37471af4236a8eea41538382632641cc55367d`
- `resource_capacity_ready.json`:
  `e93b9064d43e469f150fbeec5a6426dd40d8e08e6d4de0ad64c02f43e7b896a5`
- `resource_usage.jsonl`:
  `f5511d8a9247c3191970a6aa4e5f71b87c974fbabe3bc05adb37986736fc1909`

## Next gate

资源门失败（内存/swap），package 已消费，runroot 为最终产物。按交接指令交回
lead-planning 审核；不得执行 smoke、不得同包重试、不得修改任何代码/参数。
