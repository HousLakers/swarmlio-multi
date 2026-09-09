# 引用计划与核验记录 v2

日期：2026-09-08。对应 [正文](paper_draft_v2.md) 与 [BibTeX](literature_v2/references.bib)。本轮已完成支持当前正文范围的检索、筛选、原始来源核对与引用布置；学术索引 API 联网核验未完成，不得称为所有引用自动验证通过。

## 1. 核验状态

公开一手来源核对：正文8篇均有原论文、预印本或出版页面来源，作者、题名、年份和可用标识符已逐项核对。FAST-LIO2、Swarm-LIO、FUEL明确采用预印本实例；Swarm-LIO2与RACER采用期刊实例，不混合预印本题名、期刊年和卷页。

离线脚本原样输出：

```text
VERDICT-LINE: PASS: 0/8 verified, 0 errors, 0 warnings (0 checks skipped)
```

上述PASS仅为本次 `--offline` 的解析与静态检查；8项均为 `PARSED_ONLY`，0项获得自动联网验证。证据：[完整回执](audit_v2/citations_offline.txt)、[机器JSON](audit_v2/citations_offline.json)。语料库按回执同步后保留 `verified=false`，未将人工核对伪装成学术索引API确认。[check_review](audit_v2/review_gate.txt) 因8项未自动验证返回FAIL；这项待办明确保留。

未完成的原因：当前未提供真实 `CONTACT_EMAIL`。已按 [verify-citations SKILL.md](/home/houslakers/.codex/skills/verify-citations/SKILL.md) 的“Ask the user for it if unset; never invent one.”要求提出联系邮箱问题，没有伪造邮箱，也没有使用论文作者邮箱代替。此邮箱只用于学术索引请求标识，不发送邮件。继续写作依据用户明确授权；投稿前须完成联网元数据、撤稿与出版实例检查。

## 2. 正文编号、文献实例与使用边界

| 编号 / key | 一手来源与实例 | 正文用途 | 不承载的论断 |
|---|---|---|---|
| [1] fastlio2021 | [arXiv:2107.06829](https://arxiv.org/abs/2107.06829)，Xu等，2021 | 1.2、3.1：直接点云配准、增量地图与计算设计动机 | 本机ATE、功耗、统一10 Hz |
| [2] swarmlio2022 | [arXiv:2209.06628](https://arxiv.org/abs/2209.06628)，Zhu等，初始年2022；访问版本v3更新于2023 | 1.2、3.1：相互观测与分布式估计 | 本项目协同实飞精度 |
| [3] swarmlio2025 | [IEEE DOI](https://doi.org/10.1109/TRO.2024.3522155)，T-RO 41:960–981，2025；公开技术文本为[2409.17798v1](https://arxiv.org/html/2409.17798v1) | 1.2、3.1：初始化、估计与效率，参考原文III–V节 | 本地部署全部启用、原生LIO心跳等于任务协议 |
| [4] yamauchi1997 | [原论文PDF](https://www.cs.cmu.edu/~motionplanning/papers/sbp_papers/integrated2/yamauchi_frontier_explor.pdf)，Yamauchi，CIRA 1997:146–151 | 1.2：frontier的概念来源 | 当前规划器新颖性、性能排名 |
| [5] fuel2020 | [arXiv:2010.11561](https://arxiv.org/abs/2010.11561)，Zhou等，2020 | 1.2、2.3：增量frontier与层次规划 | 原论文速度倍率转为本项目收益 |
| [6] racer2023 | [IEEE DOI](https://doi.org/10.1109/TRO.2023.3236945)，T-RO 39(3):1816–1835，2023；[公开原文](https://arxiv.org/html/2209.08533v1) | 1.2、3.2、6.2：最接近先行框架与增量边界 | 首次负载均衡、首次去中心化多机探索 |
| [7] cbba2009 | [IEEE DOI](https://doi.org/10.1109/TRO.2009.2022423)，Choi、Brunet、How，T-RO 25(4):912–926，2009 | 1.2：拍卖与一致性处理任务冲突 | 本项目乐观协议具有同样收敛保证 |
| [8] best2022 | [RSS官方论文及BibTeX](https://www.roboticsproceedings.org/rss18/p004.html)，Best等，2022；DOI 10.15607/RSS.2022.XVIII.004 | 1.2：复杂环境中多传感器探索与行为组织 | 本项目三机外场成功、实际恢复率 |

完整作者写入BibTeX，正文按三名后et al.形式压缩。没有给未独立确认的文献编造DOI。Yamauchi使用已读取的原论文链接作为可解析来源。参考条目不引用搜索结果页，不把项目内部报告伪装成学术出版物。

## 3. 五个必需主题与检索路径

主题由正文承诺导出，而不是从检索结果倒推：激光惯性与协同估计、frontier与层次规划、去中心化任务分配、弹性任务执行、机载计算设计动机。具体查询与筛选记录位于 [corpus.json](literature_v2/corpus.json)，每篇转述笔记位于 [notes](literature_v2/notes)。本稿定位是系统论文的简洁研究现状，不是穷尽性综述。

五个主题各有至少两项实际使用的引用键；[覆盖检查](audit_v2/related_coverage.txt) 未发现空主题。该检查只计算主题—引用键覆盖，不验证文献真伪；报告中的confirmed表示计划中实际引用，不代表API验证。机载计算主题仅讨论高效估计的动机，没有扩张为硬件算法协同或国产芯片性能贡献，因而未用无关加速器论文补足数量。

ALLIANCE候选中读到1994作者PDF，但与拟用1998期刊实例不同，未混用；Navion候选的原PDF访问不完整，且正文未主张其硬件功耗比较，未纳入。排除理由已登记。若后续加入国产平台性能或硬件协同创新，应重新检索直接相关工作，再扩展论断；当前参考集合不支持这一扩张。

## 4. 文件一致性与下一步

- 语料库是引用键来源，生成后补充已核对的URL与卷页，未另造引用键。
- [编号映射](literature_v2/citation_number_map.json) 将正文[1]—[8]与BibTeX绑定；[corpus_keys](audit_v2/corpus_keys.txt)检查纳入集合一致。
- [review.md](literature_v2/review.md)保存支撑1.2的主题综合；`review_audit.tex`仅将引用标记转换为TeX语法以适配离线检查，不是投稿模板。
- [audit_bib](audit_v2/related_bib.txt)检查8条引用均被使用且可解析标识存在；不代替联网核验。
- 下一步是提供请求标识后运行学术索引核验并处理真实差异，再依据比赛版式统一参考文献格式。本轮稿件不因离线PASS获得可投稿状态。
