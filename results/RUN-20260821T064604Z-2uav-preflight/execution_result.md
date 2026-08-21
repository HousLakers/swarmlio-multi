# 2-UAV preflight execution result

- Runroot: `RUN-20260821T064604Z-2uav-preflight`
- Command: `python3 scripts/two_uav_runner.py preflight --manifest experiments/manifests/2uav_smoke.yaml`
- Exit code: `2`
- Decision: `PREFLIGHT_FAILED_GATE_BEFORE_STACK`（`verify_workspace_environment` 门在
  任何进程启动前拒绝；runner 脚本缺陷导致的 fail-closed 误报，非环境/运行期失败）
- Smoke trigger: not issued（本 package 只批准 preflight）
- Active lifecycle after exit: absent（无任何 ROS/Gazebo 进程启动过，无
  `/tmp/swarmlio_multi_2uav_active.json`）
- 本 runroot 为最终 append-only 产物；一次性 approval package 已消费（receipt
  `8b3b7530...json` 落盘）

## Frozen identity

- Multi repo: `41879e8ccea783895965831f75646ac2a6a43ed7`（`main`，dirty tree 由完整
  hash manifest 绑定；未 commit）
- Platform repo: `57c1f34a607b834915f9aa4a4a6b301ecc5a4ffc`（tracked-clean）
- Single repo: `c01f1f5af40ec25631aa11765a0f21e06834abc4`（tracked-clean）
- Source hash manifest: `91c91c0cdb67b5603cc95ea3cda942440ffec8cd676c3dbcd6ed646add9d0d4e`
  （12/12 OK）
- Experiment manifest: `e366f943180cb1471742ab2a84e685d75e64442fd00c8bf75e14a00ee618a0f2`
- Runner: `06f2ae31c5514cbb2efeae3be266f1d77d188a1c695380183a8d532501a308de`
- Public baseline manifest: `48d00fca6032c76f59ca26134ff39dba2d555a552c2d73f81e3ca51b4583dc44`
- 50x50 world: `28a306b646297011b564c5ce94ac97634281a5e9a34e337956c5f4a9227c320e`
- One-time approval package:
  `8b3b75309100f43e68808f6380bc44bbfc2cda5de2b766d9ad665eabb07a4937`（consumed）

## Pre-execution gates（启动前核对，全部通过）

- 四项 SHA-256 与 sol_approval 第 9 节一致：manifest `e366f943…`、source hash
  manifest `91c91c0c…`、runner `06f2ae31…`、approval package `8b3b7530…`。
- package 字段：`stage: preflight`、`approved: true`、`allowed_actions: [preflight]`、
  `issued_by: sol`、`max_uses: 1`；`manifest_sha256` 与 `source_hash_manifest_sha256`
  字段与实际文件匹配。
- 无 `8b3b7530…` 的消费 receipt（仅旧 `3bf111db…`、`57a76ff0…` 存在）；无 active
  lifecycle；冻结仓库 commit 未变。
- 环境探针：`netifaces.interfaces()` OK（5 接口）、localhost TCP OK、`/tmp` 可写。
- `static_preflight.json`: **passed: true**，53/53 项（在创建 runroot 后、gate 失败前由
  runner 写入）。

## Failure（runner gate 误报，进程未启动）

- runner 消费 package 后进入 `start_stack`：静态 53/53 通过 → `verify_workspace_environment`
  门失败 → 立即抛 `RuntimeError("workspace environment probe failed: swarm_lio,
  exploration_manager, quadrotor_msgs")` → 无任何 Popen 启动、无 process_specs.json、
  无进程日志、无 stop_result.json、无 telemetry/metrics（RUNBOOK 允许：基础设施门失败
  无逐机 metrics 属预期，不得补造）。
- `workspace_environment_probe.json`：三项 probe 全部 `ok: false`：
  - `swarm_lio` / `exploration_manager`：`[rospack] Error: package not found`；
  - `quadrotor_msgs`：`ModuleNotFoundError`。
- `runtime_environment.json` 记录的组合环境本身正确：
  `ROS_PACKAGE_PATH=/home/houslakers/swarm_ws/src:/home/houslakers/racer_ws/src:/opt/ros/noetic/share`、
  `PYTHONPATH` 含双 workspace devel dist-packages。

## Root cause（runner 脚本缺陷，已复现）

`verify_workspace_environment`（runner 第 326-346 行）的 probe 子进程命令为
`bash -lc "source /opt/ros/noetic/setup.bash; <probe>"`，env 已带组合环境；但
**`source /opt/ros/noetic/setup.bash` 会把 `ROS_PACKAGE_PATH` 与 `PYTHONPATH` 重置为仅
noetic 的值**（实测：source 前含双 workspace，source 后只剩
`/opt/ros/noetic/share` / `/opt/ros/noetic/lib/python3/dist-packages`），probe 因此
全部失败。而 `process_specs`（第 222-225 行）在 source noetic **之后**调用
`workspace_environment_exports(runroot)` 重新导出组合路径，长期进程环境是正确的。

复现证据（与 probe 相同命令/相同环境值）：

```text
source /opt/ros/noetic/setup.bash 前后:
  ROS_PACKAGE_PATH: <swarm>:<racer>:<noetic>  →  /opt/ros/noetic/share
  PYTHONPATH:       <swarm dp>:<racer dp>:<noetic dp>  →  /opt/ros/noetic/.../dist-packages
probe 直接失败; 但 source noetic 后重新导出组合路径:
  rospack find swarm_lio           → /home/houslakers/swarm_ws/src/Swarm-LIO2/swarm_lio  OK
  rospack find exploration_manager → /home/houslakers/racer_ws/src/RACER/... OK
  python3 -c 'import quadrotor_msgs.msg' → OK
```

结论：环境 baseline 与包解析本身合格（swarm_lio/exploration_manager/quadrotor_msgs
均真实存在且可解析）；失败源于 runner `verify_workspace_environment` 的 probe 环境
构造与 `process_specs` 不一致（source 顺序/未重导出），属脚本缺陷，需 terra 最小修复。

## Artifact hashes

- `manifest.yaml`:
  `e366f943180cb1471742ab2a84e685d75e64442fd00c8bf75e14a00ee618a0f2`
- `2uav_static.yaml`:
  `fa3be02954ea86280c19c8b41c1ca194e7d565351857051e9c0f8536e0d7e8d6`
- `2uav_approval.yaml`:
  `8b3b75309100f43e68808f6380bc44bbfc2cda5de2b766d9ad665eabb07a4937`
- `runtime_environment.json`:
  `9c778c6e4f8a6faf451a947ed2b99ccc1d2710c06b593a2cd2a3c6d8a5d5910d`
- `workspace_environment_probe.json`:
  `eb47596d3f3e1844eb4a89bf7e6423f4cbceab5670e1a1246b19f33c514b0c67`
- `static_preflight.json`:
  `46426af7352766c4426c53aa9f657d7a72bfe4d0f9b54b47e9dffceced4d7072`
- `live_preflight.json`:
  `6c2761bd6c59849e728f6dc8e7272d326e545f33fa0040c6f5e818219ef87de4`

## Next gate

package 已消费，runroot 为最终产物。按 sol_approval 第 9 节：不得复用 package、不得
launch/smoke、不得修改源码/参数/正式状态。runner gate 缺陷已移交 Sol/terra 复审
（`state/execution_issue.md`）；修复后需 Sol 重新签发一次性 preflight package。
