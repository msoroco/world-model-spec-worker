"""Build explicit-source current-v2 diagnostics for both 400(1) branches."""
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
FOLDER=Path(__file__).resolve().parent
FINALIZER=FOLDER/'native/finalize.py'
sys.path.insert(0,str(FOLDER/'native'))
from engineering import parameters
from geometry import open_drive


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write_rows(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text('\n'.join(json.dumps(row) for row in rows)+'\n')


def source_digest(folder):
    return {str(p.relative_to(folder)):sha(p) for p in folder.rglob('*') if p.is_file() and p.name not in ('analysis-report.json','result.json')}


def make_base(destination,suffix,approach_y,frame_count=480):
    destination.mkdir(parents=True,exist_ok=True);(destination/'capture').mkdir(exist_ok=True)
    construction=json.loads((FOLDER/'selected-candidates'/suffix/'primary/construction.json').read_text())
    config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
    if frame_count!=480:raise ValueError('Selected diagnostic requires 480 frames')
    config['duration_s']=frame_count/20;config['rate_hz']=20
    (destination/'config.json').write_text(json.dumps(config))
    geometry={'native_map_sha256':'a'*64,'approach_road_id':1,
              'turn_connector_road_id':13,'right_turn_lane_id':-2,
              'design_source':'synthetic_native_map_survey',
              'single_right_only_turn_lane':suffix.startswith('witness_'),
              'rightmost_lane_id':-2,'turn_connector_lane_id':-2,
              'right_turn_lane_native_y_bounds_m':[3.5,7.0],
              'intersection_native_xy_bounds_m':[-7,-7,7,7],
              'right_turn_lane_design_native_verified':False}
    (destination/'road_geometry.json').write_text(json.dumps(geometry))
    (destination/'context.json').write_text(json.dumps({'surveyed_right_turn_lane_intersection':geometry}))
    trace=[];evidence=[];mapping=[];motion=[];history=[]
    lane=-2 if suffix.endswith('_1') else -1
    if frame_count==4:
        states=[(-20,approach_y,(1,0),1,lane),(-12,approach_y,(1,0),1,lane),
                (-3,2,(.7,.714142842),13,-2),(-5.25,12,(0,1),4,-2)]
    else:
        states=[]
        requested=parameters(suffix,'primary')['native_route_xy_m']
        entry_index=round(((-7)+50)/.1)
        turn_points=requested[entry_index:entry_index+151]
        assert len(turn_points)==151
        for index in range(frame_count):
            if index<160:
                x=-40+33*index/159;y=approach_y;angle=0;road_id=1;lane_id=lane
            elif index<320:
                point=round(150*(index-160)/159)
                x,y=turn_points[point]
                before=turn_points[max(0,point-1)]
                after=turn_points[min(150,point+1)]
                angle=math.atan2(after[1]-before[1],after[0]-before[0]);road_id=13;lane_id=-2
            else:
                x=-5.25;y=7.3+32.7*(index-320)/159;angle=math.pi/2;road_id=4;lane_id=-2
            states.append((x,y,(math.cos(angle),math.sin(angle)),road_id,lane_id))
    for i,(x,y,forward,road_id,lane_id) in enumerate(states):
        frame=100+i;t=.05*(i+1)
        fx,fy=forward;rx,ry=-fy,fx
        corners=[[x+direction*2.6*fx+side*1.1*rx,
                  y+direction*2.6*fy+side*1.1*ry]
                 for direction,side in ((-1,-1),(-1,1),(1,1),(1,-1))]
        body=[[a,b,z] for a,b in corners for z in (0,1.5)]
        position=[x,y,0.5]
        trace.append({'frame':frame,'time_s':t,
                      'position':{'x':x,'y':y,'z':0.5},
                      'position_m':position,
                      'heading_deg':math.degrees(math.atan2(fy,fx)),
                      'speed_mps':5.0,'speed_provenance':'synthetic_native_sample',
                      'control':{'throttle':0,'brake':0,'hand_brake':False},
                      'synthetic_diagnostic':True})
        evidence.append({'original_frame':frame,'replay_frame':frame,'actor_id':107,
                         'recording_time_s':t,'replay_simulation_time_s':t,
                         'ego':{'position_m':position,
                                'heading_deg':math.degrees(math.atan2(fy,fx)),
                                'speed_mps':5.0,'speed_provenance':'synthetic_native_sample',
                                'body_vertices_m':body},
                         'world':{'weather':{'cloudiness':0,'precipitation':0,
                                             'wetness':0,'fog_density':0},
                                  'road_projection':{'road_id':road_id,'section_id':0,
                                                     'lane_id':lane_id,'s_m':max(0,x+100)}}})
        mapping.append({'video_frame':i,'native_frame':frame,'carla_frame':frame,'time_s':t})
        motion.append({'native_frame':frame,'time_s':t,'native_center_xy_m':[x,y],
                       'native_forward_xy':list(forward),'native_body_xy_m':corners,
                       'native_road_id':road_id,'native_lane_id':lane_id,
                       'speed_mps':5.0,'speed_provenance':'synthetic_native_sample'})
        history.append({'frame':frame,'time_s':t,'body_vertices_m':body})
    for index,row in enumerate(trace):
        before,after=(trace[0],trace[1]) if index==0 else (trace[index-1],row)
        dt=after['time_s']-before['time_s']
        velocity=[(after['position_m'][axis]-before['position_m'][axis])/dt
                  for axis in range(3)]
        speed=math.sqrt(sum(value*value for value in velocity))
        row['velocity_mps']=velocity
        row['speed_mps']=speed
        row['speed_mph']=speed/.44704
        evidence[index]['ego']['speed_mps']=speed
        motion[index]['speed_mps']=speed
    for name,rows in [('trace.jsonl',trace),('capture/evidence.jsonl',evidence),
                      ('video_frames.jsonl',mapping),('native_samples.jsonl',motion),
                      ('body_history.jsonl',history)]:write_rows(destination/name,rows)
    (destination/'road.xodr').write_text(open_drive(right_only=suffix.startswith('witness_'))+'\n')
    (destination/'capture/manifest.json').write_text(json.dumps({
        'extraction_confirmed':True,'frames':frame_count,'required_observations':[],
        'sources':{'road.xodr':sha(destination/'road.xodr'),
                   'trace.jsonl':sha(destination/'trace.jsonl')},
        'synthetic_diagnostic':True})+'\n')
    (destination/'capture/recorder_info.txt').write_text('Create 107: vehicle.lincoln.mkz_2020\n')
    native_frames=[{'frame':100+i,'time_s':(i+1)/20,'simulation_time':(i+1)/20,
                    'synthetic_diagnostic':True,
                    'adapter_graph':f'graphs/base/{100+i:08d}.adapter.json'}
                   for i in range(frame_count)]
    write_rows(destination/'capture/native/frames.jsonl',native_frames)
    (destination/'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind':'synthetic_local_diagnostic','diagnostic_fixture':True,
        'native_executed':False})+'\n')
    (destination/'channels').mkdir(exist_ok=True)
    for channel in config['recording_description']['channels']:
        name=channel['name'];values=[]
        for index,sample in enumerate(motion):
            if name=='drv.turning':value={'authored_intent':'right turn','observed_forward':sample['native_forward_xy']}
            elif name in ('st.intersection','st.turn_lane'):
                value=geometry
            elif name in ('drv.extreme_lane','st.lane_adjacency'):
                value={'observed_lane_id':sample['native_lane_id'],'rightmost_lane_id':-2}
            elif name=='drv.approaching':value=max(a for a,b in sample['native_body_xy_m'])<-7
            elif name=='rel.occupies':value=sample['native_body_xy_m']
            elif name=='native_body_pose_control':value=sample
            elif name=='camera_frame_join':value=mapping[index]
            else:raise ValueError('Unknown channel '+name)
            values.append({'time_s':sample['time_s'],'value':value})
        write_rows(destination/'channels'/(name+'.jsonl'),values)


