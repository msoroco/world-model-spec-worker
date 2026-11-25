"""Build source-shaped synthetic 600-frame diagnostics, never Native evidence."""
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
NATIVE=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
def encode(obj):return json.dumps(obj,ensure_ascii=False,sort_keys=True)+'\n'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    if isinstance(rows,list):path.write_text(''.join(encode(row) for row in rows))
    else:path.write_text(encode(rows))

def build(index):
    source=ROOT/'selected-source'/f'witness_{index}'
    source.mkdir(parents=True,exist_ok=True)
    draft=json.loads((NATIVE/'30s'/f'witness_{index}'/'construction.json').read_text())
    src={item['path']:item['content'] for item in draft['files']}
    requested=[json.loads(s) for s in src['requested-tracks.jsonl'].splitlines()]
    sign=requested[0]['requested_rotation_sign'];native=[];trace=[];mapping=[];evidence=[];native_frames=[]
    for i,row in enumerate(requested):
        x=row['ego_x_m'];y=row['ego_y_m'];h=row['ego_heading_deg'];rad=math.radians(h)
        body=[]
        for dx in (-2.3,2.3):
            for dy in (-.95,.95):
                for dz in (0,1.5):body.append([x+dx*math.cos(rad)-dy*math.sin(rad),
                                               y+dx*math.sin(rad)+dy*math.cos(rad),dz])
        f=100+i;t=row['time_s'];velocity=[8*math.cos(rad),8*math.sin(rad),0]
        ego={'actor_id':42,'blueprint':'vehicle.tesla.model3','center_native_xyz_m':[x,y,.5],
             'yaw_deg':h,'velocity_native_xyz_mps':velocity,'speed_mps':8,
             'body_native_xyz_m':body}
        native.append({'frame':i,'native_frame':f,'time_s':t,'source_kind':'synthetic_cpu',
                       'witness':f'witness_{index}','candidate_id':'primary',
                       'requested_lane_id':-1,'observed_road_id':1,'observed_lane_id':-1,
                       'ego':ego,'physical_roundabout_verified':False,
                       'traffic_control_verified':False,'legal_verdict':None})
        trace.append({'frame':f,'time_s':t,'position':{'x':x,'y':y,'z':.5},
                      'position_m':[x,y,.5],'heading_deg':h,'speed_mps':8,
                      'speed_mph':8/.44704,'velocity_mps':velocity,
                      'control':{'throttle':0,'brake':0,'hand_brake':False}})
        mapping.append({'video_frame':i,'native_frame':f,'carla_frame':f,'time_s':t})
        evidence.append({'original_frame':f,'recording_time_s':t,
            'ego':{'body_vertices_m':body,'position_m':[x,y,.5],
                   'heading_deg':h,'speed_mps':8,
                   'speed_provenance':'synthetic_native_sample'},
            'replay_frame':f,'replay_simulation_time_s':t,'actor_id':42,
            'world':{'weather':{'cloudiness':0,'precipitation':0,'wetness':0,'fog_density':0},
                     'road_projection':{'road_id':1,'section_id':0,'lane_id':-1,
                                        's_m':(i+1)*.4}}})
        native_frames.append({'frame':f,'simulation_time':t,'time_s':t,
            'adapter_graph':f'graphs/base/{f:08d}.adapter.json',
            'synthetic_diagnostic':True})
    write(source/'native-raw-actors.jsonl',native)
    write(source/'trace.jsonl',trace)
    write(source/'video_frames.jsonl',mapping)
    write(source/'capture/evidence.jsonl',evidence)
    write(source/'capture/native/frames.jsonl',native_frames)
    (source/'capture/recorder_info.txt').write_text('Create 42: vehicle.tesla.model3 synthetic diagnostic\n')
    write(source/'native-map-readback.json',{'road_sha256':hashlib.sha256((NATIVE/'road_30s.xodr').read_bytes()).hexdigest(),
        'island_geometry_sha256':hashlib.sha256((NATIVE/'island-geometry.json').read_bytes()).hexdigest(),
        'native_map_sha256':hashlib.sha256(b'synthetic rotary diagnostic map').hexdigest(),
        'arc_lane_readback':{'-1':{'road_id':1,'lane_id':-1},'-2':{'road_id':1,'lane_id':-2}},
        'source_kind':'synthetic_cpu','physical_roundabout_verified':False,
        'traffic_control_verified':False,'legal_verdict':None})
    write(source/'context.json',{'rotary_island_source':{'kind':'synthetic_cpu',
        'island_center_xy_m':[0,0],'island_radius_m':15,
        'road_sha256':hashlib.sha256((NATIVE/'road_30s.xodr').read_bytes()).hexdigest(),
        'physical_roundabout_verified':False}})
    write(source/'capture/manifest.json',{'extraction_confirmed':True,'frames':600,
        'sources':{'road.xodr':hashlib.sha256((NATIVE/'road_30s.xodr').read_bytes()).hexdigest(),
                   'trace.jsonl':sha(source/'trace.jsonl')},'synthetic_diagnostic':True})
    graphs=[{'path':f'capture/native/graphs/base/{f:08d}.adapter.json',
             'attributes':{'frame':f},'nodes':[],'edges':[]} for f in range(100,700)]
    videos=[{'path':name+'.mkv','frames':600,'width':width,'height':height,'fps':20,
             'color':'black' if index==1 else 'blue'} for name,width,height in
            [('overview',1920,1080),('approach',1280,720),
             ('reference_corner',1280,720),('driver_reference',1280,720)]]
    generator={'files':{},'graphs':graphs,'videos':videos}
    generator_path=ROOT/f'selected-generator-witness_{index}.json';generator_path.write_text(json.dumps(generator,indent=2)+'\n')
    sources=[]
    for path in sorted(source.rglob('*')):
        if path.is_file():sources.append({'path':str(path.relative_to(source)),
            'source':str(path.relative_to(REPO)),'sha256':sha(path)})
    recipe={'format':'worker-fixture-recipe','sources':sources,
        'generator':{'source':str(generator_path.relative_to(REPO)),
                     'sha256':sha(generator_path)}}
    recipe_path=ROOT/f'selected-recipe-witness_{index}.json';recipe_path.write_text(json.dumps(recipe,indent=2)+'\n')
    return recipe_path
if __name__=='__main__':
    for index in (1,2):print(build(index))
