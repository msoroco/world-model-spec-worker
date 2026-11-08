"""Generate labelled synthetic raw controls from retained connected saved observations."""
import argparse
import hashlib
import json
import math
from pathlib import Path

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def write(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')
def write_rows(path,items):Path(path).write_text(''.join(json.dumps(x)+'\n' for x in items))

def generate(bundle,output):
    bundle=Path(bundle);output=Path(output);output.mkdir(parents=True,exist_ok=False)
    cfg=json.loads((bundle/'connected-config.json').read_text())
    saved=bundle/'connected-saved';observed=rows(saved/'native-observed.jsonl')
    cameras=rows(saved/'camera-frames.jsonl');requests=rows(bundle/'connected-requested-tracks.jsonl')
    actor_id=131364;actors=[];video=[];review=[]
    for i,(row,frame,request) in enumerate(zip(observed,cameras,requests)):
        t=row['time_s'];native=1000+i;speed=row['ego_speed_mps']
        heading=request['ego_heading_deg'];h=math.radians(heading)
        body=[[x,y,z] for z in (0,1) for x,y in row['ego_body_xy_m']]
        actors.append({'frame':i,'native_frame':native,'time_s':t,'source_kind':'synthetic_cpu',
            'requested_phase':request['phase'],'requested_road_id':request['road_id'],
            'requested_lane_id':request['lane_id'],'observed_road_id':row['road_id'],
            'observed_lane_id':row['lane_id'],'ego':{'actor_id':actor_id,
            'blueprint':'vehicle.tesla.model3',
            'center_native_xyz_m':[row['ego_x_m'],row['ego_y_m'],0],
            'yaw_deg':heading,'velocity_native_xyz_mps':
                [speed*math.cos(h),speed*math.sin(h),0],
            'speed_mps':speed,'body_native_xyz_m':body},
            'physical_roundabout_verified':False,'actual_left_exit_verified':False,
            'legal_verdict':None})
        video.append({'video_frame':i,'native_frame':native,'time_s':t})
        review.append({'frame':i,'native_frame':native,'time_s':t,
            'source_kind':'synthetic_cpu','review_provenance':'synthetic_cpu',
            'video_sha256':'synthetic_cpu','left_lane_visible':frame['left_lane_visible']})
    phases={'entry':10,'circulation':11,'exit':12}
    if cfg['candidate_id']=='fallback3':phases={'entry':10}
    write(output/'native-map-readback.json',{'road_sha256':cfg['road_sha256'],
        'native_map_sha256':'0'*64,'phase_lane_readback':{phase:{'road_id':road,
        'lane_id':cfg['requested_lane_id']} for phase,road in phases.items()},
        'arc_lane_readback':{str(lane):{'road_id':11,'lane_id':lane}
            for lane in (-1,-2)},'ego_actor_id':actor_id,
        'physical_roundabout_verified':False,'lane_allocation_reviewed':False,
        'actual_left_exit_verified':False,'legal_verdict':None})
    write_rows(output/'native-raw-actors.jsonl',actors)
    write_rows(output/'video_frames.jsonl',video)
    write_rows(output/'left-lane-review.jsonl',review)
    write(output/'native-capture-report.json',{'case_id':cfg['case_id'],
        'candidate_id':cfg['candidate_id'],'connected_config_sha256':sha(bundle/'connected-config.json'),
        'requested_frames':240,'observed_frames':240,'error':None,'accepted':False,
        'delivery_ready':False})
    return output

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
    print(generate(a.bundle,a.output_dir))