CAMERAS=(('overview',1920,1080,'blue'),('approach',1280,720,'green'),
         ('reference_corner',1280,720,'white'),('driver_reference',1280,720,'red'))
CASES=('witness_1','witness_2','extreme_right_1','extreme_right_2')


def build(suffix):
    destination=FOLDER/'selected-v2-source'/suffix
    make_base(destination,suffix,5.25 if suffix.endswith('_1') else 1.75)
    names=['trace.jsonl','video_frames.jsonl','native_samples.jsonl',
           'body_history.jsonl','road_geometry.json','road.xodr','context.json',
           'capture/manifest.json','capture/recorder_info.txt',
           'capture/evidence.jsonl','capture/native/frames.jsonl',
           'acquisition-provenance.json']
    names.extend(str(p.relative_to(destination)) for p in sorted((destination/'channels').glob('*.jsonl')))
    sources=[]
    for name in names:
        target=destination/name
        if target.stat().st_size>2*1024*1024:
            raise ValueError('Source exceeds 2 MiB: '+name)
        sources.append({'path':name,'source':str(target.relative_to(ROOT)),
                        'sha256':sha(target)})
    graphs=[{'path':f'capture/native/graphs/base/{frame:08d}.adapter.json',
             'attributes':{'frame':frame},'nodes':[],'edges':[]}
            for frame in range(100,580)]
    videos=[{'path':name+'.mkv','frames':480,'width':width,'height':height,
             'fps':20,'color':color} for name,width,height,color in CAMERAS]
    generator={'files':{},'graphs':graphs,'videos':videos}
    generator_path=FOLDER/f'selected-v2-{suffix}-generator.json'
    generator_path.write_text(json.dumps(generator,separators=(',',':'))+'\n')
    recipe={'format':'worker-fixture-recipe','sources':sources,
            'generator':{'source':str(generator_path.relative_to(ROOT)),
                         'sha256':sha(generator_path)}}
    recipe_path=FOLDER/f'selected-v2-{suffix}-recipe.json'
    recipe_path.write_text(json.dumps(recipe,indent=2)+'\n')
    return {'case':suffix,'source_count':len(sources),'recipe_sha256':sha(recipe_path)}


if __name__=='__main__':
    print(json.dumps([build(suffix) for suffix in CASES]))


