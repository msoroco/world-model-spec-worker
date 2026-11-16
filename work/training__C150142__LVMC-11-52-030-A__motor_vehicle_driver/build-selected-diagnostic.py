"""Build text-only, source-bound C150142 primary diagnostic fixture inputs.

The generated videos remain under .runtime-work; this spec is not Native evidence.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encode(value):
    return json.dumps(value,indent=2,allow_nan=False)+'\n'


def lines(rows):
    return ''.join(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n'
                   for row in rows)


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(encode(value))


def make(candidate='primary',witness='reference'):
    if candidate not in ('primary','fallback1','fallback2','fallback3'):
        raise ValueError('Unknown exact candidate')
    if witness not in ('reference','contrast'):
        raise ValueError('Unknown red-curb witness')
    case_id=ROOT.name+'__'+witness
    selected=ROOT/'selected-primary'/witness
    selected_path=(selected/'construction.json' if candidate=='primary' else
        ROOT/'selected-fallbacks'/witness/candidate/'construction.json')
    construction=json.loads(selected_path.read_text())
    bundle={item['path']:item['content'] for item in construction['files']}
    cfg=json.loads(bundle['config.json'])
    road_hash=hashlib.sha256(bundle['red-curb-road.xodr'].encode()).hexdigest()
    if cfg['road_sha256']!=road_hash or construction['case_id']!=case_id:
        raise ValueError('Selected diagnostic does not match construction')
    actor_rows=[];frames=[];trace=[];evidence=[];capture_frames=[];graphs=[]
    for i in range(240):
        approach=cfg['requested_approach_frames']
        distance=cfg['requested_target_x_m']-5
        x=5+distance*min(i,approach)/approach
        y=-6.8;t=i/20
        speed=distance*20/approach if i<approach else 0
        body_xy=[[x-1,y-.5],[x+1,y-.5],[x+1,y+.5],[x-1,y+.5]]
        body_xyz=[[a,b,z] for a,b in body_xy for z in (0,1.5)]
        actor_rows.append({'frame':i,'native_frame':i,'time_s':t,
            'source_kind':'synthetic_native_sample',
            'ego_center_native_xy_m':[x,y],
            'ego_body_native_xy_m':body_xy,
            'velocity_native_xyz_mps':[speed,0,0],
            'yaw_deg':0})
        frames.append({'video_frame':i,'native_frame':i,'carla_frame':i,
            'time_s':t,'views':['overview','approach','reference_corner','driver_reference'],
            'synthetic_frame_only':True})
        participant={'actor_id':1,'blueprint':'vehicle.tesla.model3',
            'position_m':[x,y,0],'heading_deg':0,
            'velocity_mps':[speed,0,0],'speed_mps':speed,
            'acceleration_mps2':[0,0,0],'accel_longitudinal_mps2':0,
            'body_vertices_m':body_xyz,
            'blueprint_attributes':{'role_name':'c150142_ego'},
            'light_attributes':{},'wheel_steer_angle_deg':0}
        observation={'frame':i,'time_s':t,'participants':[participant],
            'world_settings':{'no_rendering_mode':False},
            'rgb_sensors':{name:{'frame':i} for name in
                ('overview','approach','reference_corner','driver_reference')},
            'map_context':{'declared_public_way_road_ids':[150142],
                           'core_assumptions':[['asm.public_highway',True]]}}
        trace.append({'frame':i,'time_s':t,
            'position':{'x':x,'y':y,'z':0},
            'position_m':[x,y,0],'heading_deg':0,
            'speed_mps':speed,'speed_mph':speed*2.2369362921,
            'velocity_mps':[speed,0,0],
            'control':{'throttle':0,'brake':1 if i>=approach else 0,
                       'hand_brake':False}})
        evidence.append({'original_frame':i,'replay_frame':i,
            'actor_id':1,'recording_time_s':t,'replay_simulation_time_s':t,
            'ego':{'position_m':[x,y,0],'heading_deg':0,
                   'speed_mps':speed,'speed_provenance':'synthetic_native_sample',
                   'body_vertices_m':body_xyz},
            'world':{'weather':{'cloudiness':0,'precipitation':0,
                   'wetness':0,'fog_density':0},
                   'road_projection':{'road_id':150142,'section_id':0,
                       'lane_id':-2,'s_m':x}},
            'original_observations':observation})
        graph_path=f'graphs/base/{i:08d}.pkl'
        capture_frames.append({'frame':i,'time_s':t,'simulation_time':t,
                               'base':graph_path})
        graphs.append({'path':'capture/native/'+graph_path,
            'attributes':{'frame':i,'observed_evidence':observation},
            'nodes':[],'edges':[]})
    files={
        'road.xodr':bundle['red-curb-road.xodr'],
        'statutory-context.json':encode({
            'assignment_id':json.loads(bundle['assignment-source.json'])['assignment_id'],
            'law_id':cfg['law_id'],
            'law_text_sha256':hashlib.sha256(json.loads(bundle['assignment-source.json'])['law']['text'].encode()).hexdigest(),
            'law_text':json.loads(bundle['assignment-source.json'])['law']['text']}),
        'native-raw-actors.jsonl':lines(actor_rows),
        'video_frames.jsonl':lines(frames),
        'trace.jsonl':lines(trace),
        'native-map-readback.json':encode({
            'source_kind':'synthetic_native_sample','road_sha256':road_hash,
            'native_map_sha256':'a'*64,'road_id':150142,
            'parking_lane_id':-2,'paint_color':'red',
            'red_curb_start_x_m':30,'red_curb_end_x_m':50,
            'curb_y_m':-7,'legal_verdict':None}),
        'native-capture-report.json':encode({
            'case_id':case_id,'candidate_id':candidate,
            'config_sha256':hashlib.sha256(bundle['config.json'].encode()).hexdigest(),
            'requested_frames':240,'observed_frames':240,
            'error':None,'accepted':False,'legal_verdict':None}),
        'capture/evidence.jsonl':lines(evidence),
        'capture/native/frames.jsonl':lines(capture_frames),
        'capture/recorder_info.txt':'Synthetic CPU diagnostic; CARLA recorder did not run.\nCreate 1: vehicle.tesla.model3\n',
        'acquisition-provenance.json':encode({'provenance_kind':'synthetic_fixture',
            'diagnostic_fixture':True,'native_executed':False})}
    files['capture/manifest.json']=encode({'extraction_confirmed':True,
        'frames':240,'acquisition':'synthetic_cpu_fixture',
        'observation_contract_version':2,'required_observations':[],
        'sources':{'road.xodr':road_hash,
                   'trace.jsonl':hashlib.sha256(files['trace.jsonl'].encode()).hexdigest()}})
    videos=[{'path':name+'.mkv','frames':240,'width':width,'height':height,
             'fps':20,'color':color} for name,width,height,color in
            [('overview',1920,1080,'red'),('approach',1280,720,'green'),
             ('reference_corner',1280,720,'white'),
             ('driver_reference',1280,720,'blue')]]
    spec={'files':files,'graphs':graphs,'videos':videos}
    spec_path=ROOT/'selected-diagnostics'/witness/(candidate+'.json')
    write(spec_path,spec)
    rel=spec_path.relative_to(REPO).as_posix()
    recipe={'format':'worker-fixture-recipe',
            'sources':[{'path':'diagnostic-source.json','source':rel,
                        'sha256':sha(spec_path)}],
            'generator':{'source':rel,'sha256':sha(spec_path)}}
    recipe_path=ROOT/'selected-diagnostics'/witness/(candidate+'-recipe.json')
    write(recipe_path,recipe)
    proposal={'case_id':case_id,'target_law_id':'LVMC-11-52-030-A',
        'target_type':'attempt',
        'rationale':('Ordinary vehicle observed stopped at painted red curb' if witness=='reference'
                     else 'Ordinary vehicle observed stopped beyond painted red curb')+
                     '; legal exceptions require separate cases.',
        'variable_assignments':{
            'road_and_actors':{'kind':'world_setup','value':'authored red-curb OpenDRIVE with one ordinary ego'},
            'requested_parking_x_m':{'kind':'controller','value':cfg['requested_target_x_m'],'unit':'m'},
            'red_curb_stop_or_park':{'kind':'subject_behavior','value':None}},
        'recording_description':construction['recording_description'],
        'unresolved_judgment_calls':['Signed and public-service exceptions require separate source review']}
    write(selected/'proposals/cases.json',{'cell_id':'C150142',
        'actor':'motor_vehicle_driver','status':'draft','cases':[proposal]})
    manifest_path=selected/'draft-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    if candidate=='primary':
        manifest['cases'][0]['fixture_recipe']=recipe_path.relative_to(REPO).as_posix()
        write(manifest_path,manifest)
    root_manifest=json.loads(encode(manifest))
    root_manifest['cases'][0]['construction']='selected-primary/'+witness+'/construction.json'
    root_manifest['cases'][0]['measurement_contract']=\
        'selected-primary/'+witness+'/selected-measurement-contracts/'+witness+'.json'
    root_manifest['cases'][0]['fixture_recipe']=recipe_path.relative_to(REPO).as_posix()
    root_name=('execution-manifest-diagnostic-'+witness+'.json' if candidate=='primary'
               else 'execution-manifest-diagnostic-'+witness+'-'+candidate+'.json')
    write(ROOT/root_name,root_manifest)
    shared=ROOT/'proposals/cases.json'
    existing=json.loads(shared.read_text())['cases'] if shared.is_file() else []
    cases=[item for item in existing if item['case_id']!=case_id]+[proposal]
    write(shared,{'cell_id':'C150142','actor':'motor_vehicle_driver',
                  'status':'draft','cases':sorted(cases,key=lambda item:item['case_id'])})
    return {'case_id':case_id,'spec_bytes':spec_path.stat().st_size,
            'spec_sha256':sha(spec_path),'recipe_sha256':sha(recipe_path),
            'construction_sha256':sha(selected_path)}


if __name__=='__main__':print(json.dumps(make(
    sys.argv[1] if len(sys.argv)>1 else 'primary',
    sys.argv[2] if len(sys.argv)>2 else 'reference'),sort_keys=True))
