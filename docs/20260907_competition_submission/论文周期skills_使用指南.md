# 论文生命周期 skills 使用指南

## 一句话理解

论文周期 skills 不是一个“自动把论文写完”的按钮，而是一组按阶段协作的检查器和写作助手。它们把论文工作拆成：定位 → 结构 → 研究现状 → 初稿 → 结果/引用核验 → 去 AI 化 → 反思 → PPT/投稿准备。可以一直迭代，但每一轮都要有版本、目标和验收信号。

## 你实际会怎么用

### 1. 先设定论文定位

使用 `paper-profile`，告诉它：论文类型（建议 `systems`/`empirical`）、贡献类型（建议 `system`）、读者、风险偏好（建议 `safe` 或 `balanced`）和写作偏好（中文、正式、少套话、保留技术限定）。它会在论文目录生成 `.paper-memory/profile.yml`。这是定位配置，不是论文正文；后续 skills 会读取它来统一语气、贡献表述和审稿尺度。

### 2. 先做结构，不急着润色

用 `refactor-structure` 检查“贡献—证据—结论”是否对应。对本项目，先锁定 `paper_writing_framework_v2.md` 的七章树，再开始写段落。

### 3. 生成研究现状和相关工作

```text
literature-review-skills
  → refine-literature-question
  → decompose-review-modules
  → compare-research-methods
  → locate-review-research-gap
  → draft-related-work
```

所有引用都要经过 `verify-citations`。没有原文时保留 `[待补-引用]`，不能让模型凭记忆补作者和 DOI。

### 4. 生成论文初稿

使用 `orchestrate-paper` 作为总控，但它要求每个阶段停下来给作者检查。对本项目的阶段顺序是：

```text
框架 v2 → 逐章草稿 v1 → 结果/引用账本 → 论文级图表 → 去 AI 化 → 反思审校
```

总控 skill 不会把缺失实验伪装成成功；它会把缺失项变成阻塞项或结构化占位符。

### 5. 结果和结论核验

- `verify-claims`：检查每条“我们证明/优于/达到/显著”的句子有没有表、图、实验或文献支撑。
- `verify-results`：检查论文数字和实验输出是否一致；它区分“数值一致”和“独立复现”。
- `assess-paper`：汇总结构、完整性、引用和审稿风险。

### 6. 去 AI 化

使用 `polish-prose`，但它不是 AI 检测规避工具。它会先冻结数字、引用和技术结论，再减少模板化连接词、空泛动词、过度被动句和重复套话；润色后必须重新检查数字和引用没有变化。

### 7. 迭代方式

```text
目标：把第 X 章从“提纲”变成“可审阅初稿”
输入版本：paper_draft_vN.md + evidence_matrix.md
允许改动：段落组织、表达、图表占位
禁止改动：实验事实、数字、引用、源码、原始 runroot
验收信号：章节完整、claim ledger 有映射、prose lint 通过、无虚构引用
输出：paper_draft_vN+1.md + QA 报告
```

可以循环很多轮，但每轮都要增加可审阅性；如果只是换同义词而没有结构或证据改善，就停止。

## 关于“先假设实验成功”的正确用法

可以把论文的章节结构、表格列、图位和结果解释路径先按完整实验设计出来，便于后续填数；但不能把空白单元格写成已获得的成功结果。推荐使用：

```text
[待填-三机室内 coverage：均值±标准差；n；场景；数据文件]
```

而不是：

```text
三机室内实验成功完成，coverage 达到 XX。
```

这样既保持论文叙事完整，也不会在正式提交前留下无法追溯的结论。
