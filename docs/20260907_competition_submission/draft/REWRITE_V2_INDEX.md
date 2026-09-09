# 论文重写 v2 交付索引

状态：`READY_FOR_REVIEW`；正文：`DRAFT_NOT_SUBMITTABLE`。高级终端写作任务完成，未执行新实验或提交版本。

阅读顺序：[框架v3](../paper_writing_framework_v3.md) → [正文v2](paper_draft_v2.md) → [Word排版稿](paper_draft_v2.docx) → [论断台账](claim_ledger_v2.md) → [引用计划](citation_plan_v2.md) → [QA报告](qa_report_v2.md)。

图件：[六图清单](../figures/v2/README.md)；[系统交互图](../figures/v2/fig01_system_flow.html)；[MINMAX/MINSUM](../figures/v2/fig03_minmax_minsum.svg)；[单机实机](../figures/v2/fig05_single_real_maps.svg)；[三机空位](../figures/v2/fig06_three_real_placeholder.svg)。

数据与审校：[矩阵逐run指标](audit_v2/matrix_records.json)、[统计](audit_v2/matrix_statistics.json)、[实机重算](audit_v2/real_metrics.json)、[输入hash](audit_v2/input_hashes.json)、[静态检查](audit_v2/structure_check.json)、[skills回执](audit_v2/skill_checks.json)、[润色差异](audit_v2/polish.diff)。

Word排版：由 `build_paper_docx.py` 从 v2 Markdown 生成；为兼容 Word，正文中的六个 SVG 图位在 Word 包内使用对应 PNG，原始 SVG/PDF 仍保留在 `figures/v2/`。OOXML 检查结果：6 个 `word/media` 图片、15 个表格、20 个小节标题。LibreOffice 容器渲染因 Java/桌面配置不可用而未完成，Pandoc 反向读取与压缩包结构检查通过。

生命周期：输入阅读与profile完成 → v3框架保存并报告 → v2重写/图件完成 → 数值与中文论断核对完成 → 引用人工核对和离线检查完成、联网门待补 → 保守润色完成 → QA与状态交接完成。框架与正文没有增加实验授权。

明确限制：18条主三机GT仿真+2条C1补充；报告级组合故障每条件n=1；实机只为独立单节点baseline。自动引用检查0/8联网verified；HTML浏览器视觉检查pending。全部缺失赛题结果保留五字段占位符。
