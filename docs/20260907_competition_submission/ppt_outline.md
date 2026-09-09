# 答辩 PPT 框架（建议 16:9、16 页）

定位：比赛答辩/系统路演，不是把论文逐页缩小。每页只讲一个判断，标题使用“结论式
action title”，图表优先，正文只保留 3–5 个短句。数字全部来自
[evidence_matrix.md](evidence_matrix.md)。

## 叙事骨架（ghost deck test）

1. GNSS 拒止和通信不稳定要求无人机具备感知、探索和自愈闭环。
2. 我们把国产嵌入式平台上的 LIO、探索、任务分配和 PX4 执行连成了可审计系统。
3. 20 m 全向激光底座支撑了单机定位与多机任务分配。
4. MINMAX+0.75 让三机负载更均衡，掉线和 20% 丢包仍能继续探索。
5. 单机实机链路已经有节点级 baseline；双机目标数据丢失暴露出启动、坐标和证据链缺陷。
6. 下一步先用 fail-closed preflight 补齐双机，再安全扩展三机。

## 逐页结构

| 页 | Action title | 主要展品 | 页面内容与讲述要点 | 数据/证据 |
|---:|---|---|---|---|
| 1 | **在 GNSS 拒止环境中，让无人机自己看、自己分工、自己恢复** | 标题 + 三机轮廓/实验室照片（若无照片用系统图） | 题号 XH-202629、队伍、日期；一句话目标：国产算力上的具身智能感知与决策 | 赛题 PDF；不放未经核实的“全国产”徽标 |
| 2 | **赛题的三个技术门槛决定了我们的系统分层** | 三列：感知定位 / 协同探索 / 弹性决策 | 左：无 GNSS/无先验图；中：任务分配/地图共享；右：掉线/丢包/动态变化 | `XH-202629...pdf` 第 2–5 页 |
| 3 | **我们把传感器到飞控的链路做成了可追踪的数据流** | [双机 Archify 图](../../topic_flow_dual_real.html) | 讲共同 ROS Master、逐机 `_1/_2` 命名、LIO→RACER→bridge→MAVROS/PX4；强调共享触发不等于共享控制 | Archify deliver 9/9；浏览器 visual-check skipped，页脚注明“结构图” |
| 4 | **20 m 全向激光把单机底座从局部感知提升为协同输入** | 旧/新感知对比 + LIO/地图小图 | 4–5 m 深度相机→20 m 水平 360° 雷达；统一点云、odom、frontier 输入 | `REPORT_阶段成果整合汇报_20260825.md` §1 |
| 5 | **单机仿真先证明了定位与探索链可运行** | 轨迹/coverage/ATE 三联图 | 60.20 simulated s；coverage 72.94%；ATE 0.0802 m；P10 clearance 1.898 m；安全事件 0 | `handoff/SINGLE_TO_MULTI_TRANSFER_20260820.md`；标“仿真” |
| 6 | **我们用 21 轮矩阵而不是一次演示选择分配策略** | 实验矩阵热图/流程 | A1–A3 无掉线、B1–B3 掉线，各 3 次；C1 再验证 3 次；目标函数×容量×故障 | `REPORT_P0_MATRIX_CLOSEOUT.md` |
| 7 | **MINMAX 用更长的总路径换来了更均衡的工作量** | A1/A2/A3 失衡比—总路径散点 + 小表 | A2 失衡比 1.43±0.20 vs A1 2.41±1.03；A2 总路径 796±88 m；解释 trade-off，不只报 coverage | `REPORT_P0_MATRIX_CLOSEOUT.md` §3 |
| 8 | **C1 三次复现把 MINMAX+0.75 冻结为当前仿真配置** | C1 三行表 + 均值/误差条 | fleet ratio 0.2258±0.0050；imbalance 1.10±0.02；Jaccard 0.7612±0.0237；abort=[] | C1 r1/r2/r3；r2 人工 stop 的限制写在图注 |
| 9 | **掉线不再等于任务中断：检测、释放、接管、继续探索** | 四步状态机 + coverage 曲线 | 5 s watchdog/连续确认；释放 grid；最近在线机唯一接管；继续规划；修复 int8→int32 截断和越界守卫 | `多机容错通信改进总结...md` §3 |
| 10 | **20% 丢包下，所有权协议靠对称生效和心跳自愈收敛** | 原协议 vs 新协议对比 + 时序 | 发送即生效；stamp 幂等重答；25 Hz heartbeat；编号小者保留；异常回滚 | 0%/20% run 32/33；任务层注入，明确限定 |
| 11 | **掉线与 20% 丢包叠加时，在线无人机仍完成 300 s 任务** | coverage 柱/任务释放接管数字 | 20% 轮：coverage 0.657 vs 0.673（97.6%）；26 格释放/21 格接管；36 次冲突自愈；无崩溃 | `experiments/多机容错通信改进总结_掉线任务重分配与20%丢包_20260822.md` |
| 12 | **Khadas 嵌入式原型已跑通单机节点链路，但 fleet 证据必须分级** | 实机照片/节点级指标卡 | UAV1 34.64 m/0.9288；UAV2 55.34 m/0.9874 + 5 cm PGM；说明这是单机 baseline，不是 fleet 成绩 | `state/real_dual_audit_20260906/figures/` |
| 13 | **18:32 双机数据丢失，因此我们选择公开失败而不是补写成功** | 时间线：18:30 c89 / 18:32 missing / fea8 invalid | `EVIDENCE_MISSING`：无 runroot/rosout/bridge/bag/ULog；18:30 WAIT_TRIGGER/Empty dominance/A* outside；历史 fea8 `INVALID_RUN` | `state/dual_diagnosis_20260907/report.md`；这是可信度页 |
| 14 | **诊断把“UAV1 路径短”拆成可验证的四个工程问题** | 根因树 | ID1 初始 grid ownership；ID2 empty grid/重分配未完成；LIO z≈0.025 与 box z_min=.5；vision remap/共享 `/keys` 流程缺陷；不把 tracker reset 直接叫 LIO reset | `state/dual_diagnosis_20260907/report.md` |
| 15 | **下一次先过不解锁 preflight，再扩展到三机** | 预检门 + 三机包结构 | cloud/odom/pose 连续性、external-vision 一对一、local_position payload、grid ownership、pair-opt ACK、hover gate；UAV3 IP/串口/型号留空直至核实 | `deploy_triple_real/README.md`；不展示可执行命令作为批准 |
| 16 | **当前贡献是可复现的仿真容错闭环，加上诚实的实机证据边界** | 三行结论 + 下一步 | 已验证：21 轮分配/掉线/20% 丢包仿真；节点级实机 baseline；待验证：双机 fleet ATE/Hz/≤2 s/≤30 W/三机硬件 | `evidence_matrix.md`；联系方式/致谢 |

