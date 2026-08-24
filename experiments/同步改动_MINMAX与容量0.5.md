# 改动同步说明：MINMAX 目标函数 + 容量 0.5

> 用途：供同伴同步"负载均衡"两项改动。改动都在**同一个文件**里，改完重新编译即可。

## 目标文件

```
~/racer_ws/src/RACER/swarm_exploration/exploration_manager/src/fast_exploration_manager.cpp
```

函数名：`FastExplorationManager::allocateGrids`（多机任务分配，用 ACVRP/LKH 求解）。

---

## 改动 1：ACVRP 目标函数 MINSUM → MINMAX

**位置**：`allocateGrids` 里生成 `.par` 参数文件的 `else if (prob_type == 2)` 分支（ACVRP 分支），约 1461~1465 行。

**原代码**（ACVRP 分支原本没设目标，默认 MINSUM）：

```cpp
  } else if (prob_type == 2) {
    file << "TRACE_LEVEL = 1\n";  // ACVRP
    file << "SEED = 0\n";         // ACVRP
  }
```

**改为**（只加一行 `MTSP_OBJECTIVE = MINMAX`）：

```cpp
  } else if (prob_type == 2) {
    file << "MTSP_OBJECTIVE = MINMAX\n";  // 新增：均衡三机完成时间
    file << "TRACE_LEVEL = 1\n";  // ACVRP
    file << "SEED = 0\n";         // ACVRP
  }
```

---

## 改动 2：单机探索容量 0.75 → 0.5

**位置**：同一函数内，约 1395 行（`capacity` 计算处）。

**原代码**：

```cpp
  capacity = capacity * 0.75 * 0.1;
```

**改为**：

```cpp
  capacity = capacity * 0.5 * 0.1;
```

---

## 背景与原理

1. **原问题**：多机探索"总是一架干、一两架闲"（负载失衡）。
2. **根因**：ACVRP 目标默认 **MINSUM**（三机总路程最短）→ 求解器把前沿都分给"离得最近"的那架 → "富者愈富"，其余机闲置。
3. **改动 1（MINMAX）**：把目标从"总路程最短"改成"**最长那架的路程最短**"，直接均衡三机完成时间。LKH 求解器内置支持（`MTSP_OBJECTIVE = [MINSUM | MINMAX | MINMAX_SIZE]`），所以只改 `.par` 里一行参数，无需动求解器。
4. **改动 2（容量 0.5）**：容量 = 每机最多能拿的工作量上限。0.75 → 0.5 让求解器更难"一机包揽"，对 MINMAX 有轻微辅助（见下方测试数据）。

---

## 测试数据（pcd_generated.world，300 仿真秒）

三机路径长度失衡比（越大越不均衡）：

| 配置 | 轮次 | 平均失衡比 |
|------|------|-----------|
| 原（0.75 + MINSUM） | 13~16 | 2.56× |
| 0.5 + MINMAX | 18~20 | **1.57×** |
| 0.75 + MINMAX | 21~23 | 2.01× |

结论：**MINMAX 是主要杠杆**（失衡比降约 40%），容量 0.5 略优于 0.75。

---

## 重新编译

```bash
cd ~/racer_ws && catkin_make
```

编译通过后（`Built target exploration_node`），改动即生效。

---

## 附：本机还加了"心跳掉线检测"（可选同步）

如果同伴也需要"单机掉线检测"，另有一组改动（不在此文档范围）：
- `exploration_manager/include/exploration_manager/expl_data.h`：`DroneState` 加 `bool is_online_`；
- `exploration_manager/include/exploration_manager/fast_exploration_fsm.h`：加 `offlineCheckTimerCallback` 声明 + `offline_check_timer_` 成员；
- `exploration_manager/src/fast_exploration_fsm.cpp`：加 5s watchdog 定时器 + 回调；
- `exploration_manager/src/fast_exploration_manager.cpp`：初始化 `is_online_ = true`。

需要的话再单独出文档。
