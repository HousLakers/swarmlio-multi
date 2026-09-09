# Citation plan v1

## 已有候选文献（必须核验）

| 键 | 主题 | 当前来源 | 核验动作 |
|---|---|---|---|
| `swarm-lio2-tro25` | 分布式高效 LiDAR–惯性里程计 | `state/khadas_cleanup_20260904/evidence/archives/swarm_lio2.tar` | 用 `verify-citations` 核对作者、题名、卷期、页码、DOI |
| `swarm-lio-icra23` | 前序 Swarm-LIO | 同上 README/论文归档 | 用 `verify-citations` 核对会议、页码、DOI |

## 待补文献模块

### A. LIO 与多机协同定位

- 综述/代表性 LIO：`[CITATION_TODO]`
- 分布式/多机 LiDAR–inertial：`[CITATION_TODO]`
- 外部视觉、时间同步和坐标对齐：`[CITATION_TODO]`

### B. Frontier exploration

- frontier 定义与信息增益：`[CITATION_TODO]`
- 多机 frontier 分配与重复覆盖：`[CITATION_TODO]`
- kinodynamic/B-Spline exploration planning：`[CITATION_TODO]`

### C. 多机器人任务分配

- MINSUM/MINMAX 或多旅行商建模：`[CITATION_TODO]`
- 容量约束和在线重分配：`[CITATION_TODO]`
- 多机地图一致性：`[CITATION_TODO]`

### D. 通信与弹性决策

- 心跳、任务所有权和分布式一致性：`[CITATION_TODO]`
- 丢包、节点掉线和任务接管：`[CITATION_TODO]`
- 无人机集群故障恢复：`[CITATION_TODO]`

### E. 国产边缘平台与实时部署

- 机载计算/功耗评估：`[CITATION_TODO]`
- 国产算力适配和自主可控：`[CITATION_TODO]`

## 引用使用规则

- 项目报告只支持项目自身结果，不代替外部研究现状文献。
- 代码仓库只支持实现细节，不代替算法原始论文。
- 摘要不放引用；相关工作每个外部论断至少绑定一个可检索原文。
- 找不到 DOI 或正式出处时保留占位符，不根据模型记忆补齐。
