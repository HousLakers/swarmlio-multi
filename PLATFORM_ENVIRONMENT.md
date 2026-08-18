# Swarm-Multi 环境同步合同

多机项目统一使用公共环境仓库：

```text
https://github.com/HousLakers/racer-platform.git
```

当前多机同步基线：

```text
platform_commit: 57c1f34
platform_role: LE8E host-runtime-smoke-verified baseline
```

不要用 `latest`、未提交的本地目录或浮动 branch 作为实验环境身份。环境升级时，先在 `racer-platform` 形成新 commit，再更新本文件中的 commit。

## 队友安装/同步

```bash
cd /home/houslakers/auto_tune_racer
git clone https://github.com/HousLakers/racer-platform.git
cd racer-platform
git checkout 57c1f34
```

如果队友已经有 PX4/Gazebo，使用 LE8E 专用源码 profile，不覆盖基础环境：

```bash
export RACER_PLATFORM_SOURCE_ROOT="$PWD/sources"
export RACER_PLATFORM_WORK_ROOT="$PWD/workspace"

PX4_ROOT=/path/to/PX4-Autopilot \
  ./scripts/verify_infrastructure_compatibility.sh --check-patches

RACER_PLATFORM_ALLOW_DOWNLOAD=yes \
  ./scripts/import_sources.sh --apply --profile le8e --with-submodules

RACER_PLATFORM_ALLOW_PATCH_APPLY=yes \
  ./scripts/apply_le8e_patches.sh --apply --skip-px4
```

`--profile le8e` 会同步 RACER、Swarm-LIO2、FAST_LIO、Livox SDK、Livox 仿真和 link-attacher；不会下载或覆盖队友已有的 PX4/Gazebo。

## 编译

```bash
./scripts/build_workspace.sh --apply --component swarm
./scripts/build_workspace.sh --apply --component racer
```

构建前提包括 ROS Noetic、Gazebo Classic、MAVROS、LKH、NLopt 和队友已有的 PX4 SITL 工具链。Docker 可提供 CPU-only ROS/编译依赖，但不会自动包含 PX4、地图、控制桥接和实验总控。

## 多机运行前的 ROS 环境

多机 workspace 应引用同一 platform commit，并使用明确的 ROS overlay：

```bash
source /opt/ros/noetic/setup.bash
export ROS_PACKAGE_PATH="$RACER_PLATFORM_WORK_ROOT/racer_ws/src:$RACER_PLATFORM_WORK_ROOT/swarm_ws/src:/opt/ros/noetic/share"
export CMAKE_PREFIX_PATH="$RACER_PLATFORM_WORK_ROOT/racer_ws/devel:$RACER_PLATFORM_WORK_ROOT/swarm_ws/devel:/opt/ros/noetic"
rospack profile
```

确认：

```bash
rospack find swarm_lio
rospack find exploration_manager
```

## 多机实验合同

环境完成后，回到本仓库执行准备阶段：

```bash
cd /home/houslakers/auto_tune_racer/swarmlio_multi
```

必须先完成：

1. `handoff/SINGLE_UAV_BASELINE.md` 与当前 platform commit 一致；
2. `experiments/manifests/2uav_smoke.yaml` 填入经过批准的 2-UAV 启动入口；
3. 每架 UAV 使用独立 namespace、初始位姿、日志和结果目录；
4. 通过 2-UAV preflight、topic/TF/telemetry smoke；
5. 由 sol 写入 `state/sol_approval.md` 后，DeepSeek 才能执行实验。

当前仓库仍是多机编排骨架，`racer-platform` 只负责公共环境同步，不替代多机 launch、DeepSeek runner 或实验状态合同。
