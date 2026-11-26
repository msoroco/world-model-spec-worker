"""Build source-shaped CPU fixtures for exact selected lane-arrow cases."""
import hashlib
import json
from pathlib import Path

from prove_lane_arrow import packet

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
ASSIGNMENT=ROOT.name
CAMERAS=('overview','approach','reference_corner','driver_reference')
TEMPLATE=ROOT.parent/'training__C230259__NRS-484B-208-1__motor_vehicle_driver/diagnostic-reference-primary.json'


def encoded(value):
    return json.dumps(value,separators=(',',':'),sort_keys=True)


def lines(rows):
    return ''.join(encoded(row)+'\n' for row in rows)


def save(path,value):
    path.write_text(encoded(value)+'\n')
    if path.stat().st_size>2*1024*1024:
        raise ValueError('Returned fixture file exceeds 2 MiB: '+str(path))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(tag,lane):
    case_id=ASSIGNMENT+'__selected_378a10ff__'+tag
    source=packet(proposed_lane=lane,occupied_lane=lane)['frames']
    for row in source:
        row['diagnostic_fixture']=True
        row['signal']['mount_m']=[60.0,-1.75,4.5]
    signal_path=ROOT/f'diagnostic-{tag}-native-signal-rows.jsonl'
    signal_path.write_text(lines(source))
    template=json.loads(TEMPLATE.read_text())
    spec={'files':{},'graphs':[],'videos':template['videos']}
    frames=[];trace=[];evidence=[];native_frames=[]
    first=source[0]['native_frame']
    for i,row in enumerate(source):
        frame=first+i
        t=round(i/20,3)
        x=round(10+75*i/599,5)
        y=-1.75 if lane==-1 else -5.25
        video=json.loads(template['files']['video_frames.jsonl'].splitlines()[i])
        video.update(video_frame=i,carla_frame=frame,native_frame=frame,time_s=t,
                     camera_native_frames={name:frame for name in CAMERAS})
        frames.append(video)
        trace.append({'frame':frame,'time_s':t,'position':{'x':x,'y':y,'z':1.0},
                      'position_m':[x,y,1.0],'heading_deg':0.0,'speed_mps':2.5,
                      'speed_mph':5.5923407,'velocity_mps':[2.5,0.0,0.0],
                      'control':{'throttle':0.0,'steer':0.0,'brake':0.0,'hand_brake':False}})
        body=[[x+dx,y+dy,0.0] for dx,dy in ((-2,-0.9),(2,-0.9),(2,0.9),(-2,0.9))]
        evidence.append({'original_frame':frame,'replay_frame':frame,
                         'recording_time_s':t,'replay_simulation_time_s':t,'actor_id':71,
                         'ego':{'position_m':[x,y,1.0],'heading_deg':0.0,'speed_mps':2.5,
                                'body_vertices_m':body,'speed_provenance':'synthetic_native_sample'},
                         'world':{'weather':{'cloudiness':0,'precipitation':0,'wetness':0,'fog_density':0},
                                  'road_projection':{'road_id':1,'section_id':0,'lane_id':lane,'s_m':x}}})
        graph=f'graphs/base/{frame:08d}.adapter.json'
        native_frames.append({'abstract':graph,'adapter_graph':graph,'base':graph,
                              'edges':0,'frame':frame,'nodes':0,
                              'simulation_time':t,'time_s':t,'synthetic_diagnostic':True})
        spec['graphs'].append({'path':'capture/native/'+graph,
                              'attributes':{'frame':frame},'nodes':[],'edges':[]})
    spec['files']={'video_frames.jsonl':lines(frames),'trace.jsonl':lines(trace),
                   'capture/evidence.jsonl':lines(evidence),
                   'capture/native/frames.jsonl':lines(native_frames),
                   'capture/manifest.json':encoded({'frames':600,'extraction_confirmed':True,
                       'synthetic_diagnostic':True,'case_id':case_id,'required_observations':[],
                       'sources':{'native-map-readback.xodr':sha(HERE/'road.xodr'),
                                  'trace.jsonl':hashlib.sha256(lines(trace).encode()).hexdigest()}})+'\n',
                   'capture/recorder_info.txt':'Synthetic CPU diagnostic; no CARLA recording.\n'}
    spec_path=ROOT/f'diagnostic-{tag}.json';save(spec_path,spec)
    source_files=[('native-signal-rows.jsonl',signal_path),
                  ('native-map-readback.xodr',HERE/'road.xodr')]
    recipe={'format':'worker-fixture-recipe',
            'sources':[{'path':name,'source':str(path.relative_to(ROOT.parents[1])),
                        'sha256':sha(path)} for name,path in source_files],
            'generator':{'source':str(spec_path.relative_to(ROOT.parents[1])),
                         'sha256':sha(spec_path)}}
    recipe_path=ROOT/f'diagnostic-{tag}-recipe.json';save(recipe_path,recipe)
    print(encoded({'case_id':case_id,'spec_bytes':spec_path.stat().st_size,
                   'recipe_sha256':sha(recipe_path),'source_sha256':sha(signal_path)}))


if __name__=='__main__':
    for tag,lane in (('condition_a',-1),('condition_b',-2)):
        build(tag,lane)
