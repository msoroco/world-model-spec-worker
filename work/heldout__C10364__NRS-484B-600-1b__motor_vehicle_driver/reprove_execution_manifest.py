from pathlib import Path
import json,hashlib,subprocess,sys,shutil
R=Path.cwd();W=R/'work/heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver';M=W/'execution-manifest.json';J=json.loads(M.read_text());V=R/'.runtime-work/c125714-validator/.lake/build/bin/adapterCheck'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(args):
 p=subprocess.run(args,cwd=R,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 if p.returncode:raise ValueError('FAILED '+repr(args)+'\n'+p.stdout[-4000:])
 return p.stdout
for entry in J['cases']:
 suffix=entry['case_id'].split('__')[-1]
 for ident,sel in [('primary',entry),*[(x['id'],x) for x in entry['candidates']]]:
  tag=suffix+'-'+ident;out=R/'.runtime-work/c10364-return-reproof'/tag
  args=[sys.executable,str(R/'runtime.py'),'offline','--manifest',str(M),'--case',entry['case_id'],'--candidate',ident,'--output',str(out/'offline'),'--python',sys.executable]
  log=W/'cases'/f'case-offline-{tag}.log';log.write_text(run(args));sel['offline'].update(command=' '.join(args),log_sha256=sha(log))
  args=[sys.executable,str(R/'runtime.py'),'compatibility','--manifest',str(M),'--case',entry['case_id'],'--candidate',ident,'--output',str(out/'compat'),'--library',str(R/'runtime/library'),'--validator',str(V)]
  run(args);src=out/'compat';spec=sel['compatibility']
  for name,dst in [('compatibility.json',spec['receipt']),('compatibility-analysis.log',spec['log']),('negative-analysis.log',spec['negative_log'])]:shutil.copy2(src/name,W/dst)
  spec['sha256']=sha(W/spec['receipt'])
  receipt=json.loads((W/spec['receipt']).read_text());assert receipt['construction_sha256']==sel['construction_sha256'] and receipt['log_sha256']==sha(W/spec['log']) and receipt['negative_log_sha256']==sha(W/spec['negative_log'])
  print('PASS',tag,flush=True)
M.write_text(json.dumps(J,indent=2)+'\n')
print('ALL 36 exact returned-manifest offline + positive/negative compatibility pass',sha(M),flush=True)
