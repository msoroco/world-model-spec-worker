"""Source-shaped branch diagnostics; no original Native or legal claim."""
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'native'))
from native.expanded_layout import open_drive,ENTRANCE
from native.branch_variants import BRANCHES

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CAMERAS=('overview','approach','reference_corner','driver_reference')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(folder,name,text):
    path=folder/name;path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text.rstrip()+'\n')


def lines(items):return '\n'.join(json.dumps(item,allow_nan=False,separators=(',',':')) for item in items)+'\n'


def build(suffix):
    branch=BRANCHES[suffix]
    target=branch.target_center_x_m
    start=branch.spawn_center_x_m
    y=-2 if branch.side=='same' else 2
    direction=1 if branch.side=='same' else -1
    folder=HERE/'selected-source'/suffix;folder.mkdir(parents=True,exist_ok=True)
    parking=[];mapping=[];core=[];evidence=[];graph_frames=[];graphs=[]
    for index in range(600):
        frame=index+100;time=index/20
        x=start+(target-start)*min(index,300)/300
        speed=4 if index<300 else 0
        body=[[x-2,y-1],[x+2,y-1],[x+2,y+1],[x-2,y+1]]
        cameras={name:frame for name in CAMERAS}
        parking.append({'native_frame':frame,'video_frame':index,'time_s':time,
            'source_kind':'synthetic_diagnostic','actor_id':107,
            'blueprint_id':'vehicle.tesla.model3','center_xy_m':[x,y],
            'body_xy_m':body,'speed_mps':speed,
            'traffic_conflict_vehicle':({'actor_id':108,'blueprint_id':'vehicle.tesla.model3',
                'body_xy_m':[[11,-3],[15,-3],[15,-1],[11,-1]],'speed_mps':0}
                if suffix=='traffic_conflict' else None)})
        mapping.append({'native_frame':frame,'carla_frame':frame,'video_frame':index,
            'time_s':time,'camera_native_frames':cameras})
        core.append({'frame':frame,'time_s':time,'position':{'x':x,'y':y,'z':1},
            'position_m':[x,y,1],'heading_deg':branch.heading_deg,'speed_mps':speed,
            'speed_mph':speed/.44704,'control':{'throttle':0,'brake':0,'hand_brake':False},
            'synthetic_diagnostic':True,'velocity_mps':[direction*speed,0,0],
            'speed_provenance':'synthetic_native_sample'})
        vertices=[[px,py,z] for px,py in body for z in (0,1.5)]
        evidence.append({'original_frame':frame,'replay_frame':frame,'actor_id':107,
            'recording_time_s':time,'replay_simulation_time_s':time,
            'ego':{'position_m':[x,y,1],'heading_deg':branch.heading_deg,'speed_mps':speed,
            'speed_provenance':'synthetic_native_sample','body_vertices_m':vertices},
            'world':{'weather':{'cloudiness':0,'precipitation':0,'wetness':0,'fog_density':0},
            'road_projection':{'road_id':1,'section_id':0,'lane_id':branch.target_lane_id,'s_m':x+80}}})
        name=f'{frame:08d}.adapter.json'
        graph_frames.append({'frame':frame,'time_s':time,'simulation_time':time,
            'synthetic_diagnostic':True,'adapter_graph':'graphs/base/'+name})
        graphs.append({'path':'capture/native/graphs/base/'+name,
            'attributes':{'frame':frame},'nodes':[],'edges':[]})
    for name,items in [('native-vehicle.jsonl',parking),('video_frames.jsonl',mapping),
        ('trace.jsonl',core),('capture/evidence.jsonl',evidence),
        ('capture/native/frames.jsonl',graph_frames)]:write(folder,name,lines(items))
    write(folder,'road.xodr',open_drive())
    write(folder,'entrance-context.json',json.dumps({'source_kind':'synthetic_diagnostic',
        'cell_id':'C229410','entrance':ENTRANCE,'initial_activity':branch.activity,
        'exception_context':branch.exception,'fire_station_identity_reviewed':True,
        'driveway_entrance_reviewed':True,'highway_side_reviewed':True,
        'parking_activity_reviewed':False,'traffic_conflict_reviewed':False,
        'law_officer_device_direction_reviewed':False,
        'police_direction_source_observed':suffix=='police_direction',
        'official_device_source_observed':suffix=='device_direction',
        'applicable_law_source_reviewed':suffix=='law_direction',
        'fixture_kind':'synthetic_diagnostic_only'},indent=2))
    write(folder,'capture/recorder_info.txt','Create 107: vehicle.tesla.model3')
    write(folder,'acquisition-provenance.json',json.dumps({'provenance_kind':'synthetic_fixture',
        'diagnostic_fixture':True,'native_executed':False},indent=2))
    manifest={'extraction_confirmed':True,'frames':600,'required_observations':[],
        'synthetic_diagnostic':True,'sources':{'road.xodr':sha(folder/'road.xodr'),
        'trace.jsonl':sha(folder/'trace.jsonl')}}
    write(folder,'capture/manifest.json',json.dumps(manifest,indent=2))
    generator={'files':{},'graphs':graphs,'videos':[{'path':name+'.mkv','frames':600,
        'width':1920 if name=='overview' else 1280,
        'height':1080 if name=='overview' else 720,'fps':20,'color':color}
        for name,color in zip(CAMERAS,('blue','green','white','red'))]}
    gen=HERE/('selected-generator-'+suffix+'.json');gen.write_text(json.dumps(generator,separators=(',',':'))+'\n')
    sources=[{'path':str(path.relative_to(folder)),'source':str(path.relative_to(ROOT)),
        'sha256':sha(path)} for path in sorted(folder.rglob('*')) if path.is_file()]
    recipe={'format':'worker-fixture-recipe','sources':sources,
        'generator':{'source':str(gen.relative_to(ROOT)),'sha256':sha(gen)}}
    dest=HERE/('selected-recipe-'+suffix+'.json')
    dest.write_text(json.dumps(recipe,indent=2)+'\n')
    return {'case':suffix,'source_count':len(sources),'recipe_sha256':sha(dest)}


if __name__=='__main__':
    print(json.dumps([build(suffix) for suffix in BRANCHES if suffix not in ('controlled_1','controlled_2')]))
