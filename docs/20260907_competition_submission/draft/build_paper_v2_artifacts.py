"""Read only indexed evidence; write paper-derived figures and numeric audit tables."""
import os
os.environ.setdefault('MPLCONFIGDIR', '/tmp/paper_v2_mpl')
import csv, hashlib, json, re, statistics, sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[3]
PAPER = ROOT/'docs/20260907_competition_submission'
OUT = PAPER/'figures/v2'
AUDIT = PAPER/'draft/audit_v2'
OUT.mkdir(exist_ok=True); AUDIT.mkdir(exist_ok=True)
FONT = FontProperties(fname='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
plt.rcParams.update({'font.family': FONT.get_name(), 'font.size': 9, 'svg.fonttype':'path', 'pdf.fonttype':42, 'axes.spines.top':False, 'axes.spines.right':False})
HASHES = {}
def read(path):
    path=Path(path); data=path.read_bytes(); HASHES[str(path.relative_to(ROOT))]=hashlib.sha256(data).hexdigest(); return data
def js(path): return json.loads(read(path))
def write(path, obj): path.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n')
def save(fig, stem):
    for ext in ['svg','pdf','png']: fig.savefig(OUT/f'{stem}.{ext}', dpi=180, bbox_inches='tight', facecolor='white')
    plt.close(fig)
def box(ax,xy,text,w=.18,h=.14,color='#e9f3f8'):
    x,y=xy; ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.012',facecolor=color,edgecolor='#416275',linewidth=1))
    ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=10)
def arrow(ax,a,b,label=None):
    ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=12,color='#416275',linewidth=1.1))
    if label: ax.text((a[0]+b[0])/2,(a[1]+b[1])/2+.025,label,ha='center',fontsize=8,backgroundcolor='white')

rows=[json.loads(x) for x in read(ROOT/'experiments/matrix_results.jsonl').decode().splitlines() if x.strip()]
final={r['key']:r for r in rows if r.get('status')=='done'}
records=[]
for key,r in sorted(final.items()):
    path=(ROOT/Path(r['runroot'])).resolve(); meta=dict(r)
    for old in rows:
        if old.get('runroot') and (ROOT/Path(old['runroot'])).resolve()==path:
            for k in ['manifest_sha256','source_hash_sha256']:
                if old.get(k):
                    if meta.get(k) and meta[k]!=old[k]: raise ValueError('conflicting same-run hash '+key)
                    meta[k]=old[k]
    fleet=js(path/'fleet/metrics.json')
    uavs=[js(path/f'uav{i}/metrics.json') for i in range(3)]
    lengths=[u['path_length_m'] for u in uavs]
    manifest_hash=hashlib.sha256(read(path/'manifest.yaml')).hexdigest()
    if meta.get('manifest_sha256'): assert manifest_hash==meta['manifest_sha256'],key
    execution=js(path/'execution_result.json') if (path/'execution_result.json').exists() else None
    for name in ['static.yaml','static_preflight.json','live_preflight.json','2uav_approval.yaml']:
        if (path/name).exists(): read(path/name)
    approval=yaml.safe_load(read(path/'2uav_approval.yaml'))
    assert approval['approved'] and approval['manifest_sha256']==manifest_hash,key
    if meta.get('source_hash_sha256'):
        assert approval['source_hash_manifest_sha256']==meta['source_hash_sha256'],key
    included=key!='C1-r2'
    if included:
        assert execution and execution['exit_reason']=='duration_complete',key
        assert execution['final_safety_passed'] and fleet['telemetry_completeness'],key
    records.append({'key':key,'group':r['group'],'run_id':path.name,'runroot':str(path.relative_to(ROOT)),
        'included':included,'role':'main' if key[0] in 'AB' else 'supplement' if included else 'excluded_duration_incomplete',
        'coverage':fleet['fleet_coverage_ratio'],'path_m':sum(lengths),'imbalance':max(lengths)/min(lengths),
        'jaccard':fleet['map_consistency_jaccard'],'overlap':fleet['overlap_ratio'],
        'manifest_hash_matches_index':manifest_hash==meta.get('manifest_sha256') if meta.get('manifest_sha256') else None,
        'execution_available':execution is not None,'per_uav_path_m':lengths,'contact_count':fleet['fleet_contact_count']})
metrics=['coverage','path_m','imbalance','jaccard','overlap']; groups=['A1','A2','A3','B1','B2','B3','C1']
stats={}
for g in groups:
    rr=[r for r in records if r['group']==g and r['included']]
    stats[g]={'n':len(rr),**{m:{'mean':statistics.mean(r[m] for r in rr),'sd':statistics.stdev(r[m] for r in rr)} for m in metrics}}
