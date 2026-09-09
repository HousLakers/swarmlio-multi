# QA report v1

**状态**：`DRAFT_NOT_SUBMITTABLE`  
**输入**：`paper_draft_v1.md`、`paper_writing_framework_v2.md`、`evidence_matrix.md`  
**日期**：2026-09-08

## 已完成

- 章节树严格对应《论文框架.docx》七章；第五章编号已统一为 5.1–5.3。
- 已建立摘要、正文、表格、图位、参考文献和展望，正文没有展开日常调试命令或逐行日志。
- 已将当前可追溯仿真数字和单机节点级数字绑定到 claim ledger；未验证结果保留结构化占位符。
- 已生成三幅论文级 SVG：系统架构、三机任务分配统计、弹性决策状态机；SVG XML 解析通过。
- 已保留 `EVIDENCE_MISSING`/`INVALID_RUN` 的内部状态，没有把它们润色成成功结论。

## 尚未完成的硬门

| 检查项 | 状态 | 下一动作 |
|---|---|---|
| 结果占位符绑定真实 runroot | BLOCKED | 归档实验数据后填写 |
| frontier/分配/容错/国产算力外部引用 | BLOCKED | `literature-review` + `verify-citations` |
| 数字与原始 metrics 一致性 | PARTIAL | `verify-results`，不启动重实验 |
| claim→evidence 矩阵 | PASS（初版） | `verify-claims` 后复核 |
| 去 AI 化 | PENDING | `polish-prose` 先 lint，再人工确认表达 |
| 图表视觉 QA | PENDING | 浏览器/图像检查，确认字体与图注 |
| 摘要提交资格 | BLOCKED | 绑定 typed result slots 后再 lint |

## 不能声称的内容

真实三机成功、双机 ATE/融合地图、室内六/十机、AirSim 探索闭环、实机 ≥10 Hz、≤2 s 重规划、≤30 W、完整国产化和最终演示视频均尚未形成可审计证据。

## 下一唯一动作

由作者确认 `paper_writing_framework_v2.md` 的结构和术语；确认后进入论文草稿 v2 的引用检索、结果绑定和 `polish-prose` 阶段。不要通过增加形容词或改写占位符绕过证据硬门。
