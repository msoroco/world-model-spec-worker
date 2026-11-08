"""Bind C135709 Native actor/video records and reviewed stand frames to saved rows."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

import check

RAW=('native-map-readback.json','native-raw-actors.jsonl','video_frames.jsonl',
     'stand-review.jsonl','native-capture-report.json')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def finite(x):return type(x) in (int,float) and math.isfinite(x)
def require(ok,message):
    if not ok:raise ValueError(message)

def prepare(bundle,raw,output,synthetic_cpu=False):
    bundle,raw,output=Path(bundle),Path(raw),Path(output)
    checked=check.check(bundle);cfg=read(bundle/'config.json')
    require(not output.exists(),'C135709 saved output must be fresh')
    hashes={name:sha(raw/name) for name in RAW}
    map_readback=read(raw/RAW[0]);actors=rows(raw/RAW[1])
    video=rows(raw/RAW[2]);reviews=rows(raw/RAW[3]);report=read(raw/RAW[4])
    request=rows(bundle/'requested-tracks.jsonl')
    kind='synthetic_cpu' if synthetic_cpu else 'original_native'
    require(len(actors)==len(video)==len(reviews)==len(request)==240,
            'C135709 raw coverage differs')
    require(map_readback.get('road_sha256')==cfg['road_sha256'] and
            isinstance(map_readback.get('native_map_sha256'),str) and
            len(map_readback['native_map_sha256'])==64 and
            map_readback.get('stand_lane_readback')=={
                '-1':{'road_id':517,'lane_id':-1},
                '-2':{'road_id':517,'lane_id':-2}} and
            map_readback.get('authored_sign_text')=='TAXICAB STAND' and
            type(map_readback.get('ego_actor_id')) is int and
            all(map_readback.get(k) is False for k in
                ('official_designation_verified','appropriate_signing_verified',
                 'stand_geometry_verified','actual_parking_verified',
                 'non_taxicab_actual_use_verified',
                 'passenger_loading_exception_verified')) and
            map_readback.get('legal_verdict') is None,
            'C135709 raw map/stand readback differs')
    phase_readback={}
    for phase in ('approach','parked','prestand','hold_before_stand'):
        matching=[x for x in request if x['phase']==phase]
        if matching:
            phase_readback[phase]={'road_id':517,
                'lane_id':matching[len(matching)//2]['lane_id']}
    require(map_readback.get('phase_lane_readback')==phase_readback,
            'C135709 raw phase readback differs')
    require(report.get('case_id')==checked['case_id'] and
            report.get('candidate_id')==checked['candidate_id'] and
            report.get('config_sha256')==sha(bundle/'config.json') and
            report.get('requested_frames')==report.get('observed_frames')==240 and
            report.get('error') is None and report.get('accepted') is False and
            report.get('delivery_ready') is False,
            'C135709 raw capture report differs')
    media={}
    if not synthetic_cpu:
        for name in ('forward.mkv','overview.mkv'):
            path=raw/name;media[name]=sha(path)
            proc=subprocess.run(['ffprobe','-v','error','-count_frames',
                '-select_streams','v:0','-show_entries','stream=codec_name,nb_read_frames',
                '-of','json',str(path)],capture_output=True,text=True,check=True,timeout=120)
            streams=json.loads(proc.stdout).get('streams',[])
            require(len(streams)==1 and streams[0].get('codec_name')=='ffv1' and
                    streams[0].get('nb_read_frames')=='240',
                    'C135709 Native video coverage differs')
    first=actors[0].get('native_frame');actor_id=map_readback['ego_actor_id']
    require(type(first) is int,'C135709 Native frame absent')
    saved_rows=[];camera=[];review_rows=[];previous_t=None
    for i,(row,frame,review,req) in enumerate(zip(actors,video,reviews,request)):
        native=first+i;t=row.get('time_s')
        require(row.get('frame')==i and row.get('native_frame')==native and
                row.get('source_kind')==kind and
                row.get('requested_phase')==req['phase'] and
                row.get('requested_road_id')==517 and
                row.get('requested_lane_id')==req['lane_id'] and
                row.get('observed_road_id')==517 and
                row.get('observed_lane_id') in (-1,-2) and
                finite(t) and abs(t-(i+1)/20)<.005 and
                (previous_t is None or abs(t-previous_t-.05)<.005) and
                all(row.get(k) is False for k in
                    ('official_designation_verified','actual_parking_verified',
                     'non_taxicab_actual_use_verified',
                     'passenger_loading_exception_verified')) and
                row.get('legal_verdict') is None,
                f'C135709 raw actor/frame differs at {i}')
        require(frame.get('video_frame')==i and frame.get('native_frame')==native and
                finite(frame.get('time_s')) and abs(frame['time_s']-t)<1e-6 and
                review.get('frame')==i and review.get('native_frame')==native and
                finite(review.get('time_s')) and abs(review['time_s']-t)<1e-6 and
                review.get('source_kind')==kind and
                review.get('review_provenance')==
                    ('synthetic_cpu' if synthetic_cpu else 'human_frame_review') and
                review.get('video_sha256')==media.get('forward.mkv','synthetic_cpu') and
                type(review.get('stand_sign_visible')) is bool and
                type(review.get('stand_polygon_visible')) is bool and
                finite(review.get('reviewed_ego_y_m')),
                f'C135709 raw video/review join differs at {i}')
        ego=row.get('ego',{});center=ego.get('center_native_xyz_m')
        velocity=ego.get('velocity_native_xyz_mps');body=ego.get('body_native_xyz_m')
        require(ego.get('actor_id')==actor_id and
                ego.get('blueprint')=='vehicle.tesla.model3' and
                isinstance(center,list) and len(center)==3 and all(map(finite,center)) and
                isinstance(velocity,list) and len(velocity)==3 and all(map(finite,velocity)) and
                isinstance(body,list) and len(body)==8 and all(
                    isinstance(p,list) and len(p)==3 and all(map(finite,p)) for p in body) and
                finite(ego.get('yaw_deg')) and finite(ego.get('speed_mps')) and
                ego['speed_mps']>=0 and
                abs(math.sqrt(sum(v*v for v in velocity))-ego['speed_mps'])<.01,
                f'C135709 raw ego pose differs at {i}')
        saved_rows.append({'frame':i,'native_frame':native,'time_s':(i+1)/20,
            'source_kind':kind,'witness':req['witness'],'candidate_id':cfg['candidate_id'],
            'road_id':517,'lane_id':row['observed_lane_id'],
            'phase':req['phase'],'ego_actor_id':actor_id,
            'ego_blueprint':ego['blueprint'],'ego_x_m':center[0],
            'ego_y_m':center[1],'ego_heading_deg':ego['yaw_deg'],
            'ego_speed_mps':ego['speed_mps'],
            'ego_body_xy_m':[[p[0],p[1]] for p in body],
            'actual_parking_observed':False})
        camera.append({'frame':i,'camera_frame':native,'time_s':(i+1)/20,
            'source_kind':kind,'stand_sign_visible':review['stand_sign_visible'],
            'stand_polygon_visible':review['stand_polygon_visible']})
        review_rows.append({'frame':i,'native_frame':native,'time_s':(i+1)/20,
            'source_kind':kind,'reviewed_ego_y_m':review['reviewed_ego_y_m'],
            'review_provenance':review['review_provenance']})
        previous_t=t
    output.mkdir(parents=True)
    for name,items in (('native-observed.jsonl',saved_rows),
                       ('camera-frames.jsonl',camera),('stand-review.jsonl',review_rows)):
        (output/name).write_text(''.join(json.dumps(x,allow_nan=False)+'\n' for x in items))
    (output/'stand-readback.json').write_text(json.dumps({
        'source_kind':kind,'road_sha256':cfg['road_sha256'],
        'request_sha256':cfg['tracks_sha256'],
        'review_sha256':sha(output/'stand-review.jsonl'),
        'native_map_sha256':map_readback['native_map_sha256'],
        'ego_actor_id':actor_id,'stand_polygon_x_m':[50,75],
        'stand_polygon_y_m':[-8.25,-3.5],'sign_text':'TAXICAB STAND',
        'review_provenance':'synthetic_cpu' if synthetic_cpu else 'human_frame_review',
        'official_designation_verified':False,'sign_appropriateness_verified':False,
        'non_taxicab_actual_use_verified':False,
        'passenger_loading_exception_verified':False,
        'actual_parking_observed':False,'legal_verdict':None},indent=2)+'\n')
    receipt={'format':'c135709-raw-to-saved-v1','case_id':cfg['case_id'],
        'candidate_id':cfg['candidate_id'],'source_kind':kind,'raw_hashes':hashes,
        'media_hashes':media,'saved_hashes':{name:sha(output/name) for name in
            ('native-observed.jsonl','camera-frames.jsonl','stand-review.jsonl',
             'stand-readback.json')},'original_native_observed':not synthetic_cpu,
        'official_designation_verified':False,'legal_verdict':None,
        'delivery_ready':False}
    (output/'preparation-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--raw-folder',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--synthetic-cpu',action='store_true');a=p.parse_args()
    print(json.dumps(prepare(a.bundle,a.raw_folder,a.output_dir,a.synthetic_cpu),indent=2))
