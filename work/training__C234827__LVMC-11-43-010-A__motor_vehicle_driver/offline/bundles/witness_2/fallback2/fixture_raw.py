"""Construct explicit synthetic raw-file controls from retained saved diagnostics."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def write(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')
def linewrite(path,items):Path(path).write_text(''.join(json.dumps(x)+'\n' for x in items))

def generate(bundle,folder):
    bundle=Path(bundle);folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
    cfg=json.loads((bundle/'config.json').read_text());witness=cfg['direction_request']
    saved=bundle/'saved-fixtures'/witness
    observations=rows(saved/'native-observed.jsonl')
    camera=rows(saved/'roundabout-frames.jsonl')
    actors=[];video=[];review=[];actor_id=1701
    for row,frame in zip(observations,camera):
        i=row['frame'];t=row['time_s'];native=1000+i
        body=[[x,y,z] for z in (0,1) for x,y in row['ego_body_xy_m']]
        h=math.radians(row['ego_heading_deg']);speed=row['ego_speed_mps']
        actors.append({'frame':i,'native_frame':native,'time_s':t,'source_kind':'synthetic_cpu',
            'witness':witness,'candidate_id':cfg['candidate_id'],
            'requested_lane_id':row['lane_id'],'observed_road_id':1,
            'observed_lane_id':row['lane_id'],'ego':{'actor_id':actor_id,
            'blueprint':'vehicle.tesla.model3',
            'center_native_xyz_m':[row['ego_x_m'],row['ego_y_m'],0],
            'yaw_deg':row['ego_heading_deg'],
            'velocity_native_xyz_mps':[speed*math.cos(h),speed*math.sin(h),0],
            'speed_mps':speed,'body_native_xyz_m':body},
            'physical_roundabout_verified':False,'traffic_control_verified':False,
            'legal_verdict':None})
        video.append({'video_frame':i,'native_frame':native,'time_s':t})
        review.append({'frame':i,'native_frame':native,'time_s':t,
            'source_kind':'synthetic_cpu','review_provenance':'synthetic_cpu',
            'video_sha256':'synthetic_cpu','roundabout_visible':frame['roundabout_visible']})
    write(folder/'native-map-readback.json',{'road_sha256':cfg['road_sha256'],
        'island_geometry_sha256':cfg['island_geometry_sha256'],
        'native_map_sha256':'0'*64,
        'arc_lane_readback':{str(lane):{'road_id':1,'lane_id':lane} for lane in (-1,-2)},
        'ego_actor_id':actor_id,'physical_roundabout_verified':False,
        'traffic_control_verified':False,'legal_verdict':None})
    linewrite(folder/'native-raw-actors.jsonl',actors)
    linewrite(folder/'video_frames.jsonl',video)
    linewrite(folder/'roundabout-review.jsonl',review)
    write(folder/'native-capture-report.json',{'case_id':cfg['case_id'],
        'candidate_id':cfg['candidate_id'],'bundle_config_sha256':sha(bundle/'config.json'),
        'requested_frames':240,'observed_frames':240,'error':None,'accepted':False,
        'delivery_ready':False})
    return folder

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
    print(generate(a.bundle,a.output_dir))
