"""Create 600-frame source-shaped diagnostics, never Native evidence."""
import hashlib
import json
from pathlib import Path

from native.geometry import open_drive

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
ASSIGNMENT=HERE.name
CAMERAS=('overview','approach','reference_corner','driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(folder,name,content):
    path=folder/name
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(content if content.endswith('\n') else content+'\n')


def rows(values):
    return '\n'.join(json.dumps(v,allow_nan=False,separators=(',',':')) for v in values)+'\n'


def box(x,y):
    return [[x-2,y-.8],[x+2,y-.8],[x+2,y+.8],[x-2,y+.8]]


def build(suffix,conflict):
    folder=HERE/'selected-source'/suffix
    folder.mkdir(parents=True,exist_ok=True)
    road=open_drive()
    road_hash=hashlib.sha256((road+'\n').encode()).hexdigest()
    authority_hash=hashlib.sha256(b'synthetic diagnostic authority only').hexdigest()
    context={'assignment_id':ASSIGNMENT,'source_kind':'synthetic_native_sample',
             'road_id':'1','map_source_sha256':road_hash,
             'highway_boundary_source_sha256':road_hash,
             'highway_dedication_source_sha256':authority_hash,
             'public_access_source_sha256':authority_hash,
             'curb_permission_source_sha256':authority_hash,
             'parking_purpose_source_sha256':authority_hash,
             'state':'Nevada','public_highway':True,'parking_permitted':True,
             'initial_status':'parked_no_loading','synthetic_diagnostic':True}
    departure,mapping,core,evidence,graph_frames,graphs=[],[],[],[],[],[]
    for i in range(600):
        frame,time=100+i,i/20
        elapsed=max(0,i-150)
        x=.1*elapsed
        y=-5+min(1,elapsed/50)*3.25
        tx=(-50+i*.3) if conflict else (30+i*.25)
        ts=6 if not conflict or i<180 else 3
        footprint=box(x,y)
        mapped={name:frame for name in CAMERAS}
        departure.append({'video_frame':i,'native_frame':frame,'time_s':time,
            'camera_native_frames':mapped,'ego_id':'synthetic-ego',
            'traffic_id':'synthetic-traffic','ego_road_id':'1','traffic_road_id':'1',
            'ego_xy_m':[x,y],'traffic_xy_m':[tx,-1.75],
            'ego_footprint_xy_m':footprint,'traffic_footprint_xy_m':box(tx,-1.75),
            'ego_speed_mps':0 if i<150 else 2,'traffic_speed_mps':ts})
        mapping.append({'video_frame':i,'native_frame':frame,'carla_frame':frame,
                        'time_s':time,'camera_native_frames':mapped})
        core.append({'frame':frame,'time_s':time,
            'position':{'x':x,'y':y,'z':1.0},'position_m':[x,y,1.0],
            'heading_deg':0.0,'speed_mps':0 if i<150 else 2,
            'speed_mph':0 if i<150 else 2/.44704,
            'control':{'throttle':0.0,'brake':0.0,'hand_brake':False},
            'synthetic_diagnostic':True,'velocity_mps':[0 if i<150 else 2,0,0],
            'speed_provenance':'synthetic_native_sample'})
        body=[[px,py,z] for px,py in footprint for z in (0.0,1.5)]
        evidence.append({'original_frame':frame,'replay_frame':frame,
            'actor_id':107,'recording_time_s':time,'replay_simulation_time_s':time,
            'ego':{'position_m':[x,y,1.0],'heading_deg':0.0,
                   'speed_mps':0 if i<150 else 2,
                   'speed_provenance':'synthetic_native_sample',
                   'body_vertices_m':body},
            'world':{'weather':{'cloudiness':0,'precipitation':0,
                                'wetness':0,'fog_density':0},
                     'road_projection':{'road_id':1,'section_id':0,
                                        'lane_id':-2 if i<200 else -1,
                                        's_m':x+80}}})
        name=f'{frame:08d}.adapter.json'
        graph_frames.append({'frame':frame,'time_s':time,'simulation_time':time,
                             'synthetic_diagnostic':True,
                             'adapter_graph':'graphs/base/'+name})
        graphs.append({'path':'capture/native/graphs/base/'+name,
                       'attributes':{'frame':frame},'nodes':[],'edges':[]})
    for name,values in (('departure-trace.jsonl',departure),
                        ('video_frames.jsonl',mapping),('trace.jsonl',core),
                        ('capture/evidence.jsonl',evidence),
                        ('capture/native/frames.jsonl',graph_frames)):
        write(folder,name,rows(values))
    write(folder,'road.xodr',road)
    write(folder,'departure-context.json',json.dumps(context,indent=2))
    write(folder,'capture/recorder_info.txt','Create 107: vehicle.tesla.model3')
    write(folder,'acquisition-provenance.json',json.dumps({
        'provenance_kind':'synthetic_fixture','diagnostic_fixture':True,
        'native_executed':False},indent=2))
    manifest={'extraction_confirmed':True,'frames':600,
        'required_observations':[],'synthetic_diagnostic':True,
        'sources':{'road.xodr':sha(folder/'road.xodr'),
                   'trace.jsonl':sha(folder/'trace.jsonl')}}
    write(folder,'capture/manifest.json',json.dumps(manifest,indent=2))
    generator={'files':{},'graphs':graphs,
        'videos':[{'path':name+'.mkv','frames':600,
                   'width':1920 if name=='overview' else 1280,
                   'height':1080 if name=='overview' else 720,
                   'fps':20,'color':color} for name,color in
                  zip(CAMERAS,('blue','green','white','red'))]}
    generator_path=HERE/('selected-generator-'+suffix+'.json')
    generator_path.write_text(json.dumps(generator,separators=(',',':'))+'\n')
    inventory=[{'path':str(path.relative_to(folder)),
                'source':str(path.relative_to(ROOT)),'sha256':sha(path)}
               for path in sorted(folder.rglob('*')) if path.is_file()]
    recipe={'format':'worker-fixture-recipe','sources':inventory,
        'generator':{'source':str(generator_path.relative_to(ROOT)),
                     'sha256':sha(generator_path)}}
    recipe_path=HERE/('selected-recipe-'+suffix+'.json')
    recipe_path.write_text(json.dumps(recipe,indent=2)+'\n')
    return {'case':suffix,'sources':len(inventory),
            'generator_sha256':sha(generator_path),'recipe_sha256':sha(recipe_path)}


if __name__=='__main__':
    print(json.dumps([build('controlled_1',False),build('controlled_2',True)]))
