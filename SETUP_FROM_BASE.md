# 从公共环境基座到当前多机配置：搭建与版本对应指南

> 生成日期：2026-08-24 · 面向队友的 checkout/搭建指引。
> 环境版本的唯一身份是 `racer-platform` 的 Git commit，任何实验都必须记录
> 三个仓库的精确 commit，不要用 branch/latest 名称作为身份。

---

## 1. 三个仓库与当前 commit 对应

| 仓库 | GitHub | 本地路径 | 作用 | 当前版本 commit |
|---|---|---|---|---|
| **racer-platform** | `HousLakers/racer-platform` | `~/auto_tune_racer/racer-platform` | 公共环境：docker/依赖/repos/patch/环境基线/world | `4121e58` |
| **swarmlio-single** | `HousLakers/swarmlio-single` | `~/auto_tune_racer/swarmlio-single-v2` | 单机感知 overlay（多机冻结输入） | `82366bf`（本地）／`08fb545`（GitHub origin/main）⚠️ |
| **swarmlio_multi** | `HousLakers/swarmlio-multi` | `~/auto_tune_racer/swarmlio_multi` | 多机任务、实验、报告（本仓库） | `61d2624` |

⚠️ **注意**：多机配置 `config/3uav_static.yaml` 冻结的 `single_commit` 是
`82366bf`（load-balancing v1 overlay），但 `swarmlio-single` 的 GitHub
`origin/main` 目前只到 `08fb545`。队友需要先 `git pull`/`git fetch origin`
拿到 `82366bf`，或由仓库所有者将 `82366bf` push 到 GitHub 后再 checkout。

---

## 2. 基座（最初版）与当前版的差异

**基座** = 最初上传的公共环境（docker/依赖/源码导入/验证脚本/patches），
即 `racer-platform` 的 `57c1f34`（`Record successful LE8E runtime smoke test`）。

**当前版** = 基座 + C1 所需的 50x50 室外环境基线，即 `racer-platform` 的
`4121e58`，在基座上新增：

- `environment/baselines/racer_outdoor_50x50_v1.yaml`
- `environment/worlds/2uav_outdoor_50x50_v1.world`

三个仓库的相对演进（按依赖顺序）：

```text
racer-platform  57c1f34 ──────────────► 4121e58   (公共环境基座 + 50x50 C1 环境)
                                                     │
swarmlio-single 08fb545 ───────────────► 82366bf   (冻结输入：20m omnidirectional overlay v2 + load-balancing v1)
                                                     │
swarmlio_multi  (多机工作区) ──────────► 61d2624   (本仓库：C1 快照，含 MINMAX+0.75 配置)
```

---

## 3. 搭建步骤（队友从基座到当前）

### 3.0 前置

- Ubuntu 20.04 LTS (focal)，x86_64
- 已有或可构建 ROS Noetic + Gazebo Classic 11 + PX4（复用已有基础环境时
  使用 `le8e` profile，避免覆盖队友已有 PX4/Gazebo）
- 磁盘/内存按 `racer-platform` 的 `RUN_LE8E.md` 要求

### 3.1 克隆并锁定三个仓库

```bash
# 1) 公共环境仓库 —— checkout 当前版
git clone https://github.com/HousLakers/racer-platform.git
cd racer-platform
git checkout 4121e58

# 2) 单机 overlay 仓库 —— checkout 当前多机冻结输入
git clone https://github.com/HousLakers/swarmlio-single.git
cd swarmlio-single
git fetch origin
git checkout 82366bf          # 若 GitHub 尚未有该 commit，用本地 push 或从所有者同步

# 3) 多机仓库 —— checkout 当前 C1 快照
git clone https://github.com/HousLakers/swarmlio-multi.git
cd swarmlio_multi
git checkout 61d2624
```

### 3.2 环境准备（公共环境仓库内执行）

复用已有 PX4/Gazebo 基础环境（推荐队友路径）：

```bash
cd ~/auto_tune_racer/racer-platform

# 只读兼容性检查（不会改动任何已有环境）
PX4_ROOT=/path/to/PX4-Autopilot \
  ./scripts/verify_infrastructure_compatibility.sh --check-patches

# 只导入 LE8E 必需源码（RACER / Swarm-LIO2 / FAST_LIO / Livox 仿真 + SDK）
RACER_PLATFORM_ALLOW_DOWNLOAD=yes \
  ./scripts/import_sources.sh --apply --profile le8e --with-submodules

# 构建 Swarm 与 RACER 组件
./scripts/build_workspace.sh --apply --component swarm
./scripts/build_workspace.sh --apply --component racer

# 只读验证环境一致性
./scripts/verify_platform.sh
```