write(AUDIT/'matrix_records.json',records); write(AUDIT/'matrix_statistics.json',stats)
with (OUT/'fig03_matrix_data.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['key','run_id','included']+metrics,extrasaction='ignore');w.writeheader();w.writerows(records)
fig,axs=plt.subplots(2,3,figsize=(13,7.3),constrained_layout=True)
labels=['占据体素比例（无量纲）','总路径长度（m）','路径最大/最小比（无量纲）','最小成对 Jaccard（无量纲）','最小成对 overlap（无量纲）']
colors=['#486e9c']*3+['#bc6b33']*3+['#737373']
for ax,m,label in zip(axs.flat,metrics,labels):
    for i,g in enumerate(groups):
        vals=[r[m] for r in records if r['group']==g and r['included']]
        ax.scatter(np.linspace(i-.12,i+.12,len(vals)),vals,s=23,color=colors[i],alpha=.65,zorder=3)
        ax.errorbar(i,stats[g][m]['mean'],yerr=stats[g][m]['sd'],fmt='D',markersize=4,capsize=4,color=colors[i],zorder=4)
    ax.set_xticks(range(7));ax.set_xticklabels(['A1\nn=3','A2\nn=3','A3\nn=3','B1\nn=3','B2\nn=3','B3\nn=3','C1*\nn=2']);ax.set_title(label);ax.grid(axis='y',alpha=.2);ax.axvline(5.5,color='#aaaaaa',ls=':')
axs.flat[-1].axis('off');axs.flat[-1].text(.02,.93,'点：单次记录\n菱形及误差线：均值 ± 样本标准差\n\nA：无注入掉线；B：60 s 节点级掉线\nA1/B1：MINSUM，cap=0.75\nA2/B2：MINMAX，cap=0.75\nA3/B3：MINMAX，cap=0.50\n\nC1*：补充组；剔除时长不同的 C1-r2\n同一配置种子；不作显著性推断\nGT 注册三机仿真；不能替代实机 LIO',va='top',linespacing=1.6)
save(fig,'fig03_minmax_minsum')

# Static paper view derives its nodes/labels from the delivered Archify specification.
spec=js(OUT/'fig01_system_flow.dataflow.json'); nodes={n['id']:n for n in spec['nodes']}
fig,ax=plt.subplots(figsize=(13,4.8)); ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
ids=['sensing','estimation','frontiers','assignment','execution']
for i,k in enumerate(ids):
    n=nodes[k]; box(ax,(.015+i*.197,.68),n['label']+'\n'+n['sublabel'],w=.174,h=.20)
    if i: arrow(ax,(.015+(i-1)*.197+.174,.78),(.015+i*.197,.78))
for k,xy in [('reference',(.21,.20)),('teammates',(.60,.20)),('health',(.80,.20))]:
    n=nodes[k];box(ax,xy,n['label']+'\n'+n['sublabel'],w=.174,h=.20,color='#faf0df')
arrow(ax,(.297,.40),(.297,.68),'参考角色按实验披露');arrow(ax,(.687,.40),(.687,.68),'任务与心跳');arrow(ax,(.887,.68),(.887,.40),'执行反馈');arrow(ax,(.80,.30),(.774,.30))
ax.text(.02,.02,'系统设计图：箭头表示数据依赖；各实验实际启用链路须分别说明。',fontsize=10)
save(fig,'fig01_system_flow')

fig,axs=plt.subplots(1,2,figsize=(13,5.2))
for ax in axs: ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
ax=axs[0];ax.set_title('(a) 节点掉线 → 任务接管（机制图）')
for y,t in [(.78,'在线：有效状态持续更新'),(.54,'连续缺失：确认节点离线'),(.30,'释放失联节点任务'),(.06,'在线节点按距离接管')]:box(ax,(.16,y),t,w=.69,h=.13)
for y in [.78,.54,.30]:arrow(ax,(.505,y),(.505,y-.10))
ax=axs[1];ax.set_title('(b) 任务层丢包 → 协调（机制图）')
for y,t in [(.78,'发起分配：本地乐观应用并保存旧状态'),(.54,'等待响应：同时间戳重传；接收方重答'),(.30,'明确拒绝：回滚｜超时：结束等待'),(.06,'心跳核对任务归属；重复认领协调')]:box(ax,(.04,y),t,w=.91,h=.13,color='#faf0df')
for y in [.78,.54,.30]:arrow(ax,(.495,y),(.495,y-.10))
fig.text(.5,-.01,'20% 是任务消息注入条件；不丢弃 swarm_traj。状态箭头不表示实测时延或成功概率。',ha='center',fontsize=10)
save(fig,'fig02_dropout_packetloss_states')

report=ROOT/'experiments/多机容错通信改进总结_掉线任务重分配与20%丢包_20260822.md';read(report)
write(OUT/'fig04_report_data.json',{'source':str(report.relative_to(ROOT)),'level':'report_only_simulation','dropout_s':75,'duration_sim_s':300,'n_per_condition':1,'values':[{'round':32,'task_loss':0,'map_coverage':.673},{'round':33,'task_loss':.20,'map_coverage':.657}],'denominator':'not independently bound to raw run'})
fig,ax=plt.subplots(figsize=(7,3.7));ax.scatter([0,1],[.673,.657],s=65,color=['#486e9c','#bc6b33']);ax.set_xticks([0,1]);ax.set_xticklabels(['第 32 轮：0% 任务层丢包','第 33 轮：20% 任务层丢包']);ax.set(xlim=(-.5,1.5),ylim=(0,1),ylabel='报告 map_coverage（无量纲）');ax.grid(axis='y',alpha=.2)
for x,y in [(0,.673),(1,.657)]:ax.annotate(f'{y:.3f}',(x,y),xytext=(0,10),textcoords='offset points',ha='center')
ax.set_title('均叠加 75 s 单节点掉线；每条件 n=1；300 s 仿真报告');save(fig,'fig04_packetloss_report')

specs=js(ROOT/'state/real_dual_audit_20260906/single_overlays_20260907/single_overlay_metrics.json')
real=[];fig,axs=plt.subplots(1,2,figsize=(10,5.6),constrained_layout=True)
for idx,s in enumerate(specs):
    run=ROOT/s['run'];meta=js(run/'metadata.json')
    trajectory_rows=list(csv.DictReader(read(run/'trajectory.csv').decode().splitlines()))
    valid=[]
    for row in trajectory_rows:
        try: valid.append([float(row[k]) for k in ['elapsed_s','x','y','z']])
        except (ValueError, TypeError, KeyError): pass
    traj=np.array(valid)
    coverage=list(csv.DictReader(read(run/'coverage.csv').decode().splitlines()))
    length=float(np.linalg.norm(np.diff(traj[:,1:3],axis=0),axis=1).sum())
    valid_coverage=[]
    for row in coverage:
        try: valid_coverage.append(float(row['coverage']))
        except (ValueError, TypeError, KeyError): pass
    real.append({'run_id':run.name,'runroot':s['run'],'n':1,'trajectory_samples':len(traj),'trajectory_invalid_rows':len(trajectory_rows)-len(valid),'elapsed_s':float(traj[-1,0]-traj[0,0]),'path_xy_m':length,'coverage_final':valid_coverage[-1],'pgm_available':(run/'grid_map.pgm').is_file()})
    if idx==1:continue
    ax=axs[0 if idx==0 else 1];tokens=[]
    for line in read(run/'grid_map.pgm').decode().splitlines(): tokens+=line.split('#',1)[0].split()
    assert tokens[0]=='P2';w,h,maxval=map(int,tokens[1:4]);grid=np.flipud(np.array(tokens[4:],dtype=float).reshape(h,w))
    lo,hi=meta['box_min'],meta['box_max'];ax.imshow(grid,origin='lower',extent=[lo[0],hi[0],lo[1],hi[1]],cmap='gray',vmin=0,vmax=maxval,interpolation='nearest')
    ax.plot(traj[:,1],traj[:,2],color='#cf4f27',lw=1.2,label='记录轨迹');ax.scatter(*traj[0,1:3],c='#13795b',s=35,marker='o',label='记录起点');ax.scatter(*traj[-1,1:3],c='#404ba0',s=45,marker='x',label='记录终点')
    ax.set(xlabel='x（m）',ylabel='y（m）',aspect='equal');ax.set_title(f"UAV{meta['drone_id']} 节点 baseline；n=1\n{run.name}\nPGM 栅格 {meta['grid_resolution']} m；XY 路径 {length:.2f} m",fontsize=9);ax.legend(loc='lower right',fontsize=7)
fig.suptitle('单机实机：各自规划坐标系内的轨迹与二维地图；不含跨机配准',fontsize=11)
save(fig,'fig05_single_real_maps');write(AUDIT/'real_metrics.json',real)

fig,axs=plt.subplots(1,3,figsize=(13,3.3))
for ax,name,unit in zip(axs,['三机对齐轨迹','三机融合地图','任务接管与结果统计'],['m','m','文本']):
    ax.axis('off');ax.add_patch(FancyBboxPatch((.03,.06),.94,.83,boxstyle='round,pad=0.01',transform=ax.transAxes,fill=False,ls='--',edgecolor='#82909b'))
    ax.text(.5,.74,name,ha='center',fontsize=12,transform=ax.transAxes)
    ax.text(.5,.42,f'[待填-{name}：{unit}；\nn=待补；场景=室内三机实机；\n数据来源=同步记录与评估；\nrun ID=待补]',ha='center',va='center',fontsize=9,linespacing=1.7,transform=ax.transAxes)
fig.suptitle('三机实机结果图位：数据缺失，未绘制轨迹、地图或统计值',fontsize=12);save(fig,'fig06_three_real_placeholder')
write(AUDIT/'input_hashes.json',HASHES)
for name,digest in HASHES.items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
print(json.dumps({'groups':stats,'real':real,'hashed_inputs':len(HASHES),'figures':6},ensure_ascii=False,indent=2))
