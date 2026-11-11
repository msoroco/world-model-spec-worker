"""Bind each sweep axis to an independently derived retained-source context."""
import json,hashlib,copy
from pathlib import Path
r=Path(__file__).resolve().parent;p=r/'proposals';m_path=r/'execution-manifest.json';m=json.loads(m_path.read_text());proposal=json.loads((p/'cases.json').read_text());template=json.loads((p/'template.json').read_text());bindings=json.loads((p/'bindings.json').read_text())
for spec in proposal['sweep_specs']:
 axis=spec['axes'][0];safety='safety' in spec['sweep_id'];name=axis['observable']
 method='original first-frame actor-center separation' if safety else 'original first traffic deceleration frame'
 axis['measurement']={'method':method,'time_window':'all original backing frames','statistic':'first'}
 description=spec['recording_description'];context={'name':name,'unit':axis['unit'],'method':'Derived from original joined backing_history.jsonl after capture'}
 if name not in [x['name'] for x in description['context_inputs']]:description['context_inputs'].append(context)
 spec.pop('spec_version',None);spec.pop('planned_case_count',None);spec.pop('selection_order',None)
# Drop six expanded records and regenerate exact sweep metadata while retaining IDs.
proposal['cases']=proposal['cases'][:4];proposal.pop('sweeps_expanded',None)
import sys
sys.path.insert(0,str(r.parents[1]/'runtime/scenario_pipeline'))
from batch_pipeline.sweeps import expand_sweeps
expand_sweeps(proposal,[template],bindings)
case_by_id={x['case_id']:x for x in proposal['cases']}
for e in m['cases'][3:]:
 row=case_by_id[e['case_id']];safety='safety' in e['case_id'];name='other_traffic_spacing' if safety else 'other_traffic_brake_start_frame';unit='m' if safety else 'frame';method='original first-frame actor-center separation' if safety else 'original first traffic deceleration frame'
 file=r/e['construction'];construction=json.loads(file.read_text());slug=e['case_id'].rsplit('__',1)[-1];out=r/'cases'/slug
 original=next(x for x in construction['files'] if x['path']=='backing_finalizer.py')['content']
 if 'def _base_result(root,report):' not in original:
  original=original.replace('def result(root,report):','def _base_result(root,report):')
  wrapper=f'''def result(root,report):
    output=_base_result(root,report)
    observations=report['measurements']['reverse_encounter']['value']['observations']
    if {safety!r}:
        value=observations[0]['center_distance_m']
    else:
        decline=next((i for i in range(1,len(observations)) if observations[i]['other_speed_mps'] < observations[i-1]['other_speed_mps']-0.05),None)
        if decline is None:raise ValueError('Original other-traffic deceleration onset absent')
        value=float(decline)
    context={{'{name}':value}}
    (Path(root)/'sweep_context.json').write_text(json.dumps(context)+'\\n')
    output['recording_evidence'].append({{'name':'{name}','unit':'{unit}','reference':'sweep_context.json'}})
    output['realized_observables']['{name}']={{'value':value,'unit':'{unit}','method':'{method}','time_window':'all original backing frames','statistic':'first','reference':'sweep_context.json'}}
    return output

'''
  original=original.replace('def main():',wrapper+'def main():')
 (out/'backing_finalizer.py').write_text(original)
 construction['recording_description']=row['recording_description']
 for item in construction['files']:
  if item['path']=='backing_finalizer.py':item['content']=original
  if item['path']=='config.json':
   cfg=json.loads(item['content']);cfg['case']['recording_description']=row['recording_description'];item['content']=json.dumps(cfg,indent=2)+'\n';(out/'config.json').write_text(item['content'])
 file.write_text(json.dumps(construction,indent=2)+'\n');e['construction_sha256']=hashlib.sha256(file.read_bytes()).hexdigest();e.pop('offline',None)
 for cand in e['candidates']:
  path=r/cand['construction'];variant=json.loads(path.read_text());variant['recording_description']=row['recording_description']
  for item in variant['files']:
   if item['path']=='backing_finalizer.py':item['content']=original
   if item['path']=='config.json':item['content']=next(x['content'] for x in construction['files'] if x['path']=='config.json')
  path.write_text(json.dumps(variant,indent=2)+'\n');cand['construction_sha256']=hashlib.sha256(path.read_bytes()).hexdigest();cand.pop('offline',None)
(p/'cases.json').write_text(json.dumps(proposal,indent=2)+'\n')
index=json.loads((p/'semantic-index.json').read_text())
for refs in index['stages'].values():
 for ref in refs if isinstance(refs,list) else [refs]:ref['sha256']=hashlib.sha256((r/ref['path']).read_bytes()).hexdigest()
(p/'semantic-index.json').write_text(json.dumps(index,indent=2)+'\n');m_path.write_text(json.dumps(m,indent=2)+'\n')
print('sweep context sources bound to six exact bundles; old offline proofs cleared')