## 备用附录页（不计入 16 页）

### A1 指标矩阵

直接放 [evidence_matrix.md](evidence_matrix.md) 的“赛题要求—证据—缺口”表，红色只表示
`missing/invalid`，不隐藏。

### A2 双机日志证据

展示 `WAIT_TRIGGER=180`、`trigger=0`、`Empty dominance=42`、A* outside=26 的摘录，
页脚写“18:30 c89，触发前诊断，不是 18:32 飞行结果”。

### A3 三机脚本包与 hash

展示 `BUILD_RECEIPT.json`、每机 `manifest.sha256`、UAV3 空字段和 `execution_ready:false`。

### A4 安全策略

展示 bridge 的 hover gate、RC health、manual takeover latch 和 fail-closed 状态；不要在
答辩现场把 `--execute` 命令当作演示。

## 版式与演示规则

- 16:9，白底、深蓝主色、青色数据强调、玫红只表示风险/缺证；每页最多三种颜色。
- action title 24–28 pt，正文 18–20 pt，图表标注 ≥16 pt；每页只保留一个主图。
- 结果页采用左图右结论；图注写实验层级、n、run ID 和“仿真/实机”。
- 任何实机照片旁同时放 run ID/证据状态；无法关联 runroot 的照片只能标“现场观察”。
- 先按本框架确认内容，再生成 PPTX；生成后必须检查 PDF/PNG 每页溢出、数字、图例和字体。
- 现场问答预案：被问“18:32 是否成功”时回答“证据缺失，不能判成功；我们已定位并准备
  不解锁 preflight”；被问“全国产/30 W/实时”时回答“对应条目尚未形成合格采样”。

## 3 分钟压缩版

保留第 1、2、3、5、8、9、10、12、13、15、16 页；合并第 6–8 页为一页矩阵结果，
合并第 9–11 页为一页容错结果。压缩版仍保留第 13 页的 `EVIDENCE_MISSING`，不能以
删页掩盖实机数据丢失。
