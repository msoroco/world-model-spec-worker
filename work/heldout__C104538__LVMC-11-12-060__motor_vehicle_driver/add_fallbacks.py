"""Add engineering alternatives shared across all linked station cases."""
import hashlib,json
from pathlib import Path

root=Path(__file__).resolve().parent
manifest_path=root/'execution-manifest.json'
manifest=json.loads(manifest_path.read_text())
variants=(
 ('fallback1',{'spawn_height_m':.45},
  'Native subject spawn and first original body pose',
  'subject spawn succeeds and body clears road surface',
  'Primary 0.3 m spawn offset collides with surveyed entrance geometry; 0.45 m clears the same station route.'),
 ('fallback2',{'waypoint_arrival_m':3.0},
  'original subject path and selected route waypoint history',
  'nearest distance to each mapped route waypoint in metres',
  'Primary 2.0 m radius misses the next waypoint under map tessellation; 3.0 m permits progression on the same route.'),
 ('fallback3',{'speed_gain':.18},
  'original subject speed history',
  'peak-to-peak speed tracking error in m/s',
  'Primary steering/speed control oscillates around requested speed; reduced gain stabilizes the same reversal path.'))
for entry in manifest['cases']:
    primary_path=root/entry['construction']
    construction=json.loads(primary_path.read_text())
    for file in construction['files']:
        if file['path'] in ('runner.py','fire_station_geometry.py','tests/test_station_runner_finalizer.py'):
            file['content']=(root/file['path']).read_text()
    primary_path.write_text(json.dumps(construction,indent=2)+'\n')
    entry['construction_sha256']=hashlib.sha256(primary_path.read_bytes()).hexdigest()
    for key in ('offline','compatibility','negative','post_capture'):
        entry.pop(key,None)
    entry['candidates']=[]
    config=json.loads(next(file['content'] for file in construction['files'] if file['path']=='config.json'))
    for ident,changes,source,metric,condition in variants:
        candidate=json.loads(json.dumps(construction))
        candidate['candidate_id']=ident
        for file in candidate['files']:
            if file['path']=='config.json':
                adjusted=json.loads(file['content']);adjusted.update(changes)
                file['content']=json.dumps(adjusted,indent=2)+'\n'
                file.pop('source',None)
        case_dir=root/'cases'/entry['case_id'].split('__')[-1]
        case_dir.mkdir(parents=True,exist_ok=True)
        path=case_dir/(ident+'-construction.json')
        path.write_text(json.dumps(candidate,indent=2)+'\n')
        entry['candidates'].append({'id':ident,
          'construction':str(path.relative_to(root)),
          'construction_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
          'trigger':{'source':source,'metric':metric,'failure_condition':condition},
          'changed_knobs':[k+': '+str(config.get(k,{'spawn_height_m':.3,
           'waypoint_arrival_m':2.0,'speed_gain':.22}[k]))+' to '+str(v)
           for k,v in changes.items()]})
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
print(len(manifest['cases']),'cases; 3 candidates each')
