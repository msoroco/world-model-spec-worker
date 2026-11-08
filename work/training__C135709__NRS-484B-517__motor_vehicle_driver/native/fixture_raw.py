"""Generate labelled synthetic C135709 raw capture controls from saved fixtures."""
import argparse
import hashlib
import json
import math
from pathlib import Path

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def write_rows(path,items):path.write_text(''.join(json.dumps(x)+'\n' for x in items))

def generate(bundle,output):
    bundle,output=Path(bundle),Path(output)
    output.mkdir(parents=True,exist_ok=False)
    cfg=json.loads((bundle/'config.json').read_text())
    saved=bundle/'saved'
    observed=rows(saved/'native-observed.jsonl')
    cameras=rows(saved/'camera-frames.jsonl')
    reviews=rows(saved/'stand-review.jsonl')
    request=rows(bundle/'requested-tracks.jsonl')
    actor_id=135709;actors=[];video=[];review_rows=[]
    for i,(row,frame,review,req) in enumerate(zip(observed,cameras,reviews,request)):
        t=row['time_s'];native=1000+i;speed=row['ego_speed_mps']
        body=[[x,y,z] for z in (0,1) for x,y in row['ego_body_xy_m']]
        actors.append({'frame':i,'native_frame':native,'time_s':t,
            'source_kind':'synthetic_cpu','requested_phase':req['phase'],
            'requested_road_id':517,'requested_lane_id':req['lane_id'],
            'observed_road_id':517,'observed_lane_id':row['lane_id'],
            'ego':{'actor_id':actor_id,'blueprint':'vehicle.tesla.model3',
                'center_native_xyz_m':[row['ego_x_m'],row['ego_y_m'],0],
                'yaw_deg':0,'velocity_native_xyz_mps':[speed,0,0],
                'speed_mps':speed,'body_native_xyz_m':body},
            'official_designation_verified':False,
            'actual_parking_verified':False,
            'non_taxicab_actual_use_verified':False,
            'passenger_loading_exception_verified':False,'legal_verdict':None})
        video.append({'video_frame':i,'native_frame':native,'time_s':t})
        review_rows.append({'frame':i,'native_frame':native,'time_s':t,
            'source_kind':'synthetic_cpu','review_provenance':'synthetic_cpu',
            'video_sha256':'synthetic_cpu',
            'stand_sign_visible':frame['stand_sign_visible'],
            'stand_polygon_visible':frame['stand_polygon_visible'],
            'reviewed_ego_y_m':review['reviewed_ego_y_m']})
    phase_readback={}
    for phase in ('approach','parked','prestand','hold_before_stand'):
        matching=[x for x in request if x['phase']==phase]
        if matching:phase_readback[phase]={'road_id':517,
            'lane_id':matching[len(matching)//2]['lane_id']}
    write(output/'native-map-readback.json',{
        'road_sha256':cfg['road_sha256'],'native_map_sha256':'0'*64,
        'stand_lane_readback':{'-1':{'road_id':517,'lane_id':-1},
            '-2':{'road_id':517,'lane_id':-2}},
        'phase_lane_readback':phase_readback,
        'authored_sign_text':'TAXICAB STAND','ego_actor_id':actor_id,
        'official_designation_verified':False,
        'appropriate_signing_verified':False,
        'stand_geometry_verified':False,'actual_parking_verified':False,
        'non_taxicab_actual_use_verified':False,
        'passenger_loading_exception_verified':False,'legal_verdict':None})
    write_rows(output/'native-raw-actors.jsonl',actors)
    write_rows(output/'video_frames.jsonl',video)
    write_rows(output/'stand-review.jsonl',review_rows)
    write(output/'native-capture-report.json',{
        'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
        'config_sha256':sha(bundle/'config.json'),
        'requested_frames':240,'observed_frames':240,'error':None,
        'accepted':False,'delivery_ready':False})
    return output

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
    print(generate(a.bundle,a.output_dir))
