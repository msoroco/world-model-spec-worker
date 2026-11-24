"""Assemble canonical assignment handoff from exact selected artifacts."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')

plan=json.loads((HERE/'case-plan.json').read_text())
selected=json.loads((HERE/'selected-v2-manifest.json').read_text())
case_ids=[item['case_id'] for item in plan['cases']]
recording=json.loads(json.dumps(plan['cases'][0]['recording_description']))
for observation in plan['observations']:
 term=observation['name']
 recording['channels'].append({'name':term,'unit':'source_evidence',
  'sampling_rate_hz':20,'method':'original Native actor, signal, map and synchronized camera source review',
  'time_window':'full 30 s / 600-frame attempt',
  'reference_frame':'original Native frame and source camera identity',
  'uncertainty':'Physical presence, arrow pixels, governance and lawful yielding remain unknown until original review'})
proposal={'cell_id':'C111603','actor':'motor_vehicle_driver','status':'draft','cases':plan['cases'],'sweep_specs':[]}
write(HERE/'proposals/cases.json',proposal)
first=json.loads((HERE/'v2-primary/witness_1/construction.json').read_text())
config=json.loads(next(f['content'] for f in first['files'] if f['path']=='config.json'))
config.update({'supported_case_ids':case_ids,'selected_case_id':case_ids[0],
 'case':{'case_id':case_ids[0]},'mandatory_channels':['native_actor_signal_samples'],
 'status':'selected_delivery_preparation','recording_description':recording})
for camera in config['cameras']:
 camera['pose_strategy']={'overview':'elevated intersection plan view',
 'approach':'south approach signal and stop line',
 'reference_corner':'crosswalk and other traffic corner',
 'driver_reference':'driver facing signal and intersection'}[camera['name']]
 camera['fov_deg']=80
write(HERE/'config.json',config)
construction={'case_id':case_ids[0],'cell_id':'C111603','law_id':'NRS-484B-307-9a',
 'actor':'motor_vehicle_driver','entrypoint':'runner.py',
 'files':[{'path':name,'content':(HERE/name).read_text()} for name in ('runner.py','config.json','tests/test_runner_assembly.py')],
 'recording_description':recording,
 'measurement_plan':{'source':'original Native actor and synchronized RGB frame identities',
   'output':'saved source-hashed motion and signal observations; human pixel/legal review remains open'},
 'static_checks':['selected case identity','OpenDRIVE signal head distinction','600 source frame joins'],
 'termination_rules':['finish after 600 synchronized source frames','abort on missing source or restoration failure'],
 'mechanisms':['source-pinned original CARLA capture','recorded-only CPU processing'],
 'status':'selected_delivery_preparation'}
write(HERE/'construction.json',construction)
manifest=dict(selected)
manifest['status']='selected_delivery_preparation'
for entry in manifest['cases']:
 entry['candidate_risk']={'status':'physical','reason':'Original arrow pixels, signal governance or full turn/yield visibility may fail review; alternate camera and hold plans preserve case scope.'}
 entry['native_handoff']={'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'}
write(HERE/'execution-manifest.json',manifest)
print(json.dumps({'execution_manifest_sha256':sha(HERE/'execution-manifest.json'),
 'root_construction_sha256':sha(HERE/'construction.json'),'config_sha256':sha(HERE/'config.json')}))
