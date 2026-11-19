"""Build explicit synthetic source fixtures for CPU software compatibility only."""
import copy
import hashlib
import json
from pathlib import Path

from recording_contract import ASSIGNMENT

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
FRAMES = 600
NAMES = ('overview', 'approach', 'reference_corner', 'driver_reference')


def dump(value):
    return json.dumps(value, separators=(',', ':'), allow_nan=False)


def lines(rows):
    return ''.join(dump(row)+'\n' for row in rows)


def build(case):
    if case not in ('reference', 'contrast'):
        raise ValueError('Unknown case')
    template = json.loads((REPO/'work/training__C146314__NRS-484B-210-2__motor_vehicle_driver/selected-diagnostics/reference/primary.json').read_text())
    road = template['files']['road.xodr'].replace('C146314 right-pass safety request',
                                                    'C183370 synthetic warned pavement diagnostic')
    polygon = [[-1,-1],[1,-1],[1,1],[-1,1]]
    plan = {'map_name':'synthetic_cpu_fixture','repair_polygon_xy_m':polygon,
            'cases':{'reference':{'requested_pavement_crossing':True},
                     'contrast':{'requested_pavement_crossing':False}}}
    readback = {'plan':plan,'warning_person_actor_id':12,'pavement_road_id':210}
    files = {'road.xodr':road,
             'live-readback.json':json.dumps(readback,indent=2)+'\n',
             'capture/recorder_info.txt':'Create 1: vehicle.tesla.model3 (synthetic diagnostic identity)\n',
             'acquisition-provenance.json':json.dumps({
                 'provenance_kind':'synthetic_fixture','diagnostic_fixture':True,
                 'native_executed':False,'physical_acceptance_claimed':False},indent=2)+'\n',
             'capture-receipt.json':json.dumps({
                 'source_frames':FRAMES,'capture_rate_hz':20,'case':case,
                 'four_cameras':[name+'.mkv' for name in NAMES],
                 'frame_map':'video_frames.jsonl','actor_rows':'native-actors.jsonl',
                 'map':'road.xodr','trace':'trace.jsonl',
                 'source_kind':'synthetic_diagnostic_capture',
                 'physical_completion_claimed':False,'warning_act_verified':False},indent=2)+'\n'}
    mappings=[];actors=[];trace=[];evidence=[];index=[];graphs=[]
    for n in range(FRAMES):
        t=round((n+1)*.05,8)
        x=(-5 if n<300 else 0) if case=='reference' else -5
        y=0 if case=='reference' else 5
        body=[[x+dx,y+dy,z] for z in (0,1) for dx,dy in
              ((-.5,-.5),(.5,-.5),(.5,.5),(-.5,.5))]
        position=[x,y,1]
        mappings.append({'video_frame':n,'carla_frame':n,'native_frame':n,
                         'time_s':t,'synthetic_frame_only':True})
        actors.append({'video_frame':n,'frame':n,'time_s':t,
                       'source_kind':'synthetic_diagnostic_actor_and_map_readback',
                       'warning_person_actor_id':12,
                       'warning_person_type_id':'walker.pedestrian.0001',
                       'warning_person_xyz_m':[2,0,0],
                       'ego_body_vertices_xyz_m':body,
                       'ego_position_xyz_m':position,'ego_yaw_deg':0,
                       'ego_velocity_xyz_mps':[0,0,0], 'ego_speed_mps':0,
                       'ego_road_id':210,'ego_lane_id':-1})
        trace.append({'frame':n,'time_s':t,'position_m':[x,y],
                      'position':dict(zip(('x','y','z'),position)),
                      'heading_deg':0,'speed_mps':0,'speed_mph':0,
                      'velocity_mps':[0,0,0],
                      'speed_provenance':'synthetic_native_sample',
                      'control':{'throttle':0,'brake':0,'steer':0}})
        participant={'actor_id':1,'blueprint':'vehicle.tesla.model3',
                     'body_vertices_m':body,'heading_deg':0,
                     'velocity_mps':[0,0,0],'speed_mps':0,
                     'accel_longitudinal_mps2':0}
        observations={'frame':n,'time_s':t,'participants':[participant],
                      'world_settings':{'no_rendering_mode':False},
                      'rgb_sensors':{name:{'frame':n} for name in NAMES}}
        evidence.append({'original_frame':n,'replay_frame':n,'actor_id':1,
                         'recording_time_s':t,'replay_simulation_time_s':t,
                         'ego':{'position_m':position,'heading_deg':0,
                                'speed_mps':0,'speed_provenance':'synthetic_native_sample',
                                'body_vertices_m':body},
                         'world':{'weather':{'cloudiness':0,'precipitation':0,
                                             'wetness':0,'fog_density':0},
                                  'road_projection':{'road_id':210,'section_id':0,
                                                     'lane_id':-1,'s_m':max(x,0)}},
                         'original_observations':observations})
        graph_path=f'graphs/base/{n:08d}.adapter.json'
        index.append({'frame':n,'time_s':t,'simulation_time':t,'base':graph_path,
                      'adapter_graph':graph_path})
        graphs.append({'path':'capture/native/'+graph_path,
                       'attributes':{'frame':n,'observed_evidence':observations},
                       'nodes':[],'edges':[]})
    files.update({'video_frames.jsonl':lines(mappings),
                  'native-actors.jsonl':lines(actors),
                  'trace.jsonl':lines(trace),
                  'capture/evidence.jsonl':lines(evidence),
                  'capture/native/frames.jsonl':lines(index)})
    files['capture/manifest.json']=json.dumps({
        'extraction_confirmed':True,'frames':FRAMES,
        'acquisition':'synthetic_cpu_fixture','observation_contract_version':2,
        'required_observations':[],
        'sources':{name:hashlib.sha256(files[name].encode()).hexdigest()
                   for name in ('road.xodr','trace.jsonl')}},indent=2)+'\n'
    videos=[{'path':name+'.mkv','frames':FRAMES,'width':width,'height':height,
             'fps':20,'color':color} for name,width,height,color in
            (('overview',1920,1080,'blue'),('approach',1280,720,'green'),
             ('reference_corner',1280,720,'white'),
             ('driver_reference',1280,720,'red'))]
    return {'files':files,'graphs':graphs,'videos':videos}


def write():
    for case in ('reference','contrast'):
        target=PACKAGE/'selected-diagnostics'/case
        target.mkdir(parents=True,exist_ok=True)
        source=target/'primary.json'
        source.write_text(json.dumps(build(case),separators=(',',':'))+'\n')
        checksum=hashlib.sha256(source.read_bytes()).hexdigest()
        recipe={'format':'worker-fixture-recipe',
                'sources':[{'path':'diagnostic-source.json',
                            'source':str(source.relative_to(REPO)), 'sha256':checksum}],
                'generator':{'source':str(source.relative_to(REPO)),'sha256':checksum}}
        (target/'primary-recipe.json').write_text(json.dumps(recipe,indent=2)+'\n')


if __name__=='__main__':
    write()
