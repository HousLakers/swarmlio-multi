# 参赛论文与答辩材料工作区

## 队友接手入口

本目录对应 GitHub 分支 [`paper-materials-20260909`](https://github.com/HousLakers/swarmlio-multi/tree/paper-materials-20260909)，用于继续整理论文、图表、引用和证据材料。新接手人先读 [团队论文交接说明](TEAM_HANDOFF_论文进一步修改_20260909.md)，再读 [v2 交付索引](draft/REWRITE_V2_INDEX.md)。

当前主稿是 [`draft/paper_draft_v2.md`](draft/paper_draft_v2.md)，Word 是由主稿派生的 [`draft/paper_draft_v2.docx`](draft/paper_draft_v2.docx)。不要把 Word 作为唯一编辑源；修改正文后运行 `draft/build_paper_docx.py` 重新生成 Word。

当前状态：论文结构稿已完成，正文保持 `DRAFT_NOT_SUBMITTABLE`。三机 GT 注册仿真、报告级任务层丢包和单节点实机 baseline 已分层；实机 ATE、统一频率、2 s 重规划、30 W 功耗、室内六/十机、AirSim 闭环、三机实机成功及完整国产化证明仍为空位。所有缺失结果必须保留 `[待填-指标：单位；n=待补；场景=...；数据来源=...；run ID=待补]` 五字段格式。

### 快速文件导航

| 目的 | 文件 |
|---|---|
| 继续改正文 | [`draft/paper_draft_v2.md`](draft/paper_draft_v2.md) |
| 查看 Word 成稿 | [`draft/paper_draft_v2.docx`](draft/paper_draft_v2.docx) |
| 看论断是否有证据 | [`draft/claim_ledger_v2.md`](draft/claim_ledger_v2.md) |
| 看赛题指标缺口 | [`evidence_matrix.md`](evidence_matrix.md) |
| 看引用边界 | [`draft/citation_plan_v2.md`](draft/citation_plan_v2.md) |
| 看 QA 与已知限制 | [`draft/qa_report_v2.md`](draft/qa_report_v2.md) |
| 看图件说明 | [`figures/v2/README.md`](figures/v2/README.md) |
| 看章节树和写作合同 | [`paper_writing_framework_v3.md`](paper_writing_framework_v3.md) |

## 继续修改时的三条规则

1. 数字先进入证据矩阵和论断台账，再同步正文、图表数据、图注和 Word；不能只改摘要或 Word。
2. 图表只能使用真实数据。缺数据的位置保留空图位，不画推测曲线、伪造轨迹或成功柱状图。
3. 新结果必须带精确 run ID、执行台账和 metrics，并区分仿真、报告级结果、单节点实机和 fleet 实机层级。

本目录沿用 2026-09-07 建立的“可写、可追溯、不夸大”写作框架，并在 2026-09-09 增加团队接手说明。它把赛题
`XH-202629` 的四类技术指标与已有仿真、单机实机和双机审计证据分开管理，
不把缺失的 2026-09-06 18:32 双机数据补写成成功实验。

## 文件入口

- [论文写作总交接](00_论文写作交接总说明_20260907.md)：按 `论文框架.docx` 整理的总说明、证据边界、GPT-6 提示词和逐章入口；本次写作先读此文件。
- [七章材料包](chapters/)：第一章至第七章逐章汇总正文素材、原始路径和留空项。
- [完整文件对应关系](index/文件对应关系_20260907.md)：全工作区分类索引和章节—文件映射；同目录 TSV 是全量普通文件清单。
- [论文框架](paper_outline.md)：论文/系统报告章节、每节论点、图表、实验方法和待补证据。
- [答辩 PPT 框架](ppt_outline.md)：建议 16:9、16 页、每页 action title、展品和讲述要点。
- [赛题指标证据矩阵](evidence_matrix.md)：要求、当前证据、证据等级、缺口和下一次验收动作。
- [GitHub skill 推荐](recommended_github_skills.md)：PPTX、学术汇报、综述与论文生命周期工具，均为可选且未自动安装。
- [双机 Archify 话题图](../../topic_flow_dual_real.html)：按单机图风格重绘的可交互 HTML。
- [三机本地准备包](../../deploy_triple_real/README.md)：三个独立包；UAV3 未填 IP/串口，当前 fail-closed。

## 证据口径

### 可以写入但必须保留实验层级的结果

- 阶段报告中的单机仿真：60.20 simulated s，coverage 72.94%，ATE RMSE 0.0802 m，P10
  clearance 1.898 m；crash/freeze/contact/ACK timeout/segmentation fault 均为 0。当前目录
  未找到完全对应的正式 runroot，定稿时按“阶段报告结果”并补原始证据。
- 三机仿真任务分配：18 轮矩阵 + 3 轮 C1；C1 的 MINMAX + 0.75 平均 fleet ratio
  0.2258、失衡比 1.10、Jaccard 0.7612，且无 abort。
- 报告中的掉线与 20% 任务层丢包仿真：记录了检测—释放—接管闭环；20% 丢包 coverage
  0.657，相对 0% 基线 0.673 为 97.6%，无崩溃。300 s 原始 runroot 当前未精确定位，不能
  用短时 `RUN-20260827T040141Z-3uav-verify-droploss20-90s` 替代。
- 节点级单机实机：UAV1 34.64 m/coverage 0.9288；UAV2 55.34 m/coverage 0.9874，
  其中 UAV2 保存了 5 cm PGM、PCD 和占用点；两者不能拼成 fleet 结论。

### 必须明确写成“未验证/缺证”的结果

- 用户确认的 2026-09-06 18:32 双机试飞原始 runroot、rosout、bridge、bag/ULog 均未找到，
  定类为 `EVIDENCE_MISSING`。
- 更早的 `fea8` 双机候选虽然有同步 planner trigger，但两端保存的 bridge 未过
  `armed + OFFBOARD + hover` 门，ID2 空 grid，定类为 `INVALID_RUN`，不能当作双机飞行成绩。
- 双机 ATE、统一 local-position payload/频率、5 cm fleet merged map、最小机间距、
  实机重规划延迟、机载功耗、三机硬件信息尚未形成合格证据。

## 写作顺序

1. 先把 `evidence_matrix.md` 中的每一条状态冻结为 `verified / partial / missing / invalid`。
2. 先写系统架构、算法和仿真结果；实机章节只写已保存的节点级 baseline 和诊断，双机写成
   “失效分析 + 证据恢复计划”，不要用观察印象补齐指标。
3. 论文和 PPT 共用同一组图号、表号和数字；数字变化只能先改矩阵，再同步正文和幻灯片。
4. 只有新的不解锁双机/三机 preflight 通过并产生可审计 runroot 后，才把相应条目升级为
   `verified`。任何正式实验仍需 high-terminal approval 和 low-terminal runroot。

## 推荐后续工具链

- 图：继续使用本地 `archify`，先 `validate --quality showcase` 再 `deliver`，浏览器
  `visual-check` 目前因机器没有 Chrome/Chromium 而跳过，不能宣称视觉审阅通过。
- 论文：用 Markdown/LaTeX 作为单一来源，指标矩阵作为数字审计表；引用、图表和实验
  版本均附文件路径或 run ID。
- PPT：先按 [ppt_outline.md](ppt_outline.md) 固定 action titles，再使用 PPTX skill
  生成可编辑 deck，最后做 PDF/PNG 逐页检查；不先堆文字。
