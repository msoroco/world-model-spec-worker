import json,hashlib,subprocess,sys,shutil
from pathlib import Path
r=Path(__file__).resolve().parent;repo=r.parents[1];p=r/'execution-manifest.json';m=json.loads(p.read_text())
sha=lambda q:hashlib.sha256(q.read_bytes()).hexdigest()
for e in m['cases'][3:]:
 slug=e['case_id'].rsplit('__',1)[-1]
 for candidate in ('primary','fallback1','fallback2','fallback3'):
  out=repo/'.runtime-work'/('c136014-'+slug+'-'+candidate+'-offline-005')
  cmd=[sys.executable,str(repo/'runtime.py'),'offline','--manifest',str(p),'--case',e['case_id']]
  if candidate!='primary':cmd+=['--candidate',candidate]
  cmd+=['--output',str(out),'--python',sys.executable]
  completed=subprocess.run(cmd,cwd=repo,capture_output=True,text=True)
  command_log=r/'cases'/slug/(candidate+'-offline-command.log');command_log.write_text(completed.stdout+completed.stderr)
  if completed.returncode:raise ValueError(e['case_id']+' '+candidate+' offline failed: '+completed.stdout[-1000:]+completed.stderr[-1000:])
  log=r/'cases'/slug/(candidate+'-offline.log');shutil.copyfile(out/'offline.log',log)
  target=e if candidate=='primary' else next(x for x in e['candidates'] if x['id']==candidate)
  display='.venv-cpu/bin/python runtime.py offline --manifest work/'+r.name+'/execution-manifest.json --case '+e['case_id']+(' --candidate '+candidate if candidate!='primary' else '')+' --output '+str(out.relative_to(repo))+' --python '+sys.executable
  target['offline']={'command':display,'exit_code':0,'log':str(log.relative_to(r)),'log_sha256':sha(log),'construction_sha256':target['construction_sha256']}
  print(slug,candidate,'offline passed',flush=True)
p.write_text(json.dumps(m,indent=2)+'\n')
