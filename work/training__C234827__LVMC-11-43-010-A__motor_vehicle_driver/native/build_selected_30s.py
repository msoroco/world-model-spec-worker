"""Build exact selected source-bound rotary requests from retained 600-frame drafts."""
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
NATIVE=Path(__file__).resolve().parent
ASSIGNMENT=ROOT.name
CHANNELS={
 'st.roundabout':'Native rotary road and island map readback, original overview/reference pixels',
 'rel.occupies':'Original Native ego body footprint and lane IDs relative to island polygon',
 'kin.heading':'Original Native ego heading and velocity across all frames',
 'kin.position':'Original Native ego body pose and island-relative position across all frames',
 'kin.yaw_rate':'Original Native time-joined ego heading differences across consecutive frames',
 'drv.wrong_way':'Source-derived clockwise/counterclockwise observation, not a pinned Core ID',
 'native_body_pose_control':'Original Native body, velocity and applied control each frame',
 'camera_frame_join':'Four camera frames joined to original Native frame and time'}

def encode(value):return json.dumps(value,indent=2,ensure_ascii=False)+'\n'
def sha(value):return hashlib.sha256(value.encode()).hexdigest()

def build(index,candidate='primary'):
    old=json.loads((NATIVE/'30s'/f'witness_{index}'/'construction.json').read_text())
    files={item['path']:item['content'] for item in old['files']}
    config=json.loads(files['config.json'])
    config.update(format='c234827-rotary-delivery-v2',selected_case_id=old['case_id'],
                  supported_case_ids=[old['case_id']],candidate_id=candidate,
                  required_atoms=['rel.occupies','kin.heading','kin.position','kin.yaw_rate'],
                  source_packets=[],mandatory_channels=list(CHANNELS),
                  case={'case_id':old['case_id']},status='selected_native_runner_cpu_prepared',
                  native_execution_integrated=True,original_native_observed=False,
                  delivery_ready=False)
    config['cameras']=[{'name':name,'width':width,'height':height,'pose_strategy':mount,
                        'fov_deg':fov} for name,width,height,fov,_,mount in
                       [('overview',1920,1080,85,None,'world'),
                        ('approach',1280,720,80,None,'world'),
                        ('reference_corner',1280,720,85,None,'world'),
                        ('driver_reference',1280,720,90,None,'ego')]]
    config['road_sha256']=hashlib.sha256((NATIVE/'road_30s.xodr').read_bytes()).hexdigest()
    config['island_geometry_sha256']=hashlib.sha256((NATIVE/'island-geometry.json').read_bytes()).hexdigest()
    description={'channels':[{'name':key,'unit':'structured','sampling_rate_hz':20,
        'method':value,'time_window':'all original 600 Native frames / 30 s',
        'reference_frame':'original Native map and frame, distinct from authored request',
        'uncertainty':'50 ms sample interval and native pose/camera precision; no legal threshold inferred'}
        for key,value in CHANNELS.items()],
        'context_inputs':[{'name':'rotary_island_source','unit':'structured',
          'method':'source-hashed OpenDRIVE rotary road and island geometry plus original Native map readback'}],
        'limitations':['Authored path and CPU diagnostic do not prove original Native circulation',
                       'Physical island, traffic controls, route tracking, pixels and legal result require original Native source review']}
    config['recording_description']=description
    config['case']['recording_description']=description
    if candidate=='fallback1':
        # Lower speed reduces steering/traction demand while retaining the same
        # island lane, actor, observation window, cameras and comparison sign.
        sign=config['requested_rotation_sign'];speed=6.0;radius=23.75
        rows=[]
        for frame,line in enumerate(files['requested-tracks.jsonl'].splitlines()):
            row=json.loads(line);theta=-math.pi/2+sign*speed*(frame+1)/20/radius
            row.update(ego_x_m=round(radius*math.cos(theta),6),
                       ego_y_m=round(radius*math.sin(theta),6),
                       ego_heading_deg=round(math.degrees(theta+sign*math.pi/2)%360,6),
                       ego_speed_mps=speed,requested_unwrapped_angle_rad=round(theta,9))
            rows.append(json.dumps(row,sort_keys=True))
        files['requested-tracks.jsonl']='\n'.join(rows)+'\n'
        config['requested_speed_mps']=speed
    files={'runner.py':(NATIVE/'runner_30s.py').read_text(),
           'capture_30s.py':(NATIVE/'capture_30s.py').read_text(),
           'measure_saved_30s.py':(NATIVE/'measure_saved_30s.py').read_text(),
           'tests/test_capture_30s.py':(NATIVE/'test_capture_30s.py').read_text(),
           'tests/test_measure_saved_30s.py':(NATIVE/'test_measure_saved_30s.py').read_text(),
           'road.xodr':(NATIVE/'road_30s.xodr').read_text(),
           'island-geometry.json':(NATIVE/'island-geometry.json').read_text(),
           'assignment-source.json':files['assignment-source.json'],
           'requested-tracks.jsonl':files['requested-tracks.jsonl']}
    config['assignment_sha256']=sha(files['assignment-source.json'])
    config['tracks_sha256']=sha(files['requested-tracks.jsonl'])
    files['config.json']=encode(config)
    construction={'case_id':old['case_id'],'cell_id':'C234827','law_id':'LVMC-11-43-010-A',
        'actor':'motor_vehicle_driver','entrypoint':'runner.py',
        'files':[{'path':key,'content':value} for key,value in files.items()],
        'measurement_plan':{'method':'source-bound original Native 20 Hz body, lane, map and camera frame capture; saved-only rotation measurement','status':'cpu_prepared_original_native_unobserved'},
        'recording_description':description,
        'static_checks':['source hashes','600 consecutive source frames','signed continuous requested angle','four-camera contract','Native map lane readback'],
        'termination_rules':['retain complete 600 original frames','retain failure capture/report and world restoration'],
        'mechanisms':['OpenDRIVE two-lane rotary road','source-bound requested angular motion controller','four synchronized lossless cameras'],
        'status':'selected_cpu_construction'}
    path=ROOT/(f'selected-construction-witness_{index}.json' if candidate=='primary' else
                f'selected-candidates/witness_{index}/{candidate}/construction.json')
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(encode(construction))
    if candidate!='primary':
        return {'id':candidate,'construction':str(path.relative_to(ROOT)),
                'construction_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'trigger':{'source':'original Native body pose, control, lane readback and frame joins',
                           'metric':'sampled rotary-lane body clearance and continuous signed angular motion',
                           'failure_condition':'8 m/s primary leaves claimed rotary lane or reverses/interrupts signed progress'},
                'changed_knobs':['requested controller speed 8 m/s to 6 m/s; same 23.75 m lane-center radius']}
    contract={'format':'worker-measurement-contract','case_id':old['case_id'],
        'requirements':[{'disposition_index':0,'requirement':'LVMC-11-43-010-A',
            'source':'LVMC 11.43.010(A)','output_key':'rotation_observation',
            'method':'measure','value_type':'object','kind':'measured','inputs':list((
            'native-raw-actors.jsonl','native-map-readback.json','video_frames.jsonl',
            'trace.jsonl','capture/evidence.jsonl','capture/manifest.json'))}],
        'negative':{'remove':['native-raw-actors.jsonl'],
                    'error_contains':'Missing required source: native-raw-actors.jsonl'}}
    (ROOT/f'measurement-contract-witness_{index}.json').write_text(encode(contract))
    return {'case_id':old['case_id'],'kind':'delivery',
            'candidate_risk':{'status':'physical','reason':'Original Native rotary lane/turn tracking and four-camera framing may fail at target speed'},
            'measurement_contract':f'measurement-contract-witness_{index}.json',
            'measurement_procedure':{'entrypoint':'measure_saved_30s.py','output_schema':'c234827-rotary-saved-v1'},
            'candidates':[build(index,'fallback1')],'id':'primary','construction':path.name,
            'fixture_recipe':f'work/{ASSIGNMENT}/selected-recipe-witness_{index}.json',
            'construction_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

if __name__=='__main__':
    manifest={'format':'worker-execution-manifest','assignment_id':ASSIGNMENT,
              'runtime_manifest_sha256':hashlib.sha256((ROOT.parents[1]/'runtime/SOURCE-MANIFEST.json').read_bytes()).hexdigest(),
              'status':'diagnostic_selected_probe','cases':[build(1),build(2)]}
    (ROOT/'selected-probe-manifest.json').write_text(encode(manifest))
    print(json.dumps({'cases':[x['case_id'] for x in manifest['cases']]}))
