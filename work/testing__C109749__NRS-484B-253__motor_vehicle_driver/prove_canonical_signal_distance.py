"""Bind exact CPU proofs for the selected 25 m and 36 m signal probes."""
import hashlib,json,shlex,shutil,subprocess
from pathlib import Path
F=Path(__file__).resolve().parent
R=F.parent.parent
M=F/'execution-manifest.json'
PYTHON=str(R/'.venv-cpu/bin/python')
LIB='runtime/library'
VALIDATOR='.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(manifest):M.write_text(json.dumps(manifest,indent=2)+'\n')
def run(cmd,log):
 p=F/log;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('w') as out:subprocess.run(cmd,cwd=R,stdout=out,stderr=subprocess.STDOUT,check=True,timeout=300)
 return sha(p)
def main():
 m=json.loads(M.read_text()); entries=[e for e in m['cases'] if e['case_id'].endswith(('__signal_advance_100_below_25','__signal_advance_100_above_36'))]
 assert len(entries)==2
 for e in entries:
  label='below' if e['signal_target_m']==25 else 'above'
  for item in [e,*e['candidates']]:
   ident=item.get('id','primary'); stem=f'cases/signal_advance_100_{"below_25" if label=="below" else "above_36"}/canonical-proofs/{ident}'
   assert sha(F/item['construction'])==item['construction_sha256']
   output=f'.runtime-work/c109749-canonical-{label}-{ident}-offline-v1'
   cmd=[PYTHON,'runtime.py','offline','--manifest',str(M.relative_to(R)),'--case',e['case_id'],'--output',output]
   if ident!='primary':cmd+=['--candidate',ident]
   log=f'{stem}/offline.log';digest=run(cmd,log)
   receipt=json.loads((R/output/'receipt.json').read_text()) if (R/output/'receipt.json').exists() else None
   item['offline']={'command':shlex.join(cmd),'exit_code':0,'log':log,'log_sha256':digest,'construction_sha256':item['construction_sha256']}
   print('offline',label,ident,flush=True)
 write(m)
 for e in entries:
  label='below' if e['signal_target_m']==25 else 'above'
  for item in [e,*e['candidates']]:
   ident=item.get('id','primary'); stem=f'cases/signal_advance_100_{"below_25" if label=="below" else "above_36"}/canonical-proofs/{ident}'
   compat=f'.runtime-work/c109749-canonical-{label}-{ident}-compat-v1';saved=f'.runtime-work/c109749-canonical-{label}-{ident}-saved-v1'
   cmd=[PYTHON,'runtime.py','compatibility','--manifest',str(M.relative_to(R)),'--case',e['case_id'],'--output',compat,'--library',LIB,'--validator',VALIDATOR]
   if ident!='primary':cmd+=['--candidate',ident]
   replay=f'{stem}/replay.log';run(cmd,replay)
   for src,dst in [('compatibility.json','compatibility.json'),('analysis.log','analysis.log'),('negative-analysis.log','negative-analysis.log')]:
    p=F/stem/dst;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(R/compat/src,p)
   rec=json.loads((F/stem/'compatibility.json').read_text())
   assert rec['passed'] is True and rec['candidate_id']==ident and rec['construction_sha256']==item['construction_sha256']
   assert b'Missing required source: interaction_history.jsonl' in (F/stem/'negative-analysis.log').read_bytes()
   item['compatibility']={'receipt':f'{stem}/compatibility.json','sha256':sha(F/stem/'compatibility.json'),'log':f'{stem}/analysis.log','negative_log':f'{stem}/negative-analysis.log','replay_command':shlex.join(cmd),'replay_log':replay}
   item['negative']={'log':f'{stem}/negative-analysis.log'}
   cmd=[PYTHON,'runtime.py','process-saved','--manifest',str(M.relative_to(R)),'--case',e['case_id'],'--attempt',compat,'--output',saved,'--library',LIB,'--validator',VALIDATOR]
   savedlog=f'{stem}/saved.log';digest=run(cmd,savedlog)
   saved_receipt=json.loads((R/saved/'v0001/processing.json').read_text())
   assert saved_receipt['recorded_only'] is True and saved_receipt['originals_preserved'] is True
   item['post_capture']={'recorded_only':True,'command':shlex.join(cmd),'feedback_command':f'cat {saved}/v0001/feedback.json','test_log':savedlog,'test_log_sha256':digest,'test_exit_code':0}
   print('compatibility and saved',label,ident,flush=True)
  write(m)
 print(json.dumps({'selected_cases':len(m['cases']),'canonical_signal_distance_paths':8,'native_or_legal_acceptance_claimed':False}))
if __name__=='__main__':main()
