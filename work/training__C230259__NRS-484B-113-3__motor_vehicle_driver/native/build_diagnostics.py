"""Generate textual, explicitly synthetic 600-frame Native-shaped fixtures."""
import hashlib
import json
import math
from pathlib import Path

from layout import CONFLICT,open_drive
from measure_motion import CAMERAS

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text if text.endswith('\n') else text+'\n')


def actor(actor_id,blueprint,x,y,vx,vy):
    body=[[x-2,y-1],[x+2,y-1],[x+2,y+1],[x-2,y+1]]
    return {'actor_id':actor_id,'blueprint_id':blueprint,'center_xy_m':[x,y],
        'body_xy_m':body,'velocity_xy_mps':[vx,vy],'speed_mps':math.hypot(vx,vy)}


def build_case(suffix):
    branch=suffix.startswith('pedestrian_');early=suffix.endswith('_2')
    start,end=(55,145) if early else (245,335)
    source_root=ROOT/'diagnostic-sources'/suffix
    road=source_root/'road.xodr';write(road,open_drive())
    texts={name:[] for name in ('native-motion.jsonl','video_frames.jsonl','trace.jsonl',
        'capture/evidence.jsonl','capture/native/frames.jsonl')}
    graphs=[]
    for index in range(600):
        frame=index+100;time=index/20;active=start<=index<end
        progress=max(0,min(index-start,90));x=23-progress*.125;y=-7+progress*.04
        ego=actor(101,'vehicle.tesla.model3',x,y,-2.5 if active else 0,.8 if active else 0)
        other=actor(102,'vehicle.tesla.model3',-35+min(index,300)*.3,-3,6 if index<300 else 0,0)
        pedestrian=actor(103,'walker.pedestrian.0001',12,4-max(0,min(index-50,250))*.04,
            0,-.8 if 50<=index<300 else 0) if branch else None
        row={'frame':frame,'native_frame':frame,'video_frame':index,'time_s':time,
            'source_kind':'original_native','ego':ego,'other':other,'pedestrian':pedestrian,
            'backing_commanded':active}
        mapped={'video_frame':index,'carla_frame':frame,'native_frame':frame,'time_s':time,
            'camera_native_frames':{name:frame for name in CAMERAS}}
        trace={'frame':frame,'time_s':time,'position':{'x':x,'y':y,'z':1.2},
            'position_m':[x,y,1.2],'heading_deg':0,'speed_mps':ego['speed_mps'],
            'speed_mph':ego['speed_mps']*2.2369362921,
            'velocity_mps':[ego['velocity_xy_mps'][0],ego['velocity_xy_mps'][1],0],
            'control':{'throttle':0,'brake':0,'hand_brake':False,'reverse':active}}
        vertices=[[px,py,z] for px,py in ego['body_xy_m'] for z in (0,1.5)]
        evidence={'original_frame':frame,'recording_time_s':time,'replay_frame':frame,
            'replay_simulation_time_s':time,'actor_id':101,
            'ego':{'body_vertices_m':vertices,'position_m':[x,y,1.2],
                'heading_deg':0,'speed_mps':ego['speed_mps'],
                'speed_provenance':'synthetic_diagnostic'},
            'world':{'weather':{'cloudiness':0,'precipitation':0,'wetness':0,'fog_density':0},
                'road_projection':{'road_id':1,'section_id':0,'lane_id':-1,'s_m':x+80}}}
        graph_path=f'capture/native/graphs/base/{frame:08d}.adapter.json'
        graph={'path':graph_path,'attributes':{'frame':frame,'simulation_time_s':time,
            'synthetic_diagnostic':True},'nodes':[],'edges':[]}
        native_frame={'abstract':f'graphs/base/{frame:08d}.adapter.json',
            'adapter_graph':f'graphs/base/{frame:08d}.adapter.json',
            'base':f'graphs/base/{frame:08d}.adapter.json','edges':0,'frame':frame,
            'nodes':0,'simulation_time':time,'synthetic_diagnostic':True,'time_s':time}
        for name,value in [('native-motion.jsonl',row),('video_frames.jsonl',mapped),
            ('trace.jsonl',trace),('capture/evidence.jsonl',evidence),
            ('capture/native/frames.jsonl',native_frame)]:
            texts[name].append(json.dumps(value,allow_nan=False))
        graphs.append(graph)
    for name,lines in texts.items():write(source_root/name,'\n'.join(lines)+'\n')
    context={'source_kind':'original_native','cell_id':'C230259','conflict_region':CONFLICT,
        'section_stem_recovered':True,'section_source':'https://www.leg.state.nv.us/NRS/NRS-484B.html',
        'other_highway_use_reviewed':True,'other_road_id':1,'other_lane_id':-1,
        'other_route_direction':'increasing road s','other_commanded_speed_mps':6,
        'driver_control_reviewed':True,'ego_actor_id':101,'other_actor_id':102,
        'pedestrian_presence_reviewed':True,'pedestrian_actor_count_at_start':int(branch),
        'pedestrian_actor_id':103 if branch else None,'precedence_reviewed':False,
        'right_of_way_legal_verdict':None,'fixture_kind':'synthetic_diagnostic_only'}
    write(source_root/'traffic-context.json',json.dumps(context,indent=2)+'\n')
    manifest={'extraction_confirmed':True,'frames':600,
        'sources':{'road.xodr':sha(road),'trace.jsonl':sha(source_root/'trace.jsonl')},
        'synthetic_diagnostic':True}
    write(source_root/'capture/manifest.json',json.dumps(manifest)+'\n')
    write(source_root/'capture/recorder_info.txt','Synthetic diagnostic only; no CARLA recorder')
    generator={'files':{},'graphs':graphs,
        'videos':[{'path':name+'.mkv','frames':600,'width':1920 if name=='overview' else 1280,
            'height':1080 if name=='overview' else 720,'fps':20,'color':'black'} for name in CAMERAS]}
    spec=ROOT/('diagnostic-'+suffix+'.json');write(spec,json.dumps(generator,separators=(',',':'))+'\n')
    sources=[]
    for source in sorted(source_root.rglob('*')):
        if source.is_file():
            relative=str(source.relative_to(source_root))
            sources.append({'path':relative,'source':str(source.relative_to(REPO)),
                'sha256':sha(source)})
    recipe={'format':'worker-fixture-recipe','sources':sources,
        'generator':{'source':str(spec.relative_to(REPO)),'sha256':sha(spec)}}
    write(ROOT/('diagnostic-'+suffix+'-recipe.json'),json.dumps(recipe,indent=2)+'\n')
    return {'case':suffix,'source_count':len(sources),'graph_count':len(graphs)}


if __name__=='__main__':
    print(json.dumps([build_case(s) for s in ('controlled_1','controlled_2','pedestrian_1','pedestrian_2')]))
