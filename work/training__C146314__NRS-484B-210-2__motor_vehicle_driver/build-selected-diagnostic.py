"""Source-hashed four-camera synthetic fixture for the first selected case."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
sys.path.insert(0,str(ROOT/'native'))
from prove_capture_measure import fixture


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def lines(rows):return ''.join(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n' for row in rows)
def encode(value):return json.dumps(value,indent=2,allow_nan=False)+'\n'
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(encode(value))


def build():
    construction=json.loads((ROOT/'selected-primary/reference/construction.json').read_text())
    bundle={x['path']:x['content'] for x in construction['files']}
    cfg=json.loads(bundle['config.json'])
    track=[json.loads(x) for x in bundle['requested-tracks.jsonl'].splitlines()]
    actors,frames=fixture(track)
    for i,(row,frame) in enumerate(zip(actors,frames)):
        row['native_frame']=i
        frame.update(native_frame=i,carla_frame=i,synthetic_frame_only=True)
    source_hash=hashlib.sha256(bundle['right-pass-road.xodr'].encode()).hexdigest()
    map_readback={'source_kind':'synthetic_native_sample',
        'road_sha256':source_hash,'native_map_sha256':'a'*64,
        'driving_lane_readback':{str(n):{'road_id':210,'lane_id':n} for n in (-1,-2)},
        'ego_actor_id':1,'lead_actor_id':2,'legal_verdict':None}
    report={'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
        'config_sha256':hashlib.sha256(bundle['config.json'].encode()).hexdigest(),
        'requested_frames':240,'observed_frames':240,
        'error':None,'accepted':False,'delivery_ready':False,
        'legal_safety_verdict':None}
    trace=[];evidence=[];capture_frames=[];graphs=[]
    for i,row in enumerate(actors):
        ego,lead=row['ego'],row['lead'];t=row['time_s']
        center=ego['center_native_xyz_m'];speed=ego['speed_mps']
        participants=[{'actor_id':actor['actor_id'],
            'blueprint':actor['blueprint'],'body_vertices_m':actor['body_native_xyz_m'],
            'heading_deg':actor['yaw_deg'],
            'velocity_mps':actor['velocity_native_xyz_mps'],
            'speed_mps':actor['speed_mps'],'accel_longitudinal_mps2':0.0}
            for actor in (ego,lead)]
        observation={'frame':i,'time_s':t,'participants':participants,
            'world_settings':{'no_rendering_mode':False},
            'rgb_sensors':{name:{'frame':i} for name in
                ('overview','approach','reference_corner','driver_reference')}}
        trace.append({'frame':i,'time_s':t,
            'position':dict(zip(('x','y','z'),center)),
            'position_m':center,'heading_deg':ego['yaw_deg'],
            'speed_mps':speed,'speed_mph':speed*2.2369362921,
            'velocity_mps':ego['velocity_native_xyz_mps'],
            'control':{'throttle':0.0,'brake':0.0,'hand_brake':False}})
        evidence.append({'original_frame':i,'replay_frame':i,
            'actor_id':ego['actor_id'],'recording_time_s':t,
            'replay_simulation_time_s':t,
            'ego':{'position_m':center,'heading_deg':ego['yaw_deg'],
                'speed_mps':speed,'speed_provenance':'synthetic_native_sample',
                'body_vertices_m':ego['body_native_xyz_m']},
            'world':{'weather':{'cloudiness':0,'precipitation':0,
                'wetness':0,'fog_density':0},
                'road_projection':{'road_id':210,'section_id':0,
                    'lane_id':row['observed_ego_lane_id'],'s_m':max(0,center[0])}},
            'original_observations':observation})
        graph=f'graphs/base/{i:08d}.pkl'
        capture_frames.append({'frame':i,'time_s':t,
                               'simulation_time':t,'base':graph})
        graphs.append({'path':'capture/native/'+graph,
            'attributes':{'frame':i,'observed_evidence':observation},
            'nodes':[],'edges':[]})
    files={
        'road.xodr':bundle['right-pass-road.xodr'],
        'native-raw-actors.jsonl':lines(actors),
        'video_frames.jsonl':lines(frames),
        'trace.jsonl':lines(trace),
        'native-map-readback.json':encode(map_readback),
        'native-capture-report.json':encode(report),
        'capture/evidence.jsonl':lines(evidence),
        'capture/native/frames.jsonl':lines(capture_frames),
        'capture/recorder_info.txt':'Synthetic CPU diagnostic; CARLA recorder did not run.\nCreate 1: vehicle.tesla.model3\nCreate 2: vehicle.tesla.model3\n',
        'acquisition-provenance.json':encode({'provenance_kind':'synthetic_fixture',
            'diagnostic_fixture':True,'native_executed':False})}
    files['capture/manifest.json']=encode({'extraction_confirmed':True,
        'frames':240,'acquisition':'synthetic_cpu_fixture',
        'observation_contract_version':2,
        'required_observations':['kin.position','kin.heading','rel.surface_gap'],
        'sources':{'road.xodr':source_hash,
                   'trace.jsonl':hashlib.sha256(files['trace.jsonl'].encode()).hexdigest()}})
    videos=[{'path':name+'.mkv','frames':240,
        'width':1920 if name=='overview' else 1280,
        'height':1080 if name=='overview' else 720,
        'fps':20,'color':color} for name,color in
        (('overview','blue'),('approach','green'),
         ('reference_corner','white'),('driver_reference','red'))]
    spec={'files':files,'graphs':graphs,'videos':videos}
    path=ROOT/'selected-diagnostics/reference/primary.json'
    write(path,spec)
    relative=path.relative_to(REPO).as_posix()
    recipe={'format':'worker-fixture-recipe',
        'sources':[{'path':'diagnostic-source.json','source':relative,'sha256':sha(path)}],
        'generator':{'source':relative,'sha256':sha(path)}}
    recipe_path=ROOT/'selected-diagnostics/reference/primary-recipe.json'
    write(recipe_path,recipe)
    manifest_path=ROOT/'selected-primary/reference/draft-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    manifest['cases'][0]['fixture_recipe']='work/'+ROOT.name+'/selected-diagnostics/reference/primary-recipe.json'
    write(manifest_path,manifest)
    return {'spec_sha256':sha(path),'recipe_sha256':sha(recipe_path),
            'spec_bytes':path.stat().st_size,'construction_sha256':sha(ROOT/'selected-primary/reference/construction.json')}


if __name__=='__main__':print(json.dumps(build(),sort_keys=True))
