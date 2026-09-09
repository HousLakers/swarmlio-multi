"""Static manuscript checks and skill invocations; no experiment or source mutations."""
import collections, difflib, hashlib, json, re, subprocess, sys, zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];AUDIT=HERE/'audit_v2';LIT=HERE/'literature_v2'
PAPER=HERE/'paper_draft_v2.md';text=PAPER.read_text()
def write(name,obj): (AUDIT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def invoke(name,args):
    r=subprocess.run([sys.executable]+args,capture_output=True,text=True)
    (AUDIT/(name+'.txt')).write_text(r.stdout+r.stderr)
    return {'exit_code':r.returncode,'artifact':name+'.txt'}

# Freeze then make a bounded prose-only pass. Re-runs preserve the first snapshot.
before=AUDIT/'paper_before_polish.md'
if not before.exists():before.write_text(text)
replacements={
 '面向国产机载计算平台的系统设计，应把这些问题放入感知、决策与执行相互反馈的链路中，并分别测量算法效果、任务连续性与资源开销。':'国产机载计算平台上的系统需要协调感知、决策与执行，并分别测量算法效果、任务连续性和资源开销。',
 '本文将算法原理与实验输入分开。':'评价时需要区分算法原理与实际输入。',
 '本文把进展检查、候选目标历史与轨迹安全检查组织成明确接口，分别回答是否需要恢复、恢复到哪里以及恢复动作是否可执行。':'进展检查判断是否需要恢复，候选目标历史帮助选择恢复方向，轨迹安全检查约束恢复动作。',
 '这一组织方式属于系统机制设计。':'这些接口构成系统的恢复机制设计。',
 '弹性决策的应用增量是让故障后的任务归属变化具有可解释状态：':'弹性决策通过不同状态处理故障后的任务归属：',
 '本文组织了多无人机感知、探索分配和弹性任务协调的系统方案，并以统一的统计定义重新解释已有仿真及单节点实机材料。':'本文给出多无人机感知、探索分配和弹性任务协调方案，并按统一的统计定义分析已有仿真与单节点实机材料。'
}
for old,new in replacements.items():text=text.replace(old,new)
def inventory(t):
    return {'numbers':re.findall(r'\d+(?:\.\d+)?',t),
      'citations':re.findall(r'\[(?:\d+[–,]?)+\]',t),
      'placeholders':re.findall(r'\[待填-[^\]]+\]',t),
      'units_terms':re.findall(r'\b(?:m|s|ms|Hz|W|RMS|RMSE|ATE|GT|LIO|MINSUM|MINMAX|EVIDENCE_MISSING|INVALID_RUN|REAL_NODE_BASELINE)\b',t),
      'equations':re.findall(r'\\\[.*?\\\]',t,re.S),
      'headings':re.findall(r'^#{2,3} .+$',t,re.M)}
frozen=inventory(before.read_text());after=inventory(text);assert frozen==after,'polish changed frozen facts'
PAPER.write_text(text)
write('polish_inventory.json',{'equal':True,'before':frozen,'after':after,'scope':'numbers, units/terms, citation markers, headings, equations, exact placeholders; semantic review also required'})
(AUDIT/'polish.diff').write_text(''.join(difflib.unified_diff(before.read_text().splitlines(True),text.splitlines(True),fromfile='before_polish',tofile='paper_draft_v2.md')))

# Extract literal manuscript numbers, then compare them with separately recomputed metrics.
claims=[];metrics={};groupstats=json.loads((AUDIT/'matrix_statistics.json').read_text())
for line in text.splitlines():
    parts=[p.strip() for p in line.strip('|').split('|')]
    if len(parts)==7 and parts[0] in groupstats and '±' in line:
        g=parts[0];assert int(parts[1])==groupstats[g]['n']
        for cell,m in zip(parts[2:],['coverage','path_m','imbalance','jaccard','overlap']):
            for value,kind in zip(cell.split('±'),['mean','sd']):
                key=f'{g}.{m}.{kind}';claims.append({'id':key,'metric':key,'value':float(value),'is_percent':False,'source':'paper_draft_v2.md Table 8'});metrics[key]=groupstats[g][m][kind]
real=json.loads((AUDIT/'real_metrics.json').read_text())
for idx,r in enumerate(real,1):
    line=next(l for l in text.splitlines() if l.startswith(f'| R{idx} | 1 |'))
    cells=[p.strip() for p in line.strip('|').split('|')]
    for pos,m in [(2,'trajectory_samples'),(3,'elapsed_s'),(4,'path_xy_m'),(5,'coverage_final')]:
        key=f'R{idx}.{m}';claims.append({'id':key,'metric':key,'value':float(cells[pos]),'is_percent':False,'source':'paper_draft_v2.md Table 11'});metrics[key]=r[m]
write('numeric_claims.json',{'claims':claims});write('numeric_reference.json',metrics)
records=json.loads((AUDIT/'matrix_records.json').read_text());ledger=HERE/'claim_ledger_v2.md';lt=ledger.read_text()
if '<!-- RUN_TABLE -->' in lt:
    table='| 逻辑槽 | run ID（均位于results/） | 角色 |\n|---|---|---|\n'+''.join(f"| {r['key']} | `{r['run_id']}` | {r['role']} |\n" for r in records)
    ledger.write_text(lt.replace('<!-- RUN_TABLE -->',table))

# Required tree is extracted afresh from DOCX, normalizing whitespace and only prescribed numbering.
with zipfile.ZipFile(ROOT/'论文框架.docx') as z:doc=ET.fromstring(z.read('word/document.xml'))
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
paras=[''.join(p.itertext()).strip() for p in []] # use text nodes only below
paras=[''.join(t.text or '' for t in p.findall('.//w:t',ns)).strip() for p in doc.findall('.//w:p',ns)]
expected=[];chapter=0;intro=0
for p in paras:
    p=re.sub(r'\s+','',p)
    if re.match(r'^第[一二三四五六七]章',p):chapter+=1;expected.append(p)
    elif p and (re.match(r'^\d\.\d',p) or (chapter==1 and p in ['项目背景（简洁）','研究现状（简洁）','项目目标'])):
        if chapter==1 and not re.match(r'^\d',p):intro+=1;p=f'1.{intro}'+p
        if chapter==5:p=re.sub(r'^4\.', '5.',p)
        expected.append(p)
actual=[re.sub(r'\s+','',h) for h in re.findall(r'^#{2,3} (.+)$',text,re.M) if h!='参考文献']
assert expected==actual,(expected,actual)
holders=re.findall(r'\[待填-[^\]]*\]',text)
for h in holders:
    fields=h[4:-1].split('；');assert len(fields)==5 and '：' in fields[0] and fields[1].startswith('n=') and fields[2].startswith('场景=') and fields[3].startswith('数据来源=') and fields[4].startswith('run ID='),h
links=re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',text)
for link in links:
    if not link.startswith('http'):assert (HERE/link).is_file(),link
svgs=list((HERE.parent/'figures/v2').glob('*.svg'))
for f in svgs:ET.parse(f)
body=text.split('## 第一章：绪论')[1].split('## 参考文献')[0]
for term in ['SSH','ssh ','roslaunch','rostopic','终端命令','逐行日志','排障经过','参数试错']:
    assert term not in body,term
assert all(x in body for x in ['EVIDENCE_MISSING','INVALID_RUN','fea8','18:32'])
hashes=json.loads((AUDIT/'input_hashes.json').read_text())
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items())
assert len(re.findall(r'^\*\*表 \d+　',text,re.M))==15
assert len(re.findall(r'^!\[图 ',text,re.M))==6
write('structure_check.json',{'status':'PASS','chapters':7,'subsections':20,'docx_tree_exact_after_authorized_normalization':True,'placeholders':len(holders),'tables':15,'figures':6,'svg_xml_valid':len(svgs),'input_hashes_unchanged':len(hashes),'numeric_claims_extracted':len(claims),'manuscript_sha256':hashlib.sha256(PAPER.read_bytes()).hexdigest()})

