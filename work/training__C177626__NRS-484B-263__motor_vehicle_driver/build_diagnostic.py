"""Build small textual CPU diagnostics for exact entry cases, never physical evidence."""
from hashlib import sha256
import json
from pathlib import Path
import sys

root=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'native'))
from acquisition import VIEWS
from geometry import open_drive


def write_text(path, content):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(content)


def lines(records):
    return ''.join(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n' for row in records)


def build(suffix):
    case=root.name+'__selected_ed45c8e4__condition_'+suffix
    src=root/'selected-source'/('condition_'+suffix)
    src.mkdir(parents=True,exist_ok=True)
    rows=[];cameras=[];history=[];trace=[];evidence=[];frame_map=[];native_frames=[]
    for i in range(600):
        t=i/20;native_frame=1000+i;x=-70+8*t
        ego_road=13 if x<0 else 2 if x<20 else 4
        ego_y=-20+(x+70)*20/70 if x<0 else 0
        ego={'center_xy_m':[x,ego_y],'velocity_xy_mps':[8,8*20/70] if x<0 else [8,0],
             'radius_m':1.2,'road_id':ego_road,'lane_id':-1}
        traffic={}
        for name,start in (('near',-110),('far',-170)):
            other_x=start+10*t
            traffic[name]={'center_xy_m':[other_x,-1.75],
                           'velocity_xy_mps':[10,0],'radius_m':1.2,
                           'road_id':1 if other_x<0 else 2 if other_x<20 else 4,
                           'lane_id':-1}
        rows.append({'frame':i,'native_frame':native_frame,'time_s':t,'native_elapsed_s':t,
                     'ego':ego,'traffic':traffic,'ego_yielding':i<200,
                     'controller_yield_request':i<200})
        cameras.append({'frame':native_frame,'views':{view:native_frame for view in VIEWS}})
        history.append({'frame':native_frame,'time_s':t,'position_m':[x,ego_y],
                        'road_id':ego_road})
        trace.append({'frame':native_frame,'time_s':t,
                      'position':{'x':x,'y':ego_y,'z':1},'position_m':[x,ego_y,1],
                      'heading_deg':0,'speed_mps':8,'speed_mph':8*2.2369362920544,
                      'control':{'throttle':0,'brake':0,'hand_brake':False},
                      'synthetic_diagnostic':True,'velocity_mps':[8,0,0],
                      'speed_provenance':'synthetic_native_sample'})
        evidence.append({'original_frame':native_frame,'replay_frame':native_frame,
                         'actor_id':107,'recording_time_s':t,'replay_simulation_time_s':t,
                         'ego':{'position_m':[x,ego_y,1],'heading_deg':0,
                                'speed_mps':8,'speed_provenance':'synthetic_native_sample',
                                'body_vertices_m':[[x+dx,ego_y+dy,z]
                                  for dx in (-2.35,2.35) for dy in (-0.95,0.95)
                                  for z in (0,1.5)]},
                         'world':{'weather':{'cloudiness':0,'precipitation':0,'wetness':0,'fog_density':0},
                                  'road_projection':{'road_id':ego_road,'section_id':0,'lane_id':-1,'s_m':max(0,x+70)}}})
        frame_map.append({'native_frame':native_frame,'carla_frame':native_frame,
                          'video_frame':i,'time_s':t,
                          'camera_native_frames':{view:native_frame for view in VIEWS}})
        native_frames.append({'frame':native_frame,'time_s':t,'simulation_time':t,
                              'synthetic_diagnostic':True,
                              'adapter_graph':f'graphs/base/{native_frame:08d}.adapter.json'})
    files={'native_samples.jsonl':lines(rows),'camera_frames.jsonl':lines(cameras),
           'entry_history.jsonl':lines(history),'trace.jsonl':lines(trace),
           'capture/evidence.jsonl':lines(evidence),'video_frames.jsonl':lines(frame_map),
           'capture/native/frames.jsonl':lines(native_frames),
           'capture/recorder_info.txt':'Create 107: vehicle.lincoln.mkz_2020\nSynthetic diagnostic only; no CARLA recording.\n',
           'capture-seal.json':json.dumps({'diagnostic_fixture':True,'provenance_kind':'synthetic_fixture'})+'\n',
           'acquisition-provenance.json':json.dumps({'provenance_kind':'synthetic_fixture','diagnostic_fixture':True})+'\n',
           'road.xodr':open_drive(),
           'authored-context.json':json.dumps({'case_id':case,'candidate_id':'near_80',
             'route_kind':'entry','map_source':'native_opendrive_readback',
             'map_sha256':'a'*64,'actor_inventory_source':'synthetic_diagnostic_inventory',
             'approaching_vehicle_ids':['near','far'],
             'controlled_access_designation_verified':False,
             'legal_immediate_hazard_conclusion':None,
             'legal_reasonable_safety_conclusion':None})+'\n'}
    files['capture/manifest.json']=json.dumps({'extraction_confirmed':True,'frames':600,
       'required_observations':[],'synthetic_diagnostic':True,
       'sources':{'road.xodr':sha256(files['road.xodr'].encode()).hexdigest(),
                  'trace.jsonl':sha256(files['trace.jsonl'].encode()).hexdigest()}},indent=2)+'\n'
    for name,content in files.items():write_text(src/name,content)
    graphs=[{'path':f'capture/native/graphs/base/{1000+i:08d}.adapter.json',
             'attributes':{'frame':1000+i},'nodes':[],'edges':[]} for i in range(600)]
    generator={'files':{},'graphs':graphs,'videos':[
        {'path':view+'.mkv','frames':600,'width':1920 if view=='overview' else 1280,
         'height':1080 if view=='overview' else 720,'fps':20,'color':color}
        for view,color in zip(VIEWS,('blue','green','white','red'))]}
    genpath=root/f'selected-generator-condition-{suffix}.json'
    genpath.write_text(json.dumps(generator,separators=(',',':'))+'\n')
    recipe={'format':'worker-fixture-recipe','sources':[
        {'path':name,'source':str((src/name).relative_to(Path.cwd())),
         'sha256':sha256((src/name).read_bytes()).hexdigest()} for name in files],
        'generator':{'source':str(genpath.relative_to(Path.cwd())),
                     'sha256':sha256(genpath.read_bytes()).hexdigest()}}
    recipe_path=root/f'selected-recipe-condition-{suffix}.json'
    recipe_path.write_text(json.dumps(recipe,indent=2)+'\n')
    print(case,len(files),len(graphs),recipe_path)


if __name__=='__main__':
    for suffix in ('a','b'):build(suffix)
