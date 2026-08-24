# 多机环境搭建指南（一步到位版）

> 面向队友。假设你已经在**共同环境配置**下（已有 Ubuntu 20.04 + ROS Noetic +
> Gazebo Classic 11 + PX4 可用），下面所有操作都**不需要重装系统依赖**，
> 直接 clone + checkout 当前 commit + 增量构建即可。
>
> 环境版本的唯一身份是 Git commit。任何实验都必须记录三个仓库的精确 commit，
> 不要用 branch / latest 名称作为身份。

---

## 1. 快速开始（推荐：一步到位）

三条命令把三个仓库拿到手并锁定到当前版本：

```bash
# ① 公共环境仓库
git clone https://github.com/HousLakers/racer-platform.git
cd racer-platform && git checkout 4121e58

# ② 单机 overlay 仓库（多机配置的冻结输入）
git clone https://github.com/HousLakers/swarmlio-single.git
cd swarmlio-single && git checkout 82366bf

# ③ 多机仓库（任务、实验、报告）
git clone https://github.com/HousLakers/swarmlio-multi.git
cd swarmlio_multi && git checkout c0eed5e
```

> Git 的每个 commit 都是**完整快照**：`checkout` 任意一个 commit 就拿到该版本的
> 全部文件，**不需要先 checkout 更早的版本**。这里直接锁定当前版本即可。

---

## 2. 环境准备（在 racer-platform 内，共同环境上增量构建）

```bash
cd ~/auto_tune_racer/racer-platform   # 或你的实际路径

# ① 只读兼容性检查：确认你的 PX4/Gazebo 基础环境可复用（不会改动任何东西）
PX4_ROOT=/path/to/your/PX4-Autopilot \
  ./scripts/verify_infrastructure_compatibility.sh --check-patches

# ② 只导入 LE8E 必需源码（RACER / Swarm-LIO2 / FAST_LIO / Livox 仿真 + SDK）
RACER_PLATFORM_ALLOW_DOWNLOAD=yes \
  ./scripts/import_sources.sh --apply --profile le8e --with-submodules

# ③ 增量构建 Swarm 与 RACER 组件（复用已编译产物，不重装系统依赖）
./scripts/build_workspace.sh --apply --component swarm
./scripts/build_workspace.sh --apply --component racer

# ④ 只读验证环境一致性（输出应无 FAIL）
./scripts/verify_platform.sh
```

说明：

- 所有脚本**默认只检查**；只有 `--apply` + 对应 `RACER_PLATFORM_ALLOW_*`
  环境变量才会真正执行。不会动你已有的 PX4/Gazebo。
- 如果你不是已有环境、而是空白机器，则先补一步系统依赖安装，再执行上面的 ②③④：

  ```bash
  RACER_PLATFORM_ALLOW_INSTALL=yes ./scripts/install_native.sh --apply --with-python
  ```

- 任何一步不满足一致性检查时**停止并人工修复**，不要跳过。

---

## 3. 校验 C1 配置引用的输入

```bash
# 确认 multi 仓库冻结的三个输入与当前 checkout 一致
cd ~/auto_tune_racer/swarmlio_multi

# ① 单机 overlay commit 必须等于 82366bf
grep single_commit config/3uav_static.yaml        # 期望 82366bf26e26cd0dddea3ee57e8591d3a2a42c7f

# ② 50x50 world 的 sha256 必须匹配
sha256sum ../racer-platform/environment/worlds/2uav_outdoor_50x50_v1.world
# 期望 28a306b646297011b564c5ce94ac97634281a5e9a34e337956c5f4a9227c320e

# ③ racer-platform 的 50x50 baseline 存在
ls ../racer-platform/environment/baselines/racer_outdoor_50x50_v1.yaml
```

---

## 4. 三个仓库当前 commit 一览

| 仓库 | GitHub | 作用 | 当前版本 commit |
|---|---|---|---|
| **racer-platform** | `HousLakers/racer-platform` | 公共环境：依赖/源码导入/构建脚本/50x50 环境基线 + world | `4121e58` |
| **swarmlio-single** | `HousLakers/swarmlio-single` | 单机感知 overlay（多机冻结输入） | `82366bf` |
| **swarmlio_multi** | `HousLakers/swarmlio-multi` | 多机任务、实验、报告 | `c0eed5e` |

三个仓库 GitHub `origin/main` 均已与上表一致，直接 `git clone` 后按第 1 节
checkout 即可，无需额外同步。

---

## 5. 背景：仓库演进（仅用于理解，不需要执行）

> 本节只是解释"这些 commit 是怎么来的"，**不是**搭建步骤。搭建请按第 1–3 节。

### 5.1 三个仓库的相对演进

```text
racer-platform  57df512 ──► ... ──► 57c1f34 ──► 4121e58   (基座 → LE8E 验证 → 新增 50x50 C1 环境)
                                                              │ 依赖
swarmlio-single 41879e8 ──► ... ──► 82366bf                  (共享根 → 20m omnidirectional → load-balancing v1)
                                                              │ 冻结输入
swarmlio_multi  (与 single 共享根 41879e8) ──► ... ──► c0eed5e (dropout → 负载均衡矩阵 → C1 快照)
```

### 5.2 关键节点说明

- `57df512`（racer-platform 根）：公共环境审计基线。
- `57c1f34`（racer-platform）：LE8E 运行冒烟验证通过，是 C1 实验实际冻结的
  运行环境 commit。
- `4121e58`（racer-platform 当前）：在基座上**仅新增** 50x50 baseline + world
  （`git diff 57c1f34 4121e58` 只改 2 个文件），脚本与基座完全一致。
- `41879e8`：`swarmlio-single` 与 `swarmlio_multi` 的共享根 commit
  （`Initialize multi-UAV workspace and platform sync`），两仓库从同一份
  初始历史分叉，分别走向单机 overlay 治理与多机实验。
- `82366bf`（swarmlio-single 当前）：load-balancing v1 overlay（MINMAX +
  capacity factor），是多机 `3uav_static.yaml` 的冻结输入。
- `c0eed5e`（swarmlio_multi 当前）：C1 快照 + 本指南。

### 5.3 为什么不需要"从基座一步步走到当前"

Git 的 commit 是完整快照而非补丁。`git checkout 4121e58` 拿到的就是该版本
的完整文件树（含全部脚本），然后执行第 2 节的增量构建即可得到可运行环境。
"基座 → 当前"描述的是**历史演进**，不是**搭建路径**。队友唯一需要的版本
就是第 4 节表格里的三个 commit。

---

## 6. 常见核对点

1. 三个仓库 checkout 与第 4 节表格一致，不要用 branch 名代替 commit。
2. `verify_platform.sh` 输出无 FAIL；patch/commit/dirty 状态与 lock 一致。
3. `sha256sum` 校验 50x50 world 与 baseline 中记录的 hash 一致（第 3 节）。
4. 实验开始前在 multi 仓库记录三个仓库 commit（`git rev-parse HEAD`），
   实验记录与 runroot 保持一致。
5. 如果 `verify_infrastructure_compatibility.sh --check-patches` 报不兼容，
   **不要**直接 `--apply` 覆盖，先与仓库所有者确认环境差异。
