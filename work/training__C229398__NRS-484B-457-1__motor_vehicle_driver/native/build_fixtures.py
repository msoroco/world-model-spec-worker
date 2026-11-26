"""Write permanent textual CPU fixtures; generated media stays in .runtime-work."""
import hashlib
import json
import math
from pathlib import Path
import sys

PKG=Path(__file__).resolve().parents[1]
NATIVE=Path(__file__).resolve().parent
sys.path.insert(0,str(PKG))
from parking_scene import CASES,request
from prove_parking_branches import fixture

CAMERAS=('overview','approach','reference_corner','driver_reference')
VIDEOS=[{'path':name+'.mkv','frames':600,'width':1920 if name=='overview' else 1280,
         'height':1080 if name=='overview' else 720,'fps':20,'color':'black'} for name in CAMERAS]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(value)


def lines(values):return ''.join(json.dumps(row,sort_keys=True,allow_nan=False)+'\n' for row in values)


def build(suffix):
    kind,gap,angle,rest_mode=CASES[suffix]
    req=request(suffix)
    context,metric_rows=fixture(kind,gap,angle)
    context['source_kind']='synthetic_native_sample'
    context['diagnostic_fixture']=True
    context['case_id']=PKG.name+'__'+suffix
    folder=NATIVE/'diagnostic'/suffix
    folder.mkdir(parents=True,exist_ok=True)
    put(folder/'parking-context.json',json.dumps(context,indent=2)+'\n')
    center=req['requested_center_xy_m']
    start=req['approach_start_xy_m']
    motion=[];frame_map=[];trace=[];evidence=[];graphs=[];native_frames=[]
    for i,row in enumerate(metric_rows):
        fraction=min(i,240)/240
        x=start[0]+(center[0]-start[0])*fraction
        y=start[1]+(center[1]-start[1])*fraction
        speed=1 if i<240 else 0
        cosine=math.cos(math.radians(angle));sine=math.sin(math.radians(angle))
        body=[[x+dx*cosine-dy*sine,y+dx*sine+dy*cosine,z]
              for dx in (-2,2) for dy in (-1,1) for z in (0,1.5)]
        shift=y-center[1]
        ego={'center_xyz_m':[x,y,1.5],'yaw_deg':angle,'speed_mps':speed,
             'stopped_or_parked':i>=240,'body_xyz_m':body,
             'right_front_wheel_outer_y_m':row['right_front_wheel_outer_y_m']+shift,
             'right_rear_wheel_outer_y_m':row['right_rear_wheel_outer_y_m']+shift,
             'left_front_wheel_outer_y_m':row['left_front_wheel_outer_y_m']+shift,
             'left_rear_wheel_outer_y_m':row['left_rear_wheel_outer_y_m']+shift}
        motion.append({'native_frame':i,'video_frame':i,'time_s':i/20,
                       'source_kind':'synthetic_native_sample','ego':ego,
                       'rest_mode_request':rest_mode,'legal_verdict':None})
        frame_map.append({'video_frame':i,'native_frame':i,'carla_frame':i,'time_s':i/20,
                          'camera_native_frames':{name:i for name in CAMERAS}})
        trace.append({'frame':i,'time_s':i/20,'position':{'x':x,'y':y,'z':1.5},
                      'position_m':[x,y,1.5],'velocity_mps':[speed,0,0],
                      'speed_mps':speed,'speed_mph':speed*2.2369362921,
                      'heading_deg':angle,'control':{},'source_kind':'synthetic_native_sample'})
        evidence.append({'replay_frame':i,'original_frame':i,'recording_time_s':i/20,
            'replay_simulation_time_s':i/20,'actor_id':10,'ego':{
                'position_m':[x,y,1.5],'heading_deg':angle,'speed_mps':speed,
                'body_vertices_m':body,'synthetic_diagnostic':True,
                'speed_provenance':'synthetic_native_sample'},'other_actors':[],
            'world':{'road_projection':{'road_id':229398,'lane_id':-3 if kind!='left_ordinance' else 1,
                                       'section_id':0,'s_m':x+80},
                     'weather':{'cloudiness':0,'fog_density':0,'precipitation':0,'wetness':0}}})
        name=f'capture/native/graphs/base/{i:08d}.adapter.json'
        native_frames.append({'frame':i,'simulation_time':i/20,'nodes':1,'edges':0,
                              'base':f'graphs/base/{i:08d}.adapter.json',
                              'adapter_graph':f'graphs/base/{i:08d}.adapter.json'})
        graphs.append({'path':name,'attributes':{'frame':i,'simulation_time_s':i/20,
                    'synthetic_diagnostic':True},'edges':[],
                    'nodes':[{'id':'ego','attributes':{'entity_id':10,'sem_class':'ego',
                    'vertex':[x,y,1.5],'forward':[1,0,0],
                    'threedbbox':body}}]})
    for name,rows in (('native-parking.jsonl',motion),('video_frames.jsonl',frame_map),
                      ('trace.jsonl',trace),('capture/evidence.jsonl',evidence)):
        put(folder/name,lines(rows))
    manifest={'extraction_confirmed':True,'frames':600,'synthetic_diagnostic':True,
              'sources':{'road.xodr':hashlib.sha256(req['source_map'].encode()).hexdigest(),
                         'trace.jsonl':sha(folder/'trace.jsonl')}}
    put(folder/'capture/manifest.json',json.dumps(manifest,sort_keys=True)+'\n')
    spec={'files':{'capture/native/frames.jsonl':lines(native_frames),
                   'capture/recorder_info.txt':'Synthetic C229398 CPU diagnostic; no CARLA recorder\nCreate 10: vehicle.tesla.model3 (0)\n'},
          'graphs':graphs,'videos':VIDEOS}
    spec_path=NATIVE/f'diagnostic-{suffix}-fixture-spec.json'
    put(spec_path,json.dumps(spec,separators=(',',':'))+'\n')
    sources=[]
    for name in ('parking-context.json','native-parking.jsonl','video_frames.jsonl',
                 'trace.jsonl','capture/evidence.jsonl','capture/manifest.json'):
        path=folder/name
        sources.append({'path':name,'source':str(path.relative_to(Path.cwd())),
                        'sha256':sha(path)})
    recipe={'format':'worker-fixture-recipe',
            'generator':{'source':str(spec_path.relative_to(Path.cwd())),
                         'sha256':sha(spec_path)},'sources':sources}
    recipe_path=NATIVE/f'diagnostic-{suffix}-fixture-recipe.json'
    put(recipe_path,json.dumps(recipe,indent=2)+'\n')
    return {'case':suffix,'spec_bytes':spec_path.stat().st_size,
            'recipe':str(recipe_path.relative_to(PKG))}


if __name__=='__main__':print(json.dumps([build(s) for s in CASES],indent=2))