从零环境搭建（完整路径）：

```bash
RACER_PLATFORM_ALLOW_INSTALL=yes ./scripts/install_native.sh --apply --with-python
RACER_PLATFORM_ALLOW_DOWNLOAD=yes ./scripts/import_sources.sh --apply --with-submodules
./scripts/build_workspace.sh --apply --component swarm
./scripts/build_workspace.sh --apply --component racer
./scripts/verify_platform.sh
```

> 所有脚本默认只检查；`--apply` + 对应 `RACER_PLATFORM_ALLOW_*` 环境变量
> 才会真正执行安装/导入/构建。任何一步不满足一致性检查时停止并人工修复。

### 3.3 校验当前 C1 配置引用的输入

在 `swarmlio_multi` 中确认 `config/3uav_static.yaml`：

```yaml
frozen:
  platform_commit: 57c1f34a...      # ← 见下方说明
  single_commit: 82366bf...          # 必须与 swarmlio-single 当前 HEAD 一致
  overlay_manifest: platform_overlays/range20m_omnidirectional_load_balancing_v1/current_config.sha256
```

> `platform_commit` 记录的是 LE8E 冻结基座 `57c1f34`（C1 实验实际使用的
> 运行环境）；公共环境仓库的当前版 `4121e58` 是它的向后兼容扩展（新增
> 50x50 baseline/world，未改动基座内容）。验证 baseline 文件：
>
> ```bash
> sha256sum racer-platform/environment/worlds/2uav_outdoor_50x50_v1.world
> # 期望 28a306b646297011b564c5ce94ac97634281a5e9a34e337956c5f4a9227c320e
> ```

### 3.4 多机实验入口

```bash
cd ~/auto_tune_racer/swarmlio_multi
# 状态机断点续跑 / 矩阵执行见 README.md、RUNBOOK.md 与 experiments/PLAN_* 文档
```

---

## 4. 三个仓库 commit 清单（2026-08-24）

### racer-platform（GitHub origin/main = 本地 main）

```text
4121e58 feat: publish the C1 50x50 outdoor environment baseline
57c1f34 Record successful LE8E runtime smoke test
c7cd501 Document LE8E reconstruction and runtime workflow
185a6b0 Initialize submodules for selected source profile
```

### swarmlio-single（GitHub origin/main = `08fb545`；本地多机冻结输入 = `82366bf`）

```text
82366bf overlay: add load-balancing v1 (MINMAX objective + capacity factor)   ← 本地/多机冻结
08fb545 Fix uav2 freeze root cause: keep vehicle body region free in shared map (overlay v2, 22 files)  ← origin/main
8c8ddf2 Finalize compute overlay identity
aea4b71 Finalize RUN-20260821T175600Z: freeze bridge readiness identity
c01f1f5 Document racer-platform to single onboarding
7c0da5b Finalize reproducible 20m omnidirectional overlay
658c9fa Finalize RUN-20260819T143725Z: functional validation
2fed30e Finalize 20m omnidirectional v8 smoke gate
...（更早记录见仓库历史）
```

### swarmlio_multi（GitHub origin/main = 本地 main = `61d2624`）

```text
61d2624 clean: publish C1 snapshot — prune runroot data, keep report figures + docs + C1 config
fcb1ff9 docs: regenerate P0 closeout report HTML — 21/21 done + C1 3/3 + runner fix
5766e9d docs: finalize P0 closeout report — C1 3/3 done + runner fix record
ca4db69 stage: LB-matrix closeout — 21/21 done (incl. C1 validation) + runner monitor fix
e63c6fd stage: LB-matrix closeout — 18 runs (17 done / 1 failed) + plot fix + records (high)
f31a3c2 fix: make per-vehicle coverage growth curves visible in lower panel
...（更早记录见仓库历史）
```

---

## 5. 常见核对点

1. 三个仓库的 checkout 必须与第 3.1 节一致；`swarmlio_multi` 只引用
   `racer-platform` 的 commit，不复制环境锁。
2. `sha256sum` 校验 50x50 world 与 baseline 中记录的 hash 一致。
3. `verify_platform.sh` 输出无 FAIL；patch/commit/dirty 状态与 lock 一致。
4. 若 `swarmlio-single` GitHub 缺少 `82366bf`，联系仓库所有者 push 该 commit
   或要求同步，否则 multi 配置冻结输入不匹配。
