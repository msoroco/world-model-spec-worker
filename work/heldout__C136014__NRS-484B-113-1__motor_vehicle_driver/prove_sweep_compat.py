import json,hashlib,subprocess,sys,shutil
from pathlib import Path
r=Path(__file__).resolve().parent;repo=r.parents[1];p=r/'execution-manifest.json';m=json.loads(p.read_text());validator=repo/'.runtime-work/c136014-decoder/.lake/build/bin/adapterCheck'
sha=lambda q:hashlib.sha256(q.read_bytes()).hexdigest()
for e in m['cases'][3:]:
 slug=e['case_id'].rsplit('__',1)[-1];sub=r/'cases'/slug
 for candidate in ('primary','fallback1','fallback2','fallback3'):
  out=repo/'.runtime-work'/('c136014-'+slug+'-'+candidate+'-compat-005')
  cmd=[sys.executable,str(repo/'runtime.py'),'compatibility','--manifest',str(p),'--case',e['case_id']]
  if candidate!='primary':cmd+=['--candidate',candidate]
  cmd+=['--output',str(out),'--library',str(repo/'runtime/library'),'--validator',str(validator)]
  run=subprocess.run(cmd,cwd=repo,capture_output=True,text=True)
  command=sub/(candidate+'-compat-command.log');command.write_text(run.stdout+run.stderr)
  if run.returncode:raise ValueError(e['case_id']+' '+candidate+' compatibility failed: '+(run.stdout+run.stderr)[-2000:])
  receipt=sub/(candidate+'-compatibility.json');log=sub/(candidate+'-compat.log');negative=sub/(candidate+'-negative.log')
  shutil.copyfile(out/'compatibility.json',receipt);shutil.copyfile(out/'compatibility-analysis.log',log);shutil.copyfile(out/'negative-analysis.log',negative)
  target=e if candidate=='primary' else next(x for x in e['candidates'] if x['id']==candidate)
  target['compatibility']={'receipt':str(receipt.relative_to(r)),'sha256':sha(receipt),'log':str(log.relative_to(r)),'negative_log':str(negative.relative_to(r))}
  if candidate=='primary':target['negative']={'log':str(negative.relative_to(r))}
  print(slug,candidate,'compatibility passed',flush=True)
p.write_text(json.dumps(m,indent=2)+'\n')
