"""Create bounded textual synthetic compatibility sources for both exact cases."""
import copy
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
AID=ROOT.name
VIEWS=('overview','approach','reference_corner','driver_reference')
COUNT=600


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def lines(values):return ''.join(json.dumps(v,separators=(',',':'))+'\n' for v in values)


def build(short):
    example=json.loads((REPO/'runtime/fixtures/example.json').read_text())
    ef=example['files']
    source=json.loads(ef['capture/evidence.jsonl'].splitlines()[0])
    ego=copy.deepcopy(next(x for x in example['graphs'][0]['nodes'] if x['id']=='ego'))
    for key in list(ego['attributes']):
        if key not in ('vertex','sem_class','entity_id','threedbbox','forward','special_class'):
            ego['attributes'].pop(key)
    source['original_observations']={
        'world_settings':{'no_rendering_mode':False},'rgb_sensors':[],
        'frame':0,'time_s':0.0,'devices':[],
        'participants':[source['original_observations']['participants'][0]],
        'relations':[],'participant_inventory':'synthetic diagnostic',
        'map_context':{'declared_public_way_road_ids':[]}}
    for key in list(source):
        if key not in ('original_frame','replay_frame','actor_id','recording_time_s',
                       'replay_simulation_time_s','ego','world','original_observations'):
            source.pop(key)
    for key in list(source['ego']):
        if key not in ('position_m','heading_deg','speed_mps','speed_provenance','body_vertices_m'):
            source['ego'].pop(key)
    participant=source['original_observations']['participants'][0]
    keep=('actor_id','blueprint','position_m','heading_deg','velocity_mps','speed_mps','body_vertices_m')
    source['original_observations']['participants']=[{k:participant[k] for k in keep}]
    step=.17 if short=='reference' else .14
    speed=step*20
    evidence=[];frames=[];trace=[];mapping=[];motion=[];graphs=[]
    for i in range(COUNT):
        frame=1000+i;t=round(i*.05,4);x=round(i*step,4)
        body=[[round(x+dx,4),dy,dz] for dx in (-2.,2.) for dy in (-1.,1.) for dz in (0.,2.)]
        motion.append({'source_kind':'synthetic_native_sample','native_frame':frame,
                       'time_s':t,'position_m':[x,0.,0.],
                       'velocity_mps':[speed,0.,0.],
                       'acceleration_mps2':[0.,0.,0.],
                       'yaw_deg':0.})
        mapping.append({'video_frame':i,'native_frame':frame,'carla_frame':frame,'time_s':t})
        trace.append({'frame':frame,'time_s':t,'position':{'x':x,'y':0.,'z':0.},
                      'position_m':[x,0.,0.],'heading_deg':0.,
                      'speed_mps':speed,'speed_mph':speed/.44704,
                      'velocity_mps':[speed,0.,0.],'control':{}})
        event=copy.deepcopy(source)
        event.update(original_frame=frame,replay_frame=frame,actor_id=205,
                     recording_time_s=t,replay_simulation_time_s=t)
        event['ego'].update(position_m=[x,0.,0.],speed_mps=speed,
                            speed_provenance='synthetic_native_sample',body_vertices_m=body)
        event['original_observations'].update(frame=frame,time_s=t)
        p=event['original_observations']['participants'][0]
        p.update(position_m=[x,0.,0.],speed_mps=speed,
                 velocity_mps=[speed,0.,0.],body_vertices_m=body)
        evidence.append(event)
        frames.append({'frame':frame,'simulation_time':t,'abstract':None,'base':None,
                       'nodes':1,'edges':0,
                       'adapter_graph':f'graphs/base/{frame:08d}.adapter.json'})
        node=copy.deepcopy(ego)
        node['attributes']['vertex']=[x,0.,0.]
        node['attributes']['threedbbox']=body
        graphs.append({'path':f'capture/native/graphs/base/{frame:08d}.adapter.json',
                       'attributes':{'frame':frame,
                                     'observed_evidence':copy.deepcopy(event['original_observations'])},
                       'nodes':[node],'edges':[]})
    context={'source_kind':'synthetic_native_sample',
             'camera_sources':{v:v+'.mkv' for v in VIEWS},
             'case_id':AID+'__'+short,
             'camera_pose_and_optics':json.loads((ROOT/f'native/selected-{short}-primary-construction.json').read_text())['recording_description']['channels'],
             'driver_facing_pixels_reviewed':False,
             'driver_attention_to_operation':None,'legal_verdict':None}
    files={'road.xodr':ef['road.xodr'],
           'capture/recorder_info.txt':'Version: 1\nMap: OpenDriveMap\nCreate 205: vehicle.tesla.model3 (0) at (0, 0, 0)\n',
           'trace.jsonl':lines(trace),'video_frames.jsonl':lines(mapping),
           'native-ego-frames.jsonl':lines(motion),
           'native-driving-context.json':json.dumps(context,separators=(',',':'))+'\n',
           'capture/evidence.jsonl':lines(evidence),
           'capture/native/frames.jsonl':lines(frames)}
    manifest={'status':'draft','acquisition':'diagnostic_fixture','case_id':AID+'__'+short,
              'source_run':'synthetic diagnostic only','map':'OpenDriveMap',
              'frames':COUNT,'required_observations':[],'extraction_confirmed':True,
              'sources':{n:hashlib.sha256(files[n].encode()).hexdigest()
                         for n in ('road.xodr','trace.jsonl')},
              'complete_driving_lanes':False}
    files['capture/manifest.json']=json.dumps(manifest,separators=(',',':'))+'\n'
    videos=[{'path':v+'.mkv','frames':COUNT,'width':1920 if v=='overview' else 1280,
             'height':1080 if v=='overview' else 720,'fps':20,
             'color':'black'} for v in VIEWS]
    spec={'files':files,'graphs':graphs,'videos':videos}
    path=ROOT/f'diagnostic-{short}.json'
    path.write_text(json.dumps(spec,separators=(',',':'))+'\n')
    recipe={'format':'worker-fixture-recipe',
            'sources':[{'path':'fixture-assignment.json',
                        'source':str((REPO/'inputs'/AID/'assignment.json').relative_to(REPO)),
                        'sha256':sha(REPO/'inputs'/AID/'assignment.json')}],
            'generator':{'source':str(path.relative_to(REPO)),'sha256':sha(path)}}
    (ROOT/f'fixture-recipe-{short}.json').write_text(json.dumps(recipe,indent=2)+'\n')
    print(short,path.stat().st_size,sha(path))


if __name__=='__main__':
    for name in ('reference','contrast'):build(name)
