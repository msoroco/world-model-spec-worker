"""Materialize six exact Native control variants from frozen physical grids."""
from pathlib import Path
import json,hashlib,copy
r=Path(__file__).resolve().parent;repo=r.parents[1];proposal=json.loads((r/'proposals/cases.json').read_text());manifest_path=r/'execution-manifest.json';manifest=json.loads(manifest_path.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
oldids=[e['case_id'] for e in manifest['cases']]
selected=[x['case_id'] for x in proposal['cases'] if x['target_type']!='baseline']
for row in proposal['cases'][4:]:
 case=row['case_id'];slug=case.rsplit('__',1)[-1]
 if case in oldids:continue
 safety='safety' in slug
 base_entry=manifest['cases'][0] if safety else manifest['cases'][2]
 base_id=base_entry['case_id'];base_slug=base_id.rsplit('__',1)[-1]
 base=json.loads((r/base_entry['construction']).read_text())
 out=r/'cases'/slug;out.mkdir(parents=True,exist_ok=True)
 value=row['sweep_point']['other_traffic_spacing' if safety else 'other_traffic_brake_start_frame']
 for item in base['files']:
  content=item['content'].replace(base_id,case).replace('__'+base_slug,"__"+slug)
  if item['path']=='runner.py':
   if safety:
    content=content.replace('waypoint.previous(18.0)',f'waypoint.previous({value:.1f})')
    content=content.replace('No connected Native narrow-road 18 m reverse encounter',f'No connected Native narrow-road {value:g} m reverse encounter')
   else:content=content.replace('len(frames)<80',f'len(frames)<{int(value)}')
  if item['path']=='tests/test_runner.py' and safety:
   content=content.replace("self.assertEqual(scene['other'].transform.location.x,-18)",f"self.assertEqual(scene['other'].transform.location.x,-{int(value)})")
  if item['path']=='config.json':
   config=json.loads(content);config['selected_case_id']=case;config['case']={'case_id':case,'recording_description':row['recording_description']};config['supported_case_ids']=selected
   content=json.dumps(config,indent=2)+'\n'
  path=out/item['path'];path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
  item['content']=content;item['source']=str(path.relative_to(repo))
 base['case_id']=case;base['recording_description']=row['recording_description']
 construction=out/'construction.json';construction.write_text(json.dumps(base,indent=2)+'\n')
 diagnostic=json.loads((r/('diagnostic.json' if safety else 'cases/reverse_clear_traffic_brakes/diagnostic.json')).read_text())
 if safety:
  rows=[json.loads(line) for line in diagnostic['files']['backing_history.jsonl'].splitlines()]
  delta=12.0-value
  for h in rows:
   h['other']['position_m'][0]+=delta
   for vertex in h['other']['body_vertices_m']:vertex[0]+=delta
  diagnostic['files']['backing_history.jsonl']=''.join(json.dumps(x,separators=(',',':'))+'\n' for x in rows)
 diagnostic_text=json.dumps(diagnostic,indent=2)+'\n';(out/'diagnostic.json').write_text(diagnostic_text)
 recipe={'format':'worker-fixture-recipe','sources':[{'path':'diagnostic-input.json','source':str((out/'diagnostic.json').relative_to(repo)),'sha256':sha(out/'diagnostic.json')}],'generator':{'source':str((out/'diagnostic.json').relative_to(repo)),'sha256':sha(out/'diagnostic.json')}}
 (out/'diagnostic-recipe.json').write_text(json.dumps(recipe,indent=2)+'\n')
 contract=json.loads((r/base_entry['measurement_contract']).read_text());contract['case_id']=case;(out/'measurement-contract.json').write_text(json.dumps(contract,indent=2)+'\n')
 entry={'case_id':case,'kind':'delivery','construction':str(construction.relative_to(r)),'construction_sha256':sha(construction),
        'candidate_risk':{'status':'physical','reason':'Native route, reverse control, and original four-view visibility each need a measured fallback.'},'candidates':[],
        'measurement_contract':str((out/'measurement-contract.json').relative_to(r)),'measurement_procedure':{'entrypoint':'backing_finalizer.py'},
        'fixture_recipe':str((out/'diagnostic-recipe.json').relative_to(repo)),
        'native_handoff':{'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'}}
 for number in (1,2,3):
  variant=copy.deepcopy(base)
  if number==1:
   old=f'waypoint.previous({value:.1f})' if safety else 'waypoint.previous(18.0)'
   new=f'waypoint.previous({value-2:.1f})' if safety else 'waypoint.previous(16.0)'
   knob=f'rear actor spawn continuation {value:g} to {value-2:g} m' if safety else 'rear actor spawn continuation 18 to 16 m'
   trigger={'source':'Native waypoint selection diagnostic','metric':'connected rear continuation count','failure_condition':'Primary rear continuation unavailable at the exact requested distance'}
  elif number==2:
   old='throttle=.22,reverse=True';new='throttle=.14,reverse=True';knob='ego reverse throttle 0.22 to 0.14'
   trigger={'source':'original backing_history.jsonl','metric':'minimum actor-center separation','failure_condition':'Primary reverse control enters a 2 m engineering collision-risk band'}
  else:
   old='"approach": ((1.2, 0.0, 2.0)';new='"approach": ((1.8, 0.0, 2.4)';knob='approach camera mount forward and higher'
   trigger={'source':'full decoded original approach RGB','metric':'full subject and other vehicle body visibility','failure_condition':'Either vehicle body is omitted in an original frame'}
  target='backing_camera_capture.py' if number==3 else 'runner.py'
  found=next(f for f in variant['files'] if f['path']==target)
  if old not in found['content']:raise ValueError('Expected fallback knob changed: '+old)
  found['content']=found['content'].replace(old,new);found.pop('source',None)
  cand=out/f'fallback{number}-construction.json';cand.write_text(json.dumps(variant,indent=2)+'\n')
  entry['candidates'].append({'id':f'fallback{number}','construction':str(cand.relative_to(r)),'construction_sha256':sha(cand),'trigger':trigger,'changed_knobs':[knob]})
 manifest['cases'].append(entry)
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
print('built',len(manifest['cases'])-len(oldids),'exact judgment grid bundles plus three fallbacks each')
