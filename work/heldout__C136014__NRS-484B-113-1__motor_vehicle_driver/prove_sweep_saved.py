import json,hashlib,subprocess,sys
from pathlib import Path
r=Path(__file__).resolve().parent;repo=r.parents[1];p=r/'execution-manifest.json';m=json.loads(p.read_text());validator=repo/'.runtime-work/c136014-decoder/.lake/build/bin/adapterCheck'
sha=lambda q:hashlib.sha256(q.read_bytes()).hexdigest()
for e in m['cases'][3:]:
 slug=e['case_id'].rsplit('__',1)[-1];sub=r/'cases'/slug
 for candidate in ('primary','fallback1','fallback2','fallback3'):
  log=sub/(candidate+'-saved-proof.log')
  cmd=[sys.executable,str(r/'prove_saved.py'),'--manifest',str(p),'--validator',str(validator),'--case',e['case_id'],'--candidate',candidate]
  result=subprocess.run(cmd,cwd=repo,capture_output=True,text=True)
  log.write_text(result.stdout+result.stderr)
  if result.returncode:raise ValueError(e['case_id']+' '+candidate+' saved failed: '+(result.stdout+result.stderr)[-2000:])
  proof=json.loads(log.read_text());assert proof['positive_saved_processing'] and proof['negative_missing_source_rejected']
  if candidate=='primary':
   e['post_capture']={'recorded_only':True,'command':f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{r.name}/execution-manifest.json --case {e["case_id"]} --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $VALIDATOR','feedback_command':'cat $OUTPUT/v0001/feedback.json','test_log':str(log.relative_to(r)),'test_log_sha256':sha(log),'test_exit_code':0}
  else:
   c=next(x for x in e['candidates'] if x['id']==candidate)
   c['saved_processing_test']={'command':f'.venv-cpu/bin/python work/{r.name}/prove_saved.py --manifest work/{r.name}/execution-manifest.json --validator $VALIDATOR --case {e["case_id"]} --candidate {candidate}','exit_code':0,'log':str(log.relative_to(r)),'log_sha256':sha(log)}
  print(slug,candidate,'saved passed',flush=True)
p.write_text(json.dumps(m,indent=2)+'\n')
