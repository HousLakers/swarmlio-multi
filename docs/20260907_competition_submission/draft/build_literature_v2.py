"""Record retrieved primary-source metadata and run the offline corpus workflow."""
import json, re, subprocess, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
WS=HERE/'literature_v2'
CORPUS=WS/'corpus.json'
SCRIPT='/home/houslakers/.codex/skills/literature-review/scripts/corpus.py'
papers=[
 ('fastlio2021','FAST-LIO2: Fast Direct LiDAR-inertial Odometry','Wei Xu;Yixi Cai;Dongjiao He;Jiarong Lin;Fu Zhang',2021,'arXiv','2107.06829',None,'https://arxiv.org/abs/2107.06829','直接点云配准与增量地图；公开处理器实验只支持设计动机，不是本项目功耗或频率证据。'),
 ('swarmlio2022','Swarm-LIO: Decentralized Swarm LiDAR-inertial Odometry','Fangcheng Zhu;Yunfan Ren;Fanze Kong;Huajie Wu;Siqi Liang;Nan Chen;Wei Xu;Fu Zhang',2022,'arXiv','2209.06628',None,'https://arxiv.org/abs/2209.06628','激光惯性与机间相互观测联合约束；初始提交为2022，访问版本更新于2023，不混写期刊信息。'),
 ('swarmlio2025','Swarm-LIO2: Decentralized Efficient LiDAR-Inertial Odometry for Aerial Swarm Systems','Fangcheng Zhu;Yunfan Ren;Longji Yin;Fanze Kong;Qingbo Liu;Ruize Xue;Wenyi Liu;Yixi Cai;Guozheng Lu;Haotian Li;Fu Zhang',2025,'IEEE Transactions on Robotics',None,'10.1109/TRO.2024.3522155','https://doi.org/10.1109/TRO.2024.3522155','出版年2025，在线及DOI含2024；原文的初始化、估计与边缘化支持3.1方法背景，不证明部署全部特性。'),
 ('yamauchi1997','A frontier-based approach for autonomous exploration','Brian Yamauchi',1997,'IEEE International Symposium on Computational Intelligence in Robotics and Automation',None,None,'https://www.cs.cmu.edu/~motionplanning/papers/sbp_papers/integrated2/yamauchi_frontier_explor.pdf','以已知自由空间与未知区域边界引导探索；采用原论文托管链接，未把未独立确认的DOI加入条目。'),
 ('fuel2020','FUEL: Fast UAV Exploration using Incremental Frontier Structure and Hierarchical Planning','Boyu Zhou;Yichen Zhang;Xinyi Chen;Shaojie Shen',2020,'arXiv','2010.11561',None,'https://arxiv.org/abs/2010.11561','增量frontier与层次规划；使用预印本身份，不混合后续期刊年份和未核验页码。'),
 ('racer2023','RACER: Rapid Collaborative Exploration With a Decentralized Multi-UAV System','Boyu Zhou;Hao Xu;Shaojie Shen',2023,'IEEE Transactions on Robotics',None,'10.1109/TRO.2023.3236945','https://doi.org/10.1109/TRO.2023.3236945','最接近先行框架；已有层次网格、成对分配及负载考虑，本文增量限于本地目标对照和任务恢复接口。'),
 ('cbba2009','Consensus-Based Decentralized Auctions for Robust Task Allocation','Han-Lim Choi;Luc Brunet;Jonathan P. How',2009,'IEEE Transactions on Robotics',None,'10.1109/TRO.2009.2022423','https://doi.org/10.1109/TRO.2009.2022423','拍卖与一致性协调任务冲突；原方法保证依赖假设，不转用为当前乐观任务协议的收敛证明。'),
 ('best2022','Resilient Multi-Sensor Exploration of Multifarious Environments with a Team of Aerial Robots','Graeme Best;Rohit Garg;John Keller;Geoffrey A. Hollinger;Sebastian Scherer',2022,'Robotics: Science and Systems',None,'10.15607/RSS.2022.XVIII.004','https://www.roboticsproceedings.org/rss18/p004.html','多传感器探索与行为组织应对复杂环境；仅用于弹性系统背景，不将其外场结果转记为本项目结果。')]
