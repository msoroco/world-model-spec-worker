"""Bind each requested physical setpoint to measured original-source attainment."""
import json,hashlib
from pathlib import Path
r=Path(__file__).resolve().parent;p=r/'execution-manifest.json';m=json.loads(p.read_text());cases={x['case_id']:x for x in json.loads((r/'proposals/cases.json').read_text())['cases']}
for e in m['cases'][3:]:
 row=cases[e['case_id']];safety='safety' in e['case_id'];name='other_traffic_spacing' if safety else 'other_traffic_brake_start_frame';requested=row['sweep_point'][name];tol=1.0 if safety else 2.0
 for target in [e]+e['candidates']:
  path=r/target['construction'];d=json.loads(path.read_text());f=next(x for x in d['files'] if x['path']=='backing_finalizer.py');source=f['content']
  if "'target':'"+name+"'" not in source:
   marker="    context={'"+name+"':value}"
   insert=f'''    tolerance={tol!r}
    matched=abs(value-{requested!r})<=tolerance
    output['target_checks'].append({{'target':'{name}','requested':{requested!r},'measured':value,'method':'original joined backing_history.jsonl physical setpoint readback','tolerance':tolerance,'matched':matched,'physical_cause_confirmed':matched,'cause_evidence':'Original other-vehicle positions and speeds joined to frame identities; diagnostic fixtures do not claim real physical acceptance'}})
    output['physical_failure_flags']['sweep_target_missed']=not matched
'''
   if marker not in source:raise ValueError('Expected sweep context marker absent')
   source=source.replace(marker,insert+marker)
   f['content']=source
   if target is e:(r/'cases'/e['case_id'].rsplit('__',1)[-1]/'backing_finalizer.py').write_text(source)
   path.write_text(json.dumps(d,indent=2)+'\n');target['construction_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
   for key in ('offline','compatibility','saved_processing_test','post_capture','physical_preparation','delivery_acceptance'):target.pop(key,None)
p.write_text(json.dumps(m,indent=2)+'\n');print('bound original-source target attainment checks to all 24 new bundles')
