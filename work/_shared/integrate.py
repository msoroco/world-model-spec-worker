"""Integrate reviewed partition contributions; never executes Native capture."""
import hashlib,json,shlex
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def read(p):return json.loads(p.read_text())
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def main():
 batch=read(ROOT/'batch.json');laws={};bindings=[];queue=[];comparisons=[]
 for p in sorted((ROOT/'work').glob('*/branch-contribution.json')):
  contribution=read(p)
  if 'laws' in contribution:
   additions=contribution['laws']
  else:additions={contribution['law_id']:{'branches':contribution['branches']}}
  for law,data in additions.items():
   laws.setdefault(law,{'branches':[]})['branches'].extend(data['branches'])
  bindings.extend(contribution.get('additional_bindings',[]))
 for path in sorted((ROOT/'work').glob('*/additional-bindings.json')):
  value=read(path);bindings.extend(value if isinstance(value,list) else value['additional_bindings'])
 unique={}
 for binding in bindings:
  aid=binding['assignment_id']
  if aid in unique and binding!=unique[aid]:raise ValueError('Conflicting binding '+aid)
  unique[aid]=binding
 bindings=list(unique.values())
 for law,data in laws.items():
  ids=[b['branch_id'] for b in data['branches']]
  if len(ids)!=len(set(ids)):raise ValueError('Duplicate branch identity '+law)
 matrix={'format':'worker-full-branch-coverage-v1','batch_id':batch['batch_id'],'additional_bindings':bindings,'laws':laws}
 write(ROOT/'work/_shared/branch-coverage.json',matrix)
 for p in sorted((ROOT/'work').glob('*/execution-manifest.json')):
  m=read(p);plan=read(p.parent/'case-plan.json')
  native_index={}
  for c in m['cases']:
   queue.append({'order':len(queue)+1,'assignment_id':m['assignment_id'],'case_id':c['case_id'],'capture_command':c.get('gpu_command'),'postprocessing_command':c.get('post_capture',{}).get('command')})
   post=c.get('post_capture',{}).get('command','')
   tokens=shlex.split(post)
   if '--attempt' in tokens:
    attempt=tokens[tokens.index('--attempt')+1];native_index[c['case_id']]={'analysis_report':attempt+'/analysis-report.json','config':attempt+'/config.json'}
    queue[-1]['additional_source_audit_command']='python3.11 work/_shared/source_audit.py --spec work/_shared/source-audit-specs.json --case '+c['case_id']+' --attempt '+attempt+' --output '+attempt+'/additional-source-audit.json'
  write(p.parent/'native-comparison-index.json',native_index)
  comparisons.extend({'assignment_id':m['assignment_id'],**c} for c in plan['comparisons'])
 write(ROOT/'work/_shared/gpu-queue.json',{'format':'worker-ordered-gpu-queue-v1','native_executed':0,'video_core_accepted':0,'comparison_complete':0,'cases':queue,'comparison_audit_commands':[{'assignment_id':c['assignment_id'],'comparison_id':c['comparison_id'],'command':'python3.11 work/_shared/comparison_audit.py --spec work/'+c['assignment_id']+'/comparison-audit-specs.json --comparison '+c['comparison_id']+' --index work/'+c['assignment_id']+'/native-comparison-index.json --output .runtime-work/'+c['assignment_id']+'/comparison-'+c['comparison_id']+'.json'} for c in comparisons]})
 first={}
 for case in queue:first.setdefault(case['assignment_id'],case['capture_command'])
 write(ROOT/'work/_shared/first-gpu-commands.json',first)
 uses={}
 for c in comparisons:
  for cid in c['case_ids']:uses[cid]=uses.get(cid,0)+1
 branches=[b for data in laws.values() for b in data['branches']]
 write(ROOT/'work/_shared/counts.json',{'laws':len(laws),'branches':len(branches),'runnable_branches':sum(b['status']=='runnable' for b in branches),'capability_blocked_branches':sum(b['status']=='capability_blocked' for b in branches),'comparisons':len(comparisons),'pending_branches':sum(b['status'] not in ('runnable','capability_blocked') for b in branches),'branch_case_memberships':sum(len(b.get('case_ids',[])) for b in branches),'planned_recordings':len(queue),'explicit_reuses':sum(max(0,n-1) for n in uses.values()),'recordings_reused':sum(n>1 for n in uses.values()),'native_executed':0,'video_core_accepted':0,'comparison_complete':0})
if __name__=='__main__':main()
