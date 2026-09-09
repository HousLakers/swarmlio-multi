# 可选 GitHub skills（仅推荐，未在本机安装）

本轮没有自动 clone 或安装第三方 skill；安装前应先审核许可证、依赖、网络访问和是否会
改写工作区。当前本地已使用 `high-terminal` 和 `archify` 完成规划、静态检查与话题图，
下面的项目用于下一阶段写作/PPT 生产与审稿，不替代证据审计。

## 优先推荐

1. **[jiandong01/pptx-skills](https://github.com/jiandong01/pptx-skills)**

   面向 Markdown→PPTX，提供模板抽取、图表抽取和 `build-slides` 三个 skill；适合把
   `ppt_outline.md` 和统一图表数据转成可编辑 deck。仓库 README 明确支持 Markdown 表格、
   图片、Mermaid 和多种原生 Excel 图表。建议先抽取学校/比赛模板，再生成草稿，最后人工
   检查字体和图注。

2. **[Gabberflast/academic-pptx-skill](https://github.com/Gabberflast/academic-pptx-skill)**

   专注学术汇报的内容结构：先定 slide-by-slide outline、action title 和 exhibit，再做
   PPTX 技术实现。它明确要求把内容/结构 skill 与底层 PPTX skill 分开使用，适合本项目的
   “论文证据→答辩叙事”流程。该仓库许可证是其自有条款，使用前必须先审核。

3. **[xingtaxueshu/literature-review-skills](https://github.com/xingtaxueshu/literature-review-skills)**

   提供问题收敛、综述模块、方法比较、矛盾映射和研究空白五个 skill，适合补写第 2 章
   相关工作，避免把“SLAM/多机协同/容错”写成没有边界的综述。仓库同时给出 Codex 的
   安装目录示例；建议只安装需要的 review skills，并对每条引用做原文核验。

## 可作为第二选择

- **[ShaishavMaisuria/research-paper-lifecycle-skills](https://github.com/ShaishavMaisuria/research-paper-lifecycle-skills)**：
  覆盖论文生命周期、引用核验、投稿、rebuttal 和 presentation，适合后期做交叉审稿与
  提交清单；仓库标注 Apache-2.0，但其“venue rules”仍需按比赛最新通知复核。
- **[O0000-code/awesome-academic-skills](https://github.com/O0000-code/awesome-academic-skills)**：
  作为索引浏览更多学术 skill，不建议直接把索引中的所有包一次性安装。
- **[anthropics/skills](https://github.com/anthropics/skills/tree/main/skills/pptx)**：
  可参考其 PPTX skill 的结构和 QA 思路；这是 Anthropic 生态材料，受其条款约束，不把
  它当作本地 Codex skill 直接复制或混入仓库。

## 推荐采用顺序

```text
evidence_matrix.md
    ↓
literature-review-skills（相关工作和研究缺口）
    ↓
academic-pptx-skill（action titles + exhibits）
    ↓
pptx-skills（模板、图表和可编辑 PPTX）
    ↓
人工逐页 QA + high-terminal 审核
```

第三方 skill 可以整理文字、表格和布局，但不能替代本项目的 runroot、manifest、hash、
安全门和 `EVIDENCE_MISSING/INVALID_RUN` 分类。
