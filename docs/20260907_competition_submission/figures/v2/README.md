# 论文 v2 图件

六幅图均提供 SVG、PDF、PNG。论文引用SVG；PDF为矢量排版资产，PNG用于预览。数据重算只读取既有索引与精确路径，不运行实验、不写原始证据。

| 图 | 文件前缀 | 类型与来源 | 范围 |
|---|---|---|---|
| 1 | fig01_system_flow | 旧fig1_system_architecture.svg分层语义与根目录单/双机Archify结构；本轮JSON、HTML及静态论文视图 | 系统设计，无数据曲线 |
| 2 | fig02_dropout_packetloss_states | 旧fig3_fault_tolerance.svg主题；按已读任务协议修正超时与拒绝处理 | 状态机制；不表示时延或概率 |
| 3 | fig03_minmax_minsum | 从矩阵精确run的metrics重算；fig03_matrix_data.csv | A/B各n=3；C1补充n=2；均值±样本SD与真实单次点 |
| 4 | fig04_packetloss_report | 第32/33轮历史报告；fig04_report_data.json | 0%/20%任务层丢包均叠加75 s掉线；n=1/条件；无误差线 |
| 5 | fig05_single_real_maps | R1/R3原trajectory.csv、PGM及metadata | 单节点实机各n=1、各自坐标系；没有猜测world变换 |
| 6 | fig06_three_real_placeholder | 无数据，仅五字段空图位 | 不含假轨迹、地图或统计值 |

旧fig2_allocation_statistics.svg的统计表达作为参考，但因C1时长口径问题不沿用旧数值图；保留原文件。本轮统计由 [论文派生脚本](../../draft/build_paper_v2_artifacts.py)生成。脚本和输入hash位于论文目录，不修改旧绘图源码或runroot。

Archify最终交付见 [fig01_delivery_final_receipt.json](fig01_delivery_final_receipt.json)：showcase 9/9，0 errors，0 warnings，spec与HTML都有SHA256。`fig01_delivery_receipt.json`是初次沙箱失败的历史回执，不能当成最终结果。静态论文SVG是根据同一JSON节点与数据关系生成的打印视图，不冒充浏览器导出。

浏览器检查 [visual-check](fig01_system_flow.visual-check.json) 为SKIPPED：环境缺少Chrome/Chromium。HTML的人工浏览器视觉审核仍pending；本轮已逐一查看六张静态PNG，检查文字、轴标、n、误差线、空图位和图例。静态PNG审核不替代HTML浏览器检查。