for key,title,authors,year,venue,arxiv,doi,url,note in papers:
    args=[sys.executable,SCRIPT,'--corpus',str(CORPUS),'add','--key',key,'--title',title,'--authors',authors,'--year',str(year),'--venue',venue,'--url',url,'--source','retrieved-primary-web','--update']
    if arxiv:args+=['--arxiv',arxiv]
    if doi:args+=['--doi',doi]
    subprocess.run(args,check=True,stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable,SCRIPT,'--corpus',str(CORPUS),'set',key,'--screened','included','--reason','支持正文实际主题；公开一手来源人工核对，自动联网门未完成'],check=True,stdout=subprocess.DEVNULL)
    (WS/'notes'/f'{key}.md').write_text(f'# {title}\n\n来源：{url}\n\n读取范围：公开摘要/出版元数据；Swarm-LIO2、RACER另读取公开HTML方法内容，Yamauchi读取原论文PDF。\n\n转述：{note}\n\n限制：未在本项目复现实验；未保存全文；自动引用核验仍待真实联系邮箱。\n')
c=json.loads(CORPUS.read_text());c['criteria']={'include':['直接支持正文五个主题的原论文、作者原文或出版记录','只引用实际使用的方法或系统范围'], 'exclude':['未能统一出版实例的候选','只凭题名相关但正文不使用的补位引用','营销及二手性能转述']}
c['search_log']=[{'date':'2026-09-08','source':'web primary-source search and open','query':q} for q in ['FAST-LIO2 arxiv Swarm-LIO Swarm-LIO2 TRO DOI','FUEL RACER paper hierarchical exploration','Yamauchi frontier 1997 original paper','Consensus-Based Decentralized Auctions Robust Task Allocation','Resilient Multi-Sensor Exploration RSS 2022','Navion JSSC algorithm hardware co-design ALLIANCE Parker original paper']]
c['excluded_candidates']=[{'name':'ALLIANCE','reason':'检索到1994作者PDF与1998期刊实例不同，本轮未混用两者；不进入正文。'},{'name':'Navion','reason':'作者原PDF获取不完整且短研究现状无需加入未充分读取的功耗比较；不进入正文。'}]
CORPUS.write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n')
# Export using corpus-owned keys, then enrich canonical fields without changing identities.
bib=subprocess.run([sys.executable,SCRIPT,'--corpus',str(CORPUS),'bibtex'],check=True,capture_output=True,text=True).stdout
extra={'swarmlio2025':{'volume':'41','pages':'960--981'},'racer2023':{'volume':'39','number':'3','pages':'1816--1835'},'cbba2009':{'volume':'25','number':'4','pages':'912--926'},'yamauchi1997':{'pages':'146--151'}}
for key,title,authors,year,venue,arxiv,doi,url,note in papers:
    fields={'url':url,**extra.get(key,{})}
    pattern=r'(@\w+\{'+re.escape(key)+r',\n)(.*?)(\n\})'
    bib=re.sub(pattern,lambda m:m[1]+m[2]+''.join(f'\n  {k} = {{{v}}},' for k,v in fields.items())+m[3],bib,flags=re.S)
(WS/'references.bib').write_text(bib)
clusters=[('激光惯性与协同估计',['fastlio2021','swarmlio2022','swarmlio2025'],'3.1'),('frontier与层次规划',['yamauchi1997','fuel2020'],'3.2'),('去中心化任务分配',['racer2023','cbba2009'],'3.2与6.2'),('弹性任务执行',['best2022','cbba2009'],'3.3与6.3'),('机载计算设计动机',['fastlio2021','swarmlio2025'],'2.2；不主张硬件算法协同创新')]
plan={'floor':2,'verification_scope':'manual primary-source verification; automated online gate pending','clusters':[{'name':n,'required_by':scope,'kind':'direct-prior-approach','refs':keys,'expected':True} for n,keys,scope in clusters]}
(WS/'coverage_plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
(WS/'themes.yml').write_text('themes:\n'+''.join(f'  - name: {n}\n    scope: {scope}\n' for n,keys,scope in clusters))
(WS/'review.md').write_text('# 支撑正文1.2的研究现状综合\n\n范围：五个实际论断主题；不是系统综述或全领域穷尽检索。人工一手来源核对与自动联网验证分开登记。\n\n'+''.join(f'## {n}\n\n适用正文：{scope}。引用：'+', '.join('[@'+k+']' for k in keys)+'。\n\n'+ ' '.join(p[-1] for p in papers if p[0] in keys)+'\n\n' for n,keys,scope in clusters))
(WS/'citation_number_map.json').write_text(json.dumps({str(i+1):p[0] for i,p in enumerate(papers)},ensure_ascii=False,indent=2)+'\n')
print('corpus, eight grounded notes, BibTeX, review and cluster plan written')
