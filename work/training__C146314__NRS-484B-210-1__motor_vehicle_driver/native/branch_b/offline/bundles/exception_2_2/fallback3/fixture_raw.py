"""Create raw-shaped synthetic CPU observations for paragraph (b) preparation."""
import argparse
import hashlib
import json
from pathlib import Path

from build import sha, put, put_rows


def actor(actor_id, x, y, speed):
    corners=[(x-2,y-.9),(x-2,y+.9),(x+2,y+.9),(x+2,y-.9)]
    return {'actor_id':actor_id,'blueprint':'vehicle.tesla.model3',
        'center_native_xyz_m':[x,y,1.5],'yaw_deg':0,
        'velocity_native_xyz_mps':[speed,0,0],'speed_mps':speed,
        'body_native_xyz_m':[[round(px,6),round(py,6),z]
            for z in (.5,2.5) for px,py in corners]}


def build(bundle,output):
    bundle=Path(bundle);output=Path(output)
    if output.exists():raise ValueError('raw output must be fresh')
    cfg=json.loads((bundle/'config.json').read_text())
    requests=[json.loads(s) for s in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
    saved=[json.loads(s) for s in (bundle/'saved/native-observed.jsonl').read_text().splitlines()]
    if len(requests)!=240 or len(saved)!=240:raise ValueError('synthetic source count')
    parked=cfg['parked_vehicle_requested']
    put(output/'native-map-readback.json',{
        'source_kind':'synthetic_cpu','road_sha256':sha(bundle/'four-lane-pass.xodr'),
        'native_map_sha256':hashlib.sha256(b'synthetic-paragraph-b-road-211').hexdigest(),
        'driving_lane_readback':{str(n):{'road_id':211,'lane_id':n}
            for n in (-2,-1,1,2)},
        'ego_actor_id':101,'lead_actor_id':102,
        'parked_actor_id':103 if parked else None,
        'four_driving_lanes_verified':True,
        'pavement_condition_verified':False,
        'parked_actor_spawned':parked,'legal_verdict':None})
    actors=[];videos=[];reviews=[]
    for i,(request,row) in enumerate(zip(requests,saved)):
        t=request['time_s'];native=i+1000
        ex,ey=row['ego_center_xy_m'];lx,ly=row['lead_center_xy_m']
        actors.append({'frame':i,'native_frame':native,'time_s':t,
            'source_kind':'synthetic_cpu','requested_ego_x_m':request['ego_x_m'],
            'requested_ego_y_m':request['ego_y_m'],
            'requested_lead_x_m':request['lead_x_m'],
            'requested_parked_vehicle':parked,
            'observed_ego_road_id':211,'observed_ego_lane_id':row['ego_lane_id'],
            'observed_lead_road_id':211,'observed_lead_lane_id':-1,
            'observed_parked_road_id':211 if parked else None,
            'observed_parked_lane_id':-2 if parked else None,
            'ego':actor(101,ex,ey,0 if cfg['stop_x_m'] is not None and ex>=45
                        else cfg['requested_ego_speed_mps']),
            'lead':actor(102,lx,ly,4),
            'parked_vehicle':actor(103,55,-6.8,0) if parked else None,
            'four_driving_lanes_verified':True,
            'pavement_condition_verified':False,'legal_verdict':None})
        videos.append({'video_frame':i,'native_frame':native,'time_s':t})
        reviews.append({'frame':i,'native_frame':native,'time_s':t,
            'source_kind':'synthetic_cpu','review_provenance':'synthetic_cpu',
            'forward_video_sha256':'synthetic_cpu',
            'overview_video_sha256':'synthetic_cpu',
            'parked_pixel_reviewed':False,'lane_pixel_reviewed':False,
            'parked_vehicle_visible':None,'lane_occupancy_visible':None})
    put_rows(output/'native-raw-actors.jsonl',actors)
    put_rows(output/'video_frames.jsonl',videos)
    put_rows(output/'frame-review.jsonl',reviews)
    put(output/'native-capture-report.json',{
        'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
        'config_sha256':sha(bundle/'config.json'),
        'requested_frames':240,'observed_frames':240,
        'restoration':{'synthetic_cpu':True},'error':None,'accepted':False,
        'four_driving_lanes_verified':True,
        'pavement_condition_verified':False,
        'parked_actor_spawned':parked,
        'legal_verdict':None,'delivery_ready':False})
    return {'source_kind':'synthetic_cpu','frames':240,'parked_actor':parked}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
    print(json.dumps(build(a.bundle,a.output_dir)))
