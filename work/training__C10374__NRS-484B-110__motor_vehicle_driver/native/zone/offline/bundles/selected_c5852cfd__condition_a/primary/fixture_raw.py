"""Raw-shaped synthetic CPU diagnostic; never an original zone observation."""
import argparse
import hashlib
import json
from pathlib import Path

from build import put,put_rows,sha


def vehicle(x,y,v):
    corners=((x-2,y-.9),(x-2,y+.9),(x+2,y+.9),(x+2,y-.9))
    return {'actor_id':101,'blueprint':'vehicle.tesla.model3',
        'center_native_xyz_m':[x,y,1.5],
        'velocity_native_xyz_mps':[v,0,0], 'speed_mps':v,
        'body_native_xyz_m':[[round(px,6),round(py,6),z]
                              for z in (.5,2.5) for px,py in corners]}


def build(bundle,output):
    bundle,output=map(Path,(bundle,output))
    if output.exists():raise ValueError('raw output must be fresh')
    cfg=json.loads((bundle/'config.json').read_text())
    requests=[json.loads(line) for line in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
    markers=[{'actor_id':200+i,'blueprint':'static.prop.streetbarrier',
              'xyz_m':[x,y,.2]} for i,(x,y) in enumerate(
                  ((40,-3.4),(40,-.1),(60,-3.4),(60,-.1)))]
    put(output/'native-map-readback.json',{
        'source_kind':'synthetic_cpu','road_sha256':sha(bundle/'alley-zone.xodr'),
        'native_map_sha256':hashlib.sha256(b'synthetic-c10374-road374').hexdigest(),
        'lane_readback':{str(lane):{'road_id':374,'lane_id':lane} for lane in (-1,-2)},
        'ego_actor_id':101,'generated_alley_lanes_verified':True,
        'native_zone_delimiters':markers,'zone_rectangle_xy_m':cfg['zone_rectangle_xy_m'],
        'physical_zone_designation_verified':False,'legal_verdict':None})
    actors=[];videos=[];reviews=[]
    for i,request in enumerate(requests):
        x,y=request['requested_ego_x_m'],request['requested_ego_y_m']
        previous=requests[i-1]['requested_ego_x_m'] if i else x
        speed=round((x-previous)*20,6)
        native=i+1000;t=request['time_s']
        actors.append({'frame':i,'native_frame':native,'time_s':t,
            'source_kind':'synthetic_cpu','requested_ego_x_m':x,'requested_ego_y_m':y,
            'ego':vehicle(x,y,speed), 'observed_road_id':374,
            'observed_lane_id':request['requested_lane_id'],
            'physical_zone_designation_verified':False,
            'actual_zone_overlap_observed':False,'legal_verdict':None})
        videos.append({'video_frame':i,'native_frame':native,'time_s':t})
        reviews.append({'frame':i,'native_frame':native,'time_s':t,
            'source_kind':'synthetic_cpu','review_provenance':'synthetic_cpu',
            'forward_video_sha256':'synthetic_cpu','overview_video_sha256':'synthetic_cpu',
            'zone_boundary_pixel_reviewed':False,
            'zone_boundary_visible':None})
    put_rows(output/'native-raw-actors.jsonl',actors)
    put_rows(output/'video_frames.jsonl',videos)
    put_rows(output/'frame-review.jsonl',reviews)
    put(output/'native-capture-report.json',{
        'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
        'config_sha256':sha(bundle/'config.json'),
        'requested_frames':240,'observed_frames':240,
        'restoration':{'synthetic_cpu':True},'error':None,'accepted':False,
        'generated_alley_lanes_verified':True,
        'physical_zone_designation_verified':False,
        'legal_verdict':None,'delivery_ready':False})
    return {'source_kind':'synthetic_cpu','frames':240}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();print(json.dumps(build(a.bundle,a.output_dir)))