base='/home/houslakers/.codex/skills/'
checks={}
checks['metrics']=invoke('metrics_check',[base+'verify-results/scripts/compare_metrics.py','--ledger',str(AUDIT/'numeric_claims.json'),'--metrics',str(AUDIT/'numeric_reference.json'),'--rel-tol','0','--abs-tol','0.00005','--strict','--json'])
checks['claims']=invoke('claim_audit',[base+'verify-claims/scripts/claim_audit.py',str(PAPER),'--json',str(AUDIT/'claims_linter.json')])
checks['prose']=invoke('prose_lint',[base+'polish-prose/scripts/prose_lint.py',str(PAPER)])
checks['terminology']=invoke('terminology_check',[base+'polish-prose/scripts/terminology_check.py',str(PAPER),'--allow','GT,LIO,ATE,RMS,RMSE,IMU,SDF,PGM,BOM,OS,ID'])
checks['citations']=invoke('citations_offline',[base+'verify-citations/scripts/check_bibtex.py',str(LIT/'references.bib'),'--offline','--json',str(AUDIT/'citations_offline.json')])
checks['corpus_verification']=invoke('corpus_verification',[base+'literature-review/scripts/corpus.py','--corpus',str(LIT/'corpus.json'),'verify-audit','--report',str(AUDIT/'citations_offline.json')])
checks['corpus_keys']=invoke('corpus_keys',[base+'literature-review/scripts/corpus.py','--corpus',str(LIT/'corpus.json'),'check-keys',str(LIT/'references.bib')])
checks['related_coverage']=invoke('related_coverage',[base+'draft-related-work/scripts/check_coverage.py',str(LIT/'coverage_plan.json'),'--json'])
review_tex=re.sub(r'\[@([a-z0-9-]+)\]',lambda m:'\\cite{'+m[1]+'}',(LIT/'review.md').read_text())
(LIT/'review_audit.tex').write_text('% Citation-syntax adapter for an offline TeX-only checker; not a paper template.\n'+review_tex)
checks['related_bib']=invoke('related_bib',[base+'draft-related-work/scripts/audit_bib.py',str(LIT/'references.bib'),'--tex',str(LIT/'review_audit.tex')])
checks['review_gate']=invoke('review_gate',[base+'literature-review/scripts/check_review.py',str(LIT/'review.md'),'--bib',str(LIT/'references.bib')])
write('skill_checks.json',checks)
print(json.dumps({'static':'PASS','checks':checks},ensure_ascii=False,indent=2))
