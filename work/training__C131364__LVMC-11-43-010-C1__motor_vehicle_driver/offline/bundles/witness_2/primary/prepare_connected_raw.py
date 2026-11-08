"""Bind captured connected-route actors and human-reviewed video to saved observations."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

import runner
import measure_exit_saved

RAW=('native-map-readback.json','native-raw-actors.jsonl','video_frames.jsonl',
     'left-lane-review.jsonl','native-capture-report.json')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def finite(x):return type(x) in (int,float) and math.isfinite(x)
def require(ok,message):
    if not ok:raise ValueError(message)

def prepare(bundle,raw,output,synthetic_cpu=False):
    bundle=Path(bundle);raw=Path(raw);output=Path(output)
    checked=runner.check(bundle);cfg=read(bundle/'connected-config.json')
    require(not output.exists() and output!=raw,'C131364 output must be fresh')
    hashes={name:sha(raw/name) for name in RAW}
    readback=read(raw/RAW[0]);actors=rows(raw/RAW[1]);video=rows(raw/RAW[2])
    reviews=rows(raw/RAW[3]);report=read(raw/RAW[4])
    kind='synthetic_cpu' if synthetic_cpu else 'original_native'
    require(len(actors)==len(video)==len(reviews)==240,'C131364 raw coverage differs')
    require(readback.get('road_sha256')==cfg['road_sha256'] and
        isinstance(readback.get('native_map_sha256'),str) and
        len(readback['native_map_sha256'])==64 and
        all(readback.get('arc_lane_readback',{}).get(str(lane))==
            {'road_id':11,'lane_id':lane} for lane in (-1,-2)) and
        all(readback.get('phase_lane_readback',{}).get(phase)==
            {'road_id':road,'lane_id':cfg['requested_lane_id']}
            for phase,road in (('entry',10),('circulation',11),('exit',12))
            if cfg['candidate_id']!='fallback3' or phase=='entry') and
        readback.get('physical_roundabout_verified') is False and
        readback.get('lane_allocation_reviewed') is False and
        readback.get('actual_left_exit_verified') is False and
        readback.get('legal_verdict') is None,
        'C131364 raw Native map/readback differs')
    require(report.get('case_id')==checked['case_id'] and
        report.get('candidate_id')==checked['candidate_id'] and
        report.get('connected_config_sha256')==sha(bundle/'connected-config.json') and
        report.get('requested_frames')==report.get('observed_frames')==240 and
        report.get('error') is None and report.get('accepted') is False and
        report.get('delivery_ready') is False,
        'C131364 raw capture report differs')
    media={}
    if not synthetic_cpu:
        for name in ('forward.mkv','overview.mkv'):
            path=raw/name;media[name]=sha(path)
            p=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
                '-show_entries','stream=codec_name,nb_read_frames','-of','json',str(path)],
                capture_output=True,text=True,check=True,timeout=120)
            streams=json.loads(p.stdout).get('streams',[])
            require(len(streams)==1 and streams[0].get('codec_name')=='ffv1' and
                    streams[0].get('nb_read_frames')=='240',
                    'C131364 Native video coverage differs')
    first=actors[0].get('native_frame');actor_id=readback.get('ego_actor_id')
    require(type(first) is int and type(actor_id) is int,'C131364 Native actor absent')
    observed=[];camera=[];previous_t=None
    for i,(row,frame,review) in enumerate(zip(actors,video,reviews)):
        native=first+i;t=row.get('time_s');road=row.get('observed_road_id')
        require(row.get('frame')==i and row.get('native_frame')==native and
            row.get('source_kind')==kind and road in (10,11,12) and
            row.get('observed_lane_id')==cfg['requested_lane_id'] and
            row.get('requested_lane_id')==cfg['requested_lane_id'] and
            row.get('requested_road_id') in (10,11,12) and
            row.get('requested_phase') in ('entry','circulation','exit') and
            finite(t) and abs(t-(i+1)/20)<.005 and
            (previous_t is None or abs(t-previous_t-.05)<.005) and
            row.get('physical_roundabout_verified') is False and
            row.get('actual_left_exit_verified') is False and
            row.get('legal_verdict') is None,
            'C131364 raw actor/frame differs')
        require(frame.get('video_frame')==i and frame.get('native_frame')==native and
            finite(frame.get('time_s')) and abs(frame['time_s']-t)<1e-6 and
            review.get('frame')==i and review.get('native_frame')==native and
            finite(review.get('time_s')) and abs(review['time_s']-t)<1e-6 and
            review.get('source_kind')==kind and
            review.get('review_provenance')==('synthetic_cpu' if synthetic_cpu else 'human_frame_review') and
            review.get('video_sha256')==media.get('forward.mkv','synthetic_cpu') and
            type(review.get('left_lane_visible')) is bool,
            'C131364 raw video/review join differs')
        ego=row.get('ego',{});center=ego.get('center_native_xyz_m');velocity=ego.get('velocity_native_xyz_mps')
        body=ego.get('body_native_xyz_m')
        require(ego.get('actor_id')==actor_id and ego.get('blueprint')=='vehicle.tesla.model3' and
            isinstance(center,list) and len(center)==3 and all(finite(x) for x in center) and
            isinstance(velocity,list) and len(velocity)==3 and all(finite(x) for x in velocity) and
            isinstance(body,list) and len(body)==8 and all(isinstance(p,list) and
                len(p)==3 and all(finite(x) for x in p) for p in body) and
            finite(ego.get('yaw_deg')) and finite(ego.get('speed_mps')) and
            ego['speed_mps']>=0 and abs(math.sqrt(sum(x*x for x in velocity))-ego['speed_mps'])<.01,
            'C131364 raw ego pose/identity differs')
        phase={10:'entry',11:'circulation',12:'exit'}[road]
        observed.append({'frame':i,'native_frame':native,'time_s':(i+1)/20,
            'source_kind':kind,'witness':cfg['case_id'].removeprefix(cfg['assignment_id']+'__'),
            'candidate_id':cfg['candidate_id'],'road_id':road,'phase':phase,
            'lane_id':row['observed_lane_id'],'ego_actor_id':actor_id,
            'ego_blueprint':ego['blueprint'],'ego_x_m':center[0],'ego_y_m':center[1],
            'ego_heading_deg':ego['yaw_deg'],'ego_speed_mps':ego['speed_mps'],
            'ego_body_xy_m':[[p[0],p[1]] for p in body],
            'actual_exit_observed':road==12 if not synthetic_cpu else False})
        camera.append({'frame':i,'camera_frame':native,'time_s':(i+1)/20,
            'source_kind':kind,'left_lane_visible':review['left_lane_visible']})
        previous_t=t
    saved_readback={'source_kind':kind,'road_sha256':cfg['road_sha256'],
        'request_sha256':cfg['tracks_sha256'],'native_map_sha256':readback['native_map_sha256'],
        'ego_actor_id':actor_id,'review_provenance':
            'synthetic_cpu' if synthetic_cpu else 'human_frame_review',
        'physical_roundabout_verified':False}
    output.mkdir(parents=True)
    for name,items in (('native-observed.jsonl',observed),('camera-frames.jsonl',camera)):
        (output/name).write_text(''.join(json.dumps(x,allow_nan=False)+'\n' for x in items))
    (output/'lane-readback.json').write_text(json.dumps(saved_readback,indent=2)+'\n')
    measurement=measure_exit_saved.measure(bundle,output)
    receipt={'format':'c131364-connected-raw-to-saved-v1','case_id':cfg['case_id'],
        'candidate_id':cfg['candidate_id'],'source_kind':kind,'raw_hashes':hashes,
        'media_hashes':media,'measurement':measurement,
        'physical_roundabout_verified':False,'legal_verdict':None,'delivery_ready':False}
    (output/'preparation-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--raw-folder',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--synthetic-cpu',action='store_true');a=p.parse_args()
    print(json.dumps(prepare(a.bundle,a.raw_folder,a.output_dir,a.synthetic_cpu),indent=2))
