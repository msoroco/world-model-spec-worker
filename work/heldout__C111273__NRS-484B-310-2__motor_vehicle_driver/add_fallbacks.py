"""Bind three physical-risk engineering alternatives to each exact signal case."""
import hashlib
import json
from pathlib import Path

root=Path(__file__).resolve().parent
manifest_path=root/'execution-manifest.json'
manifest=json.loads(manifest_path.read_text())
variants=(
 ('fallback1',{'approach_before_m':60.0},
  'Native governed-lane waypoint selection',
  'unique route availability at 70 m before governed head',
  'Primary 70 m approach lacks a unique prior waypoint; 60 m maintains the same governed lane and turn context.'),
 ('fallback2',{'spawn_z_offset_m':.35},
  'Native actor spawn result and original first body pose',
  'successful subject and crossing actor creation with body above road',
  'Primary ground-level spawn collides with map geometry; a 0.35 m height adjustment permits the same lane actors.'),
 ('fallback3',{'speed_kp':.18},
  'original participant speed history',
  'peak-to-peak approach speed tracking error in m/s',
  'Primary gain causes persistent approach speed oscillation; lower gain stabilizes the same requested case speed.'))
for entry in manifest['cases']:
    primary_path=root/entry['construction']
    construction=json.loads(primary_path.read_text())
    for file in construction['files']:
        if file['path'] in ('runner.py','native_signal.py','tests/test_runner.py','tests/test_native_signal.py'):
            file['content']=(root/file['path']).read_text()
    primary_path.write_text(json.dumps(construction,indent=2)+'\n')
    entry['construction_sha256']=hashlib.sha256(primary_path.read_bytes()).hexdigest()
    for key in ('offline','compatibility','negative','post_capture'):
        entry.pop(key,None)
    entry['candidates']=[]
    primary_config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
    for ident,knobs,source,metric,condition in variants:
        candidate=json.loads(json.dumps(construction))
        candidate['candidate_id']=ident
        for file in candidate['files']:
            if file['path']=='config.json':
                config=json.loads(file['content'])
                config.update(knobs)
                file['content']=json.dumps(config,indent=2)+'\n'
                file.pop('source',None)
        case_dir=root/'cases'/entry['case_id'].split('__')[-1]
        case_dir.mkdir(parents=True,exist_ok=True)
        path=case_dir/(ident+'-construction.json')
        path.write_text(json.dumps(candidate,indent=2)+'\n')
        entry['candidates'].append({'id':ident,
            'construction':str(path.relative_to(root)),
            'construction_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'trigger':{'source':source,'metric':metric,'failure_condition':condition},
            'changed_knobs':[k+': '+str(primary_config.get(k,{'approach_before_m':70.0,
                'spawn_z_offset_m':0.0,'speed_kp':.22}[k]))+' to '+str(v) for k,v in knobs.items()]})
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
print(len(manifest['cases']),'cases; 3 candidates each')
