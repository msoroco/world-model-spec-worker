"""Source-shaped parked lamp diagnostics; no original physical claim."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
AID=ROOT.name
VIEWS=('overview','approach','reference_corner','driver_reference')

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(value if isinstance(value,str) else json.dumps(value,indent=2,sort_keys=True)+'\n')
def lines(rows):return ''.join(json.dumps(r,separators=(',',':'),sort_keys=True)+'\n' for r in rows)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def build(suffix):
    case=AID+'__'+suffix
    state='low_beam' if suffix=='probe_a' else 'high_beam'
    diagnostic=HERE/'diagnostic'/suffix
    sources=diagnostic/'sources'
    native=[];review=[];frames=[];trace=[];evidence=[];captures=[];graphs=[]
    footprint=[[4.1,-.8,2.1],[5.6,-.8,2.1],[4.1,.8,2.1],[5.6,.8,2.1]]
    for i in range(600):
        t=(i+1)/20
        base={'frame':i,'native_frame':i,'time_s':t}
        native.append(dict(base,source_kind='synthetic_cpu_fixture',ego_actor_id=10,
                           ego_blueprint_id='vehicle.lamp.diagnostic',
                           ego_center_xyz_m=[4.85,0,2.4],ego_speed_mps=0,
                           observed_footprint_xyz_m=footprint,observed_curb_lane_id=-2,
                           requested_headlamp_lit=True,requested_beam_state=state,
                           observed_light_state_bits=1 if suffix=='probe_a' else 2,
                           observed_beam_state=state,
                           source_cameras={name:i for name in VIEWS}))
        review.append(dict(base,parking_activity='parked',
                           aim_elevation_deg=-1.2 if suffix=='probe_a' else 1.2,
                           relative_intensity=.5 if suffix=='probe_a' else 1.0,
                           review_kind='synthetic_cpu_fixture'))
        frames.append(dict(video_frame=i,native_frame=i,carla_frame=i,time_s=t,
                           camera_native_frames={name:i for name in VIEWS}))
        trace.append({'frame':i,'time_s':t,'position':{'x':4.85,'y':0,'z':2.4},
                      'position_m':[4.85,0,2.4],'heading_deg':90,'speed_mps':0,'speed_mph':0,
                      'velocity_mps':[0,0,0],
                      'control':{'throttle':0,'brake':1,'hand_brake':True}})
        evidence.append({'actor_id':10,'original_frame':i,'replay_frame':i,
                         'recording_time_s':t,'replay_simulation_time_s':t,
                         'ego':{'position_m':[4.85,0,2.4],'body_vertices_m':footprint,
                                'heading_deg':90,'speed_mps':0,
                                'speed_provenance':'synthetic_native_sample',
                                'synthetic_diagnostic':True},
                         'other_actors':[],
                         'world':{'road_projection':{'road_id':1,'lane_id':-2,'section_id':0,'s_m':4.85},
                                  'weather':{'cloudiness':0,'fog_density':0,'precipitation':0,'wetness':0}}})
        graph=f'graphs/base/{i:08d}.adapter.json'
        captures.append({'frame':i,'simulation_time':t,'adapter_graph':graph,
                         'base':graph,'nodes':1,'edges':0})
        graphs.append({'path':'capture/native/'+graph,
                       'attributes':{'frame':i,'simulation_time_s':t,
                                     'synthetic_diagnostic':True},
                       'nodes':[{'id':'ego','attributes':{
                           'entity_id':10,'sem_class':'ego','vertex':[4.85,0,2.4],
                           'forward':[0,1,0],'threedbbox':footprint,
                           'light_LowBeam':suffix=='probe_a',
                           'light_HighBeam':suffix=='probe_b',
                           'vehicle_light_state':1 if suffix=='probe_a' else 2}}],
                       'edges':[]})
    data={'native-rows.jsonl':lines(native),'lamp-review.jsonl':lines(review),
          'video_frames.jsonl':lines(frames),'trace.jsonl':lines(trace),
          'capture/evidence.jsonl':lines(evidence),
          'parking-context.json':{'case_id':case,'cell_id':'C276263',
                                  'road_grade_percent':4,'source_kind':'synthetic_cpu_fixture',
                                  'legal_verdict':None},
          'capture/manifest.json':{'extraction_confirmed':True,'frames':600,
                                   'synthetic_diagnostic':True}}
    for name,value in data.items():write(sources/name,value)
    write(sources/'capture/manifest.json',
          {'extraction_confirmed':True,'frames':600,'synthetic_diagnostic':True,
           'sources':{'road.xodr':sha(HERE/'sloped-curb-road.xodr'),
                      'trace.jsonl':sha(sources/'trace.jsonl')}})
    spec={'files':{'capture/native/frames.jsonl':lines(captures),
                   'capture/recorder_info.txt':'Synthetic parked-lamp CPU diagnostic; no Native physical or legal acceptance.\nCreate 10: vehicle.lamp.diagnostic (0)\n'},
          'graphs':graphs,
          'videos':[{'path':name+'.mkv','frames':600,
                     'width':1920 if name=='overview' else 1280,
                     'height':1080 if name=='overview' else 720,
                     'fps':20,'color':'black'} for name in VIEWS]}
    spec_path=diagnostic/'fixture-spec.json';write(spec_path,spec)
    repo=Path.cwd()
    recipe={'format':'worker-fixture-recipe',
            'generator':{'source':str(spec_path.relative_to(repo)),'sha256':sha(spec_path)},
            'sources':[{'path':str(path.relative_to(sources)),
                        'source':str(path.relative_to(repo)),'sha256':sha(path)}
                       for path in sorted(sources.rglob('*')) if path.is_file()]}
    write(diagnostic/'fixture-recipe.json',recipe)
    return {'case_id':case,'recipe_sha256':sha(diagnostic/'fixture-recipe.json'),
            'source_files':len(recipe['sources']),'spec_bytes':spec_path.stat().st_size}

if __name__=='__main__':
    print(json.dumps([build(s) for s in ('probe_a','probe_b')],indent=2))
