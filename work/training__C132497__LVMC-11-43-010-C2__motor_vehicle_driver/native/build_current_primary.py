"""Build one source-bound current-runtime C132497 primary diagnostic package."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
CASE = ROOT.name+'__reference'
SOURCE = ROOT/'current-runtime-drafts/reference/primary/construction.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False)+'\n' for row in rows)


def body(x, y, heading):
    angle = math.radians(heading)
    forward = (math.cos(angle), math.sin(angle))
    left = (-forward[1], forward[0])
    return [[x+a*forward[0]+b*left[0], y+a*forward[1]+b*left[1], z]
            for a in (-2.0, 2.0) for b in (-.9, .9) for z in (-.7, .7)]


def diagnostic(construction, case_id=CASE, candidate_id='primary'):
    files = {item['path']: item['content'] for item in construction['files']}
    cfg = json.loads(files['config.json'])
    requests = [json.loads(row) for row in files['requested-tracks.jsonl'].splitlines()]
    if len(requests) != 240:
        raise ValueError('Primary request has wrong frame count')
    traces, mappings, actors, evidence, native_frames, graphs = [], [], [], [], [], []
    for i, request in enumerate(requests):
        t = i/20
        x, y, heading = (request['ego_x_m'], request['ego_y_m'], request['ego_heading_deg'])
        speed = request['ego_speed_mps']
        vertices = body(x, y, heading)
        vx = speed*math.cos(math.radians(heading))
        vy = speed*math.sin(math.radians(heading))
        trace = {'frame':i,'time_s':t,'position':{'x':x,'y':y,'z':0},
                 'position_m':[x,y,0], 'heading_deg':heading, 'speed_mps':speed,
                 'speed_mph':speed*2.2369362921,'velocity_mps':[vx,vy,0],
                 'control':{'throttle':0.0,'brake':0.0,'hand_brake':False}}
        traces.append(trace)
        mappings.append({'carla_frame':i,'native_frame':i,'synthetic_frame_only':True,
                         'time_s':t,'video_frame':i})
        ego = {'actor_id':10,'blueprint':'vehicle.tesla.model3',
               'center_native_xyz_m':[x,y,0], 'yaw_deg':heading,
               'velocity_native_xyz_mps':[vx,vy,0], 'speed_mps':speed,
               'body_native_xyz_m':vertices}
        actors.append({'frame':i,'native_frame':i,'time_s':t,
                       'source_kind':'synthetic_native_sample',
                       'requested_phase':request['phase'],
                       'requested_road_id':request['road_id'],
                       'requested_lane_id':request['lane_id'],
                       'observed_road_id':request['road_id'],
                       'observed_lane_id':request['lane_id'],
                       'ego':ego, 'physical_roundabout_verified':False,
                       'actual_right_exit_verified':False,'legal_verdict':None})
        observations = {'frame':i,'time_s':t,'participants':[{
            'actor_id':10,'blueprint':'vehicle.tesla.model3',
            'body_vertices_m':vertices, 'heading_deg':heading,
            'velocity_mps':[vx,vy,0], 'speed_mps':speed,
            'accel_longitudinal_mps2':0.0}],
            'world_settings':{'no_rendering_mode':False},
            'rgb_sensors':{'overview':{'frame':i}}}
        evidence.append({'original_frame':i,'replay_frame':i,'actor_id':10,
            'recording_time_s':t,'replay_simulation_time_s':t,
            'ego':{'position_m':[x,y,0],'heading_deg':heading,'speed_mps':speed,
                   'speed_provenance':'synthetic_native_sample',
                   'body_vertices_m':vertices},
            'world':{'weather':{'cloudiness':0,'precipitation':0,'wetness':0,
                                'fog_density':0},
                     'road_projection':{'road_id':request['road_id'],
                                        'section_id':0,'lane_id':request['lane_id'],
                                        's_m':float(i)/20}},
            'original_observations':observations})
        graph = f'capture/native/graphs/base/{i:08d}.pkl'
        native_frames.append({'frame':i,'time_s':t,'simulation_time':t,
                              'base':f'graphs/base/{i:08d}.pkl'})
        graphs.append({'path':graph,'attributes':{'frame':i,
                       'observed_evidence':observations},'nodes':[],'edges':[]})
    trace_text = lines(traces)
    manifest = {'extraction_confirmed':True,'frames':240,
                'acquisition':'synthetic_cpu_fixture','observation_contract_version':2,
                'required_observations':['kin.position','kin.heading',
                                         'st.intersection','rel.occupies'],
                'sources':{'road.xodr':hashlib.sha256(files['road.xodr'].encode()).hexdigest(),
                           'trace.jsonl':hashlib.sha256(trace_text.encode()).hexdigest()}}
    spec = {'files':{'trace.jsonl':trace_text,
                     'video_frames.jsonl':lines(mappings),
                     'native-raw-actors.jsonl':lines(actors),
                     'capture/evidence.jsonl':lines(evidence),
                     'capture/native/frames.jsonl':lines(native_frames),
                     'capture/recorder_info.txt':'Create 10: vehicle.tesla.model3\n',
                     'acquisition-provenance.json':json.dumps({
                         'provenance_kind':'synthetic_fixture',
                         'diagnostic_fixture':True,'native_executed':False})+'\n',
                     'capture/manifest.json':json.dumps(manifest,indent=2)+'\n'},
            'graphs':graphs,
            'videos':[{'path':name+'.mkv','frames':240,'width':width,'height':height,
                       'fps':20,'color':color}
                      for name,width,height,color in (
                          ('overview',1920,1080,'blue'),('approach',1280,720,'green'),
                          ('reference_corner',1280,720,'white'),
                          ('driver_reference',1280,720,'red'))]}
    if len(json.dumps(spec)) > 2_000_000:
        raise ValueError('Diagnostic specification too large')
    suffix = case_id.rsplit('__', 1)[-1]
    prefix = f'update015-current-{suffix}-{candidate_id}'
    spec_path = ROOT/(prefix+'-diagnostic.json')
    write(spec_path,spec)
    declaration = ROOT/(prefix+'-source.json')
    write(declaration,{'case_id':case_id,'candidate_id':candidate_id,
                       'source_kind':'synthetic_native_sample',
                       'accepted_original':False})
    recipe = {'format':'worker-fixture-recipe',
              'sources':[{'path':'diagnostic-source.json',
                          'source':declaration.relative_to(REPO).as_posix(),
                          'sha256':sha(declaration)}],
              'generator':{'source':spec_path.relative_to(REPO).as_posix(),
                           'sha256':sha(spec_path)}}
    recipe_path = ROOT/(prefix+'-recipe.json')
    write(recipe_path,recipe)
    return recipe_path, spec_path


def build():
    batch = json.loads((REPO/'batch.json').read_text())
    plan = json.loads((ROOT/'case-plan.json').read_text())
    construction = json.loads(SOURCE.read_text())
    files = construction['files']
    cfg = json.loads(next(item['content'] for item in files if item['path']=='config.json'))
    cfg.update({'selected_case_id':CASE,'duration_s':12,'required_atoms':[],
                'source_packets':[], 'cameras':['overview','approach',
                'reference_corner','driver_reference'], 'case':{'case_id':CASE},
                'physical_success_claimed':False})
    next(item for item in files if item['path']=='config.json')['content'] = json.dumps(cfg,indent=2)+'\n'
    road = next(item['content'] for item in files if item['path']=='right-exit-road.xodr')
    files.extend([{'path':'road.xodr','content':road},
                  {'path':'finalize_current.py',
                   'content':(ROOT/'native/finalize_current.py').read_text()}])
    channels = [{'name':name,'unit':unit,'sampling_rate_hz':20,
                 'method':'retained Native actor/frame join','time_window':'240 frames',
                 'reference_frame':'authored OpenDRIVE coordinates',
                 'uncertainty':'50 ms frame bracket; physical lane/exit unverified'}
                for name,unit in (('ego_pose','structured'),('ego_speed','m/s'),
                                  ('right_lane_exit','bool'))]
    recording = {'channels':channels,'context_inputs':[
        {'name':'authored_road','unit':'structured','method':'source-hashed OpenDRIVE'},
        {'name':'predeclared_intention','unit':'structured',
         'method':'controller intention hashed before motion'}],
        'limitations':['Native lane allocation, actual right exit, pixels and legal status unverified']}
    construction['recording_description'] = recording
    construction['static_checks'] = ['240-frame source-bound request identity',
                                      'retained actor/trace/video frame join']
    construction['termination_rules'] = ['retain original acquisition',
                                          'require 240 synchronized frames']
    construction['mechanisms'] = ['counterclockwise two-lane roundabout request',
                                   'four synchronized source cameras']
    target = ROOT/'native/package-current/reference/primary/construction.json'
    write(target,construction)
    names = ('roundabout_context','declared_right_exit','right_lane_exit')
    methods = ('measure_roundabout_context','measure_declared_right_exit',
               'measure_right_lane_exit')
    types = ('object','boolean','boolean')
    requirements = [{'disposition_index':i,'requirement':row['requirement'],
                     'source':row['source'],'output_key':name,'method':method,
                     'value_type':typ,'kind':'measured',
                     'inputs':['native-raw-actors.jsonl']}
                    for i,(row,name,method,typ) in enumerate(zip(
                        plan['requirement_dispositions'],names,methods,types))]
    contract = {'format':'worker-measurement-contract','case_id':CASE,
                'requirements':requirements,
                'negative':{'remove':['native-raw-actors.jsonl'],
                            'error_contains':'Missing required source: native-raw-actors.jsonl'},
                'uncertainty':{'frame_bracket_s':.05,
                               'physical_and_legal_status':'unverified'}}
    write(ROOT/'native/measurement-contracts-current/reference.json',contract)
    diagnostic(construction)
    entry = {'case_id':CASE,'kind':'draft_not_selected',
             'construction':target.relative_to(ROOT).as_posix(),
             'construction_sha256':sha(target),
             'measurement_contract':'native/measurement-contracts-current/reference.json',
             'measurement_procedure':{'entrypoint':'finalize_current.py',
                                      'output_schema':'c132497-current-saved-diagnostic-v1'},
             'fixture_recipe':(ROOT/'update015-current-reference-primary-recipe.json').relative_to(REPO).as_posix(),
             'candidate_risk':{'status':'physical',
                 'reason':'Native road connectivity, governed right lane, actual exit and pixels unverified'}}
    manifest = {'format':'worker-unselected-current-runtime-primary-v1',
                'assignment_id':ROOT.name,'status':'draft_not_selected',
                'runtime_manifest_sha256':batch['runtime']['source_manifest_sha256'],
                'source_branch':'roundabout_right_exit','cases':[entry],
                'original_native_observed':False,'delivery_ready':False}
    write(ROOT/'draft-current-primary-manifest.json',manifest)
    write(ROOT/'proposals/cases.json',{'cell_id':'C132497','actor':'motor_vehicle_driver',
          'status':'unselected_cpu_draft','cases':[{'case_id':CASE,
          'target_law_id':'LVMC-11-43-010-C2','target_type':'attempt',
          'recording_description':recording}]})
    return {'manifest_sha256':sha(ROOT/'draft-current-primary-manifest.json'),
            'construction_sha256':sha(target),
            'diagnostic_sha256':sha(ROOT/'update015-current-reference-primary-diagnostic.json')}


if __name__ == '__main__':
    print(json.dumps(build(),sort_keys=True))
