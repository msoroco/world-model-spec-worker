"""CPU diagnostic proof for source binding, four views, and raw geometry."""
import copy
import json
import tempfile
from pathlib import Path

import capture
import measure_raw

ROOT=Path(__file__).resolve().parent


def actor(x,y,speed,actor_id):
    body=[[x+dx,y+dy,z] for dx in (-2.25,2.25)
          for dy in (-.9,.9) for z in (.1,1.7)]
    return {'actor_id':actor_id,'blueprint':'vehicle.tesla.model3',
            'center_native_xyz_m':[x,y,1.0],'yaw_deg':0.0,'speed_mps':speed,
            'velocity_native_xyz_mps':[speed,0,0],
            'body_native_xyz_m':body}


def fixture(track):
    rows=[];frames=[]
    for i,request in enumerate(track):
        rows.append({'frame':i,'native_frame':1000+i,
            'time_s':request['time_s'],'source_kind':'synthetic_native_sample',
            'requested_ego_x_m':request['ego_x_m'],
            'requested_ego_y_m':request['ego_y_m'],
            'requested_lead_x_m':request['lead_x_m'],
            'requested_lead_y_m':request['lead_y_m'],
            'ego':actor(request['ego_x_m'],request['ego_y_m'],request['ego_requested_speed_mps'],1),
            'lead':actor(request['lead_x_m'],request['lead_y_m'],request['lead_requested_speed_mps'],2),
            'ego_control':{'brake':0.0},
            'observed_ego_road_id':210,
            'observed_ego_lane_id':request['ego_lane_id'],
            'observed_lead_road_id':210,
            'observed_lead_lane_id':request['lead_lane_id']})
        frames.append({'video_frame':i,'native_frame':1000+i,
                       'time_s':request['time_s'],
                       'views':list(measure_raw.VIEWS)})
    return rows,frames


def rejected(rows,frames,label):
    try:
        measure_raw.measure(rows,frames)
    except (ValueError,KeyError,TypeError):
        return label
    raise AssertionError('Negative diagnostic was accepted: '+label)


def camera_creation_proof():
    class Blueprint:
        def __init__(self): self.attributes={}
        def set_attribute(self,k,v): self.attributes[k]=v
    class Library:
        def find(self,name):
            assert name=='sensor.camera.rgb'
            return Blueprint()
    class Sensor:
        def listen(self,callback): self.callback=callback
    class World:
        def __init__(self): self.calls=[]
        def spawn_actor(self,bp,transform,attach_to):
            self.calls.append((bp.attributes,transform,attach_to))
            return Sensor()
    class Carla:
        @staticmethod
        def Location(*xyz): return xyz
        @staticmethod
        def Rotation(**rotation): return rotation
        @staticmethod
        def Transform(location,rotation): return (location,rotation)
    class Process:
        pass
    def run(policy):
        world=World();ego=object();owned=[];queues={};logs={};videos={};commands=[]
        def popen(args,**kwargs):
            commands.append(args)
            assert kwargs['stdin'] is not None and kwargs['stderr'] is not None
            return Process()
        with tempfile.TemporaryDirectory() as temporary:
            capture.spawn_source_cameras(Carla,world,Library(),ego,Path(temporary),
                policy,owned,queues,logs,videos,popen=popen)
            for log in logs.values():log.close()
        assert len(world.calls)==len(owned)==len(queues)==len(logs)==len(videos)==len(commands)==4
        assert all(call[2] is ego for call in world.calls)
        assert [call[0]['image_size_x'] for call in world.calls]==['1920','1280','1280','1280']
        assert [call[0]['image_size_y'] for call in world.calls]==['1080','720','720','720']
        assert all(call[0]['sensor_tick']=='0' for call in world.calls)
        assert all('ffv1' in command and '20' in command for command in commands)
        return world.calls[0][1][0][2]
    standard=run('standard');elevated=run('elevated_overview')
    assert elevated-standard==10
    return {'sensors_created_per_policy':4,'overview_elevation_delta_m':10}


def prove():
    positive=[];negative=[]
    cameras=camera_creation_proof()
    for witness in ('reference','contrast'):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            folder=ROOT/'drafts'/witness/candidate
            check=capture.check_bundle(folder)
            assert check['source_bound'] and len(check['camera_views'])==4
            track=measure_raw.read_jsonl(folder/'requested-tracks.jsonl')
            rows,frames=fixture(track)
            result=measure_raw.measure(rows,frames)
            assert result['source_kind']=='synthetic_native_sample'
            assert result['diagnostic_only'] and result['legal_safety_verdict'] is None
            assert result['observed_right_pass_frames']>0
            assert result['minimum_pass_body_surface_gap_m']==(1.95 if witness=='reference' else 1.25)
            assert any(r['time_to_lead_center_s'] is not None for r in result['observations'])
            positive.append({'case':witness,'candidate':candidate,
                'diagnostic_body_gap_m':result['minimum_pass_body_surface_gap_m']})
            altered=copy.deepcopy(frames);altered[30]['views'].remove('reference_corner')
            negative.append(rejected(rows,altered,'missing-camera-'+witness+'-'+candidate))
            altered=copy.deepcopy(rows);altered[70]['ego']['body_native_xyz_m']=[]
            negative.append(rejected(altered,frames,'missing-body-'+witness+'-'+candidate))
            altered=copy.deepcopy(rows)
            for row in altered:
                row['ego']['center_native_xyz_m'][0]-=100
                row['ego']['body_native_xyz_m']=[[
                    p[0]-100,p[1],p[2]]
                    for p in row['ego']['body_native_xyz_m']]
            negative.append(rejected(altered,frames,'no-pass-'+witness+'-'+candidate))
            altered=copy.deepcopy(rows)
            for row in altered:
                dy=-2*(row['ego']['center_native_xyz_m'][1]-row['lead']['center_native_xyz_m'][1])
                row['ego']['center_native_xyz_m'][1]+=dy
                for p in row['ego']['body_native_xyz_m']:
                    p[1]+=dy
            negative.append(rejected(altered,frames,'wrong-side-'+witness+'-'+candidate))
    return {'positive_synthetic_diagnostics':positive,'negative_rejections':negative,
            'camera_creation':cameras,'original_native_observed':False,
            'legal_safety_verdict':None}


if __name__=='__main__':
    print(json.dumps(prove(),sort_keys=True))
