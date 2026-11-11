"""Create explicitly synthetic raw records for the C132497 converter proof."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path): return [json.loads(s) for s in Path(path).read_text().splitlines()]
def write(path,value): Path(path).write_text(json.dumps(value,indent=2)+'\n')
def write_rows(path,items): Path(path).write_text(''.join(json.dumps(x)+'\n' for x in items))

def generate(bundle,output):
    bundle,output=Path(bundle),Path(output)
    output.mkdir(parents=True,exist_ok=False)
    cfg=json.loads((bundle/'config.json').read_text())
    saved=bundle/'saved'
    observed=rows(saved/'native-observed.jsonl')
    cameras=rows(saved/'camera-frames.jsonl')
    requests=rows(bundle/'requested-tracks.jsonl')
    actors=[];video=[];reviews=[];actor_id=132497
    for i,(row,frame,request) in enumerate(zip(observed,cameras,requests)):
        t=row['time_s'];native=1000+i;speed=row['ego_speed_mps']
        heading=math.radians(row['ego_heading_deg'])
        body=[[x,y,z] for z in (0,1) for x,y in row['ego_body_xy_m']]
        actors.append({'frame':i,'native_frame':native,'time_s':t,
            'source_kind':'synthetic_cpu','requested_phase':request['phase'],
            'requested_road_id':request['road_id'],
            'requested_lane_id':request['lane_id'],
            'observed_road_id':row['road_id'],'observed_lane_id':row['lane_id'],
            'ego':{'actor_id':actor_id,'blueprint':'vehicle.tesla.model3',
                'center_native_xyz_m':[row['ego_x_m'],row['ego_y_m'],0],
                'yaw_deg':row['ego_heading_deg'],
                'velocity_native_xyz_mps':
                    [speed*math.cos(heading),speed*math.sin(heading),0],
                'speed_mps':speed,'body_native_xyz_m':body},
            'physical_roundabout_verified':False,
            'actual_right_exit_verified':False,'legal_verdict':None})
        video.append({'video_frame':i,'native_frame':native,'time_s':t})
        reviews.append({'frame':i,'native_frame':native,'time_s':t,
            'source_kind':'synthetic_cpu','review_provenance':'synthetic_cpu',
            'video_sha256':'synthetic_cpu',
            'right_lane_visible':frame['right_lane_visible']})
    phases={phase:{'road_id':road,'lane_id':cfg['requested_lane_id']}
            for phase,road in (('entry',20),('circulation',21),('exit',22))
            if any(x['phase']==phase for x in requests)}
    write(output/'native-map-readback.json',{
        'road_sha256':cfg['road_sha256'],'native_map_sha256':'0'*64,
        'arc_lane_readback':{str(lane):{'road_id':21,'lane_id':lane}
            for lane in (-1,-2)},
        'loop_lane_readback':{str(lane):{'road_id':23,'lane_id':lane}
            for lane in (-1,-2)},'phase_lane_readback':phases,
        'ego_actor_id':actor_id,'physical_roundabout_verified':False,
        'lane_allocation_verified':False,'actual_right_exit_verified':False,
        'legal_verdict':None})
    write_rows(output/'native-raw-actors.jsonl',actors)
    write_rows(output/'video_frames.jsonl',video)
    write_rows(output/'right-lane-review.jsonl',reviews)
    shutil.copyfile(bundle/'controller-intention.json',output/'controller-intention.json')
    write(output/'native-capture-report.json',{
        'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
        'config_sha256':sha(bundle/'config.json'),
        'controller_intention_sha256':sha(output/'controller-intention.json'),
        'requested_frames':240,'observed_frames':240,'error':None,
        'accepted':False,'delivery_ready':False})
    return output

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
    print(generate(a.bundle,a.output_dir))
