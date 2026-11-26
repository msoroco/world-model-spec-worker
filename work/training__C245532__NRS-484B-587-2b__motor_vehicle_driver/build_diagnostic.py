"""Build source-hashed synthetic compatibility inputs for each selected case."""
import hashlib
import json
from pathlib import Path

from layout import open_drive

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
CAMERAS=('overview','approach','reference_corner','driver_reference')
SUFFIXES=('controlled_1','controlled_2','emergency_1','emergency_2')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')


def write_rows(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n' for row in rows))


def build(suffix):
    if suffix not in SUFFIXES:raise ValueError('Unknown selected case')
    case_id=ROOT.name+'__'+suffix
    target=ROOT/'selected-source'/suffix
    target.mkdir(parents=True,exist_ok=True)
    cross=suffix!='controlled_1';obstruction=suffix=='emergency_2'
    context={'source_kind':'original_native','cell_id':'C245532',
        'separator':{'y_m':-3.5,'x_min_m':-60,'x_max_m':60,'form':'solid',
            'color':'white','inner_lane_id':-1,'outer_lane_id':-2},
        'public_highway_reviewed':False,'legal_controlled_access_reviewed':False,
        'entrance_lane_function_reviewed':False,'official_line_reviewed':False,
        'emergency_necessity_reviewed':False,'subsection_3_conditions_reviewed':False,
        'vehicle_driver_scope_reviewed':False,
        'emergency_obstacle_requested':obstruction,
        'shoulder_permission_not_treated_as_crossing_authorization':True,
        'fixture_kind':'synthetic_diagnostic_only'}
    write_json(target/'separator-context.json',context)
    write_json(target/'acquisition-provenance.json',{'provenance_kind':'synthetic_fixture',
        'diagnostic_fixture':True,'native_executed':False})
    (target/'road.xodr').write_text(open_drive()+'\n')
    (target/'capture/recorder_info.txt').parent.mkdir(parents=True,exist_ok=True)
    (target/'capture/recorder_info.txt').write_text('Create 107: vehicle.tesla.model3\n')
    trace=[];evidence=[];motion=[];frame_map=[];native_frames=[]
    for index in range(600):
        native=100+index;time=index/20
        progress=max(0,min(index-40,140))/140 if cross else 0
        x=-42+min(index,350)*.25;y=-5.25+3.5*progress
        body=[[x-2,y-.9],[x+2,y-.9],[x+2,y+.9],[x-2,y+.9]]
        speed=5 if index<350 else 0
        lane=-1 if y>-3.5 else -2
        trace.append({'frame':native,'time_s':time,'position':{'x':x,'y':y,'z':1},
            'position_m':[x,y,1],'heading_deg':0,'speed_mps':speed,
            'speed_mph':speed*2.2369362920544,'velocity_mps':[speed,0,0],
            'control':{'throttle':0,'brake':0,'hand_brake':False},
            'synthetic_diagnostic':True,'speed_provenance':'synthetic_native_sample'})
        evidence.append({'original_frame':native,'replay_frame':native,'actor_id':107,
            'recording_time_s':time,'replay_simulation_time_s':time,
            'ego':{'position_m':[x,y,1],'heading_deg':0,'speed_mps':speed,
                'speed_provenance':'synthetic_native_sample',
                'body_vertices_m':[[u,v,z] for u,v in body for z in (0,1.5)]},
            'world':{'weather':{'cloudiness':0,'precipitation':0,'wetness':0,'fog_density':0},
                'road_projection':{'road_id':1,'section_id':0,'lane_id':lane,'s_m':x+60}}})
        motion.append({'native_frame':native,'video_frame':index,'time_s':time,
            'source_kind':'synthetic_diagnostic_only',
            'ego':{'actor_id':107,'blueprint_id':'vehicle.tesla.model3',
                'center_xy_m':[x,y],'body_xy_m':body,'velocity_xy_mps':[speed,0],
                'speed_mps':speed},
            'obstruction':{'actor_id':108,'blueprint_id':'vehicle.audi.tt',
                'center_xy_m':[-7,-5.25]} if obstruction else None,
            'lane_id':lane})
        frame_map.append({'native_frame':native,'carla_frame':native,'video_frame':index,
            'time_s':time,'camera_native_frames':{name:native for name in CAMERAS}})
        native_frames.append({'frame':native,'time_s':time,'simulation_time':time,
            'synthetic_diagnostic':True,
            'adapter_graph':f'graphs/base/{native:08d}.adapter.json'})
    files={'trace.jsonl':trace,'capture/evidence.jsonl':evidence,
        'native-motion.jsonl':motion,'video_frames.jsonl':frame_map,
        'capture/native/frames.jsonl':native_frames}
    for name,rows in files.items():write_rows(target/name,rows)
    write_json(target/'capture/manifest.json',{'extraction_confirmed':True,
        'frames':600,'required_observations':[],'synthetic_diagnostic':True,
        'sources':{'road.xodr':sha(target/'road.xodr'),
            'trace.jsonl':sha(target/'trace.jsonl')}})
    generator={'files':{},'graphs':[{'path':f'capture/native/graphs/base/{100+i:08d}.adapter.json',
        'attributes':{'frame':100+i},'nodes':[],'edges':[]} for i in range(600)],
        'videos':[{'path':name+'.mkv','frames':600,'width':1920 if name=='overview' else 1280,
            'height':1080 if name=='overview' else 720,'fps':20,'color':'blue'} for name in CAMERAS]}
    generator_path=ROOT/('selected-generator-'+suffix+'.json');write_json(generator_path,generator)
    sources=[{'path':name,'source':str((target/name).relative_to(REPO)),
        'sha256':sha(target/name)} for name in
        ('acquisition-provenance.json','capture/evidence.jsonl','capture/manifest.json',
        'capture/native/frames.jsonl','capture/recorder_info.txt','trace.jsonl',
        'video_frames.jsonl','road.xodr','separator-context.json','native-motion.jsonl')]
    write_json(ROOT/('selected-recipe-'+suffix+'.json'),{'format':'worker-fixture-recipe',
        'sources':sources,'generator':{'source':str(generator_path.relative_to(REPO)),
        'sha256':sha(generator_path)}})
    return {'case_id':case_id,'recipe':str((ROOT/('selected-recipe-'+suffix+'.json')).relative_to(REPO)),
        'source_files':len(sources)}


if __name__=='__main__':
    print(json.dumps([build(s) for s in SUFFIXES]))
