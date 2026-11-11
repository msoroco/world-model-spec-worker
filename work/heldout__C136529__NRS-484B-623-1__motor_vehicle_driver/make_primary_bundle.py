"""Regenerate the first exact inline bundle from local checked text sources."""
import hashlib
import json
from pathlib import Path

root=Path(__file__).resolve().parent
repo=root.parents[1]
assignment=root.name
case_id=assignment+'__slow_with_following_traffic'
recording_description={'channels':[
 {'name':'ego_speed_mps','unit':'m/s','method':'Native subject velocity vector magnitude',
  'sampling_rate_hz':20,'time_window':'all original frames','reference_frame':'world ground plane',
  'uncertainty':'Native velocity precision and 20 Hz temporal sampling'},
 {'name':'follower_speed_mps','unit':'m/s','method':'Native following vehicle velocity vector magnitude',
  'sampling_rate_hz':20,'time_window':'all original frames','reference_frame':'world ground plane',
  'uncertainty':'Native velocity precision and 20 Hz temporal sampling'},
 {'name':'follower_gap_m','unit':'m','method':'Native actor-center ground-plane separation; full body gap separately requires footprint capture',
  'sampling_rate_hz':20,'time_window':'all original frames','reference_frame':'world ground plane',
  'uncertainty':'Actor-center distance is a descriptive traffic proxy, not full body separation'}],
 'context_inputs':[],
 'limitations':['Normal and reasonable movement remains a legal judgment; actual traffic impedance and camera visibility need physical review.']}
config={'cell_id':'C136529','law_id':'NRS-484B-623-1','actor':'motor_vehicle_driver',
 'selected_case_id':case_id,'supported_case_ids':[assignment+'__'+x for x in (
  'flowing_reference','slow_with_following_traffic','slow_for_obstruction','slow_under_control')],
 'ego_target_mps':3.0,'follower_cruise_mps':8.0,'case_branch':'slow_with_following_traffic',
 'route_step_m':5.0,'follower_gain':0.4,'speed_kp':0.22,'speed_brake_gain':0.3,
 'required_atoms':[],'source_packets':[],'rate_hz':20,'duration_s':8,'frames':160,
 'cameras':[{'name':name,'width':size[0],'height':size[1],'pose_strategy':'subject-mounted original RGB source','fov_deg':fov}
            for name,(_,_,size,fov) in __import__('slow_camera_capture').CAMERAS.items()],
 'case':{'case_id':case_id,'recording_description':recording_description}}
(root/'config.json').write_text(json.dumps(config,indent=2)+'\n')
paths=['runner.py','slow_route.py','slow_camera_capture.py','slow_capture_session.py',
       'slow_finalizer.py','slow_speed.py','config.json',
       'tests/test_runner.py','tests/test_slow_route.py']
files=[{'path':path,'source':str((root/path).relative_to(repo)),
        'content':(root/path).read_text()} for path in paths]
construction={'format':'worker-inline-construction','case_id':case_id,
 'cell_id':'C136529','law_id':'NRS-484B-623-1','actor':'motor_vehicle_driver',
 'entrypoint':'runner.py','files':files,
 'measurement_plan':{'finalizer':'slow_finalizer.py','retained_sources':[
   'video_frames.jsonl','trace.jsonl','participant_state.jsonl','prop_state.jsonl','slow_context.json'],
   'reported_boundary':'original 20 Hz speed and following-gap history; no legal cutoff'},
 'recording_description':recording_description,
 'static_checks':['runner --check','materialized CPU route and runner tests'],
 'termination_rules':['160 original 20 Hz frames','reject missing synchronized camera/source frame'],
 'mechanisms':['Native narrow two-direction route selection','three actor feedback control',
               'four original RGB sources','saved-only slow traffic measurement']}
(root/'construction.json').write_text(json.dumps(construction,indent=2,ensure_ascii=False)+'\n')
digest=hashlib.sha256((root/'construction.json').read_bytes()).hexdigest()
manifest={'format':'worker-execution-manifest','assignment_id':assignment,
 'runtime_manifest_sha256':hashlib.sha256((repo/'runtime/SOURCE-MANIFEST.json').read_bytes()).hexdigest(),
 'cases':[{'case_id':case_id,'kind':'delivery','construction':'construction.json','construction_sha256':digest,
           'measurement_procedure':{'entrypoint':'slow_finalizer.py'},
           'candidate_risk':{'status':'physical','reason':'Narrow map lane and follower dynamics may fail to realize sustained measured traffic interaction'},
           'candidates':[], 'native_handoff':{'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'}}]}
(root/'cases').mkdir(exist_ok=True)
variants=[('fallback1',{'route_step_m':2.5},
           'Native route selector reports no uniquely connected narrow road at 5 m samples',
           'number of valid 160 m narrow two-direction route chains',
           'Primary 5 m sampling finds no verified connected route; 2.5 m resolves map tessellation.'),
          ('fallback2',{'follower_gain':0.3},
           'Original participant state reports follower gap oscillation',
           'peak-to-peak measured following gap in metres over original frames',
           'Primary follower gain produces sustained gap oscillation outside predeclared engineering control band.'),
          ('fallback3',{'speed_kp':0.18,'speed_brake_gain':0.25},
           'Original participant state reports subject speed tracking instability',
           'peak-to-peak ego speed in metres per second over original frames',
           'Primary speed gains produce sustained oscillation outside predeclared engineering tracking band.')]
for ident,changes,source,metric,condition in variants:
    alternative=json.loads(json.dumps(construction))
    alternative['candidate_id']=ident
    for item in alternative['files']:
        if item['path']=='config.json':
            adjusted=json.loads(item['content']);adjusted.update(changes)
            item['content']=json.dumps(adjusted,indent=2)+'\n'
            item.pop('source',None)
    rel='cases/'+ident+'-construction.json'
    path=root/rel
    path.write_text(json.dumps(alternative,indent=2,ensure_ascii=False)+'\n')
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    manifest['cases'][0]['candidates'].append({'id':ident,'construction':rel,
      'construction_sha256':digest,
      'trigger':{'source':source,'metric':metric,'failure_condition':condition},
      'changed_knobs':[key+': '+str(config[key])+' to '+str(value) for key,value in changes.items()]})
(root/'execution-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(digest)
