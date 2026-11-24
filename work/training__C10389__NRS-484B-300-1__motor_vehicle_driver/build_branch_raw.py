"""Create clearly synthetic raw-shaped sources for branch CPU conversion."""
import hashlib
import json
from pathlib import Path
from branch_requests import HERE

BASE=HERE/'cases/branch-requests'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,obj):path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def rows(path,items):path.write_text(''.join(json.dumps(item,sort_keys=True)+'\n' for item in items))

def body(x):
    return [[x+dx,-1.75+dy,z] for dx in (-2.2,2.2) for dy in (-0.9,0.9) for z in (0.2,1.6)]


def build(suffix,candidate,output):
    bundle=BASE/(suffix if candidate=='primary' else suffix+'-'+candidate)
    cfg=json.loads((bundle/'config.json').read_text());requests=[json.loads(x) for x in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
    if len(requests)!=600:raise ValueError('Short authored source request')
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    signal=suffix.startswith('signal_');landmark={'id':'3892' if signal else '3891','road_id':389,'s_m':50.0,'type':'1000001' if signal else '206'}
    write(output/'native-map-readback.json',{'source_kind':'synthetic_cpu','road_sha256':cfg['road_sha256'],
        'native_map_sha256':'1'*64,'lane_readback':{str(x):{'road_id':389,'lane_id':-1,'lane_type':'driving'} for x in (20,45,55)},
        'stop_landmark_readback':landmark,'stop_landmark_verified':True,'ego_actor_id':101,
        'signal_actor_id':201 if signal else None,'signal_state_observed':('TrafficLightState.'+cfg['requested_signal_aspect'].capitalize()) if signal else None,
        'official_placement_verified':False,'police_direction_verified':False,'legal_verdict':None})
    actors=[];videos=[];reviews=[]
    for i,request in enumerate(requests):
        native=1000+i;t=request['time_s'];x=request['requested_ego_x_m'];speed=request['requested_speed_mps']
        ego={'actor_id':101,'blueprint':'vehicle.tesla.model3','center_native_xyz_m':[x,-1.75,1],
             'velocity_native_xyz_mps':[speed,0,0],'speed_mps':speed,'body_native_xyz_m':body(x)}
        actors.append({'frame':i,'native_frame':native,'time_s':t,'source_kind':'synthetic_cpu',
            'requested_ego_x_m':x,'requested_speed_mps':speed,'ego':ego,
            'observed_road_id':389,'observed_lane_id':-1,
            'signal_state_observed':('TrafficLightState.'+cfg['requested_signal_aspect'].capitalize()) if signal else None,
            'officer_actor':{'actor_id':301,'blueprint':'walker.pedestrian.0001','center_native_xyz_m':[47,-6,0.5],
                             'body_native_xyz_m':body(47)} if not signal and cfg['requested_officer_direction']=='proceed' else None,
            'requested_officer_direction':cfg.get('requested_officer_direction'),
            'official_placement_verified':False,'police_direction_verified':False,'legal_verdict':None})
        videos.append({'video_frame':i,'native_frame':native,'time_s':t})
        reviews.append({'frame':i,'native_frame':native,'time_s':t,'source_kind':'synthetic_cpu',
                        'review_provenance':'synthetic_cpu','device_face_pixel_reviewed':False,
                        'approach_area_pixel_reviewed':False})
    rows(output/'native-raw-actors.jsonl',actors);rows(output/'video_frames.jsonl',videos);rows(output/'frame-review.jsonl',reviews)
    write(output/'native-capture-report.json',{'case_id':cfg['case_id'],'candidate_id':candidate,
        'config_sha256':sha(bundle/'config.json'),'requested_frames':600,'observed_frames':600,
        'restoration':None,'error':None,'accepted':False,'delivery_ready':False,
        'original_native_observed':False,'official_placement_verified':False,
        'police_direction_verified':False,'legal_verdict':None})
    return {'case_id':cfg['case_id'],'candidate_id':candidate,'source_kind':'synthetic_cpu',
            'file_sha256':{f.name:sha(f) for f in output.iterdir() if f.is_file()}}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--suffix',required=True);parser.add_argument('--candidate',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();print(json.dumps(build(args.suffix,args.candidate,args.output),sort_keys=True))
