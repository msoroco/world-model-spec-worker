"""Convert source-bound C132497 Native capture records to unaccepted saved observations."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

import check

RAW = ('native-map-readback.json', 'native-raw-actors.jsonl',
       'video_frames.jsonl', 'right-lane-review.jsonl', 'native-capture-report.json')

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text())
def rows(path): return [json.loads(s) for s in Path(path).read_text().splitlines()]
def finite(value): return type(value) in (int, float) and math.isfinite(value)
def require(condition, message):
    if not condition: raise ValueError(message)

def prepare(bundle, raw, output, synthetic_cpu=False):
    bundle, raw, output = Path(bundle), Path(raw), Path(output)
    checked = check.check(bundle)
    cfg = read(bundle/'config.json')
    require(not output.exists(), 'C132497 saved output must be fresh')
    hashes = {name: sha(raw/name) for name in RAW}
    readback, report = read(raw/RAW[0]), read(raw/RAW[-1])
    actors, video, reviews = (rows(raw/name) for name in RAW[1:4])
    requests = rows(bundle/'requested-tracks.jsonl')
    kind = 'synthetic_cpu' if synthetic_cpu else 'original_native'
    require(len(actors)==len(video)==len(reviews)==len(requests)==240,
            'C132497 raw frame coverage differs')
    require(readback.get('road_sha256')==cfg['road_sha256'] and
            isinstance(readback.get('native_map_sha256'),str) and
            len(readback['native_map_sha256'])==64 and
            all(readback.get('arc_lane_readback',{}).get(str(lane))==
                {'road_id':21,'lane_id':lane} for lane in (-1,-2)) and
            all(readback.get('phase_lane_readback',{}).get(phase)==
                {'road_id':road,'lane_id':cfg['requested_lane_id']}
                for phase,road in (('entry',20),('circulation',21),('exit',22))
                if candidate_phase(requests,phase)) and
            type(readback.get('ego_actor_id')) is int and
            readback.get('physical_roundabout_verified') is False and
            readback.get('lane_allocation_verified') is False and
            readback.get('actual_right_exit_verified') is False and
            readback.get('legal_verdict') is None,
            'C132497 raw map or actor readback differs')
    require(report.get('case_id')==checked['case_id'] and
            report.get('candidate_id')==checked['candidate_id'] and
            report.get('config_sha256')==sha(bundle/'config.json') and
            report.get('requested_frames')==report.get('observed_frames')==240 and
            report.get('error') is None and report.get('accepted') is False and
            report.get('delivery_ready') is False,
            'C132497 raw capture report differs')
    media = {}
    if not synthetic_cpu:
        dimensions={'overview.mkv':[1920,1080],
                    'approach.mkv':[1280,720],
                    'reference_corner.mkv':[1280,720],
                    'driver_reference.mkv':[1280,720]}
        for name,size in dimensions.items():
            path=raw/name; media[name]=sha(path)
            proc=subprocess.run(['ffprobe','-v','error','-count_frames',
                '-select_streams','v:0','-show_entries',
                'stream=codec_name,nb_read_frames,width,height,r_frame_rate',
                '-of','json',str(path)],capture_output=True,text=True,check=True,timeout=120)
            streams=json.loads(proc.stdout).get('streams',[])
            require(len(streams)==1 and streams[0].get('codec_name')=='ffv1' and
                    streams[0].get('nb_read_frames')=='240' and
                    [streams[0].get('width'),streams[0].get('height')]==size and
                    streams[0].get('r_frame_rate')=='20/1',
                    'C132497 Native video codec, rate, size or frame count differs')
    first=actors[0].get('native_frame')
    require(type(first) is int,'C132497 native frame identity absent')
    observed=[]; camera=[]; previous_time=None; previous_phase=-1
    phases={20:('entry',0),21:('circulation',1),22:('exit',2)}
    for i,(row,frame,review,request) in enumerate(zip(actors,video,reviews,requests)):
        native=first+i; t=row.get('time_s');road=row.get('observed_road_id')
        require(row.get('frame')==i and row.get('native_frame')==native and
                row.get('source_kind')==kind and request.get('frame')==i and
                row.get('requested_phase')==request['phase'] and
                row.get('requested_road_id')==request['road_id'] and
                row.get('requested_lane_id')==cfg['requested_lane_id'] and
                road in phases and row.get('observed_lane_id')==cfg['requested_lane_id'] and
                finite(t) and abs(t-(i+1)/20)<.005 and
                (previous_time is None or abs(t-previous_time-.05)<.005) and
                row.get('physical_roundabout_verified') is False and
                row.get('actual_right_exit_verified') is False and
                row.get('legal_verdict') is None,
                f'C132497 raw actor join differs at {i}')
        phase,ordinal=phases[road]
        require(ordinal>=previous_phase,'C132497 observed road phases reverse')
        require(frame.get('video_frame')==i and frame.get('native_frame')==native and
                finite(frame.get('time_s')) and abs(frame['time_s']-t)<1e-6 and
                review.get('frame')==i and review.get('native_frame')==native and
                finite(review.get('time_s')) and abs(review['time_s']-t)<1e-6 and
                review.get('source_kind')==kind and
                review.get('review_provenance')==
                    ('synthetic_cpu' if synthetic_cpu else 'human_frame_review') and
                review.get('video_sha256')==media.get('approach.mkv','synthetic_cpu') and
                type(review.get('right_lane_visible')) is bool,
                f'C132497 raw video/review join differs at {i}')
        ego=row.get('ego',{});center=ego.get('center_native_xyz_m')
        velocity=ego.get('velocity_native_xyz_mps');body=ego.get('body_native_xyz_m')
        require(ego.get('actor_id')==readback['ego_actor_id'] and
                ego.get('blueprint')=='vehicle.tesla.model3' and
                isinstance(center,list) and len(center)==3 and all(map(finite,center)) and
                isinstance(velocity,list) and len(velocity)==3 and all(map(finite,velocity)) and
                isinstance(body,list) and len(body)==8 and all(
                    isinstance(p,list) and len(p)==3 and all(map(finite,p)) for p in body) and
                finite(ego.get('yaw_deg')) and finite(ego.get('speed_mps')) and
                ego['speed_mps']>=0 and
                abs(math.sqrt(sum(v*v for v in velocity))-ego['speed_mps'])<.01,
                f'C132497 raw ego pose differs at {i}')
        observed.append({'frame':i,'native_frame':native,'time_s':(i+1)/20,
            'source_kind':kind,'witness':request['witness'],
            'candidate_id':cfg['candidate_id'],'road_id':road,'phase':phase,
            'lane_id':row['observed_lane_id'],'ego_actor_id':ego['actor_id'],
            'ego_blueprint':ego['blueprint'],'ego_x_m':center[0],'ego_y_m':center[1],
            'ego_heading_deg':ego['yaw_deg'],'ego_speed_mps':ego['speed_mps'],
            'ego_body_xy_m':[[p[0],p[1]] for p in body],
            'actual_exit_observed':not synthetic_cpu and road==22})
        camera.append({'frame':i,'camera_frame':native,'time_s':(i+1)/20,
            'source_kind':kind,'right_lane_visible':review['right_lane_visible']})
        previous_time=t;previous_phase=ordinal
    output.mkdir(parents=True)
    for name,items in (('native-observed.jsonl',observed),('camera-frames.jsonl',camera)):
        (output/name).write_text(''.join(json.dumps(x,allow_nan=False)+'\n' for x in items))
    (output/'lane-readback.json').write_text(json.dumps({
        'source_kind':kind,'road_sha256':cfg['road_sha256'],
        'request_sha256':cfg['tracks_sha256'],
        'native_map_sha256':readback['native_map_sha256'],
        'ego_actor_id':readback['ego_actor_id'],
        'review_provenance':'synthetic_cpu' if synthetic_cpu else 'human_frame_review',
        'right_lane_id':-2,'other_lane_id':-1,
        'physical_roundabout_verified':False,'lane_allocation_verified':False,
        'actual_right_exit_verified':False,'legal_verdict':None},indent=2)+'\n')
    receipt={'format':'c132497-raw-to-saved-v1','case_id':cfg['case_id'],
        'candidate_id':cfg['candidate_id'],'source_kind':kind,'raw_hashes':hashes,
        'media_hashes':media,'saved_hashes':{name:sha(output/name) for name in
            ('native-observed.jsonl','camera-frames.jsonl','lane-readback.json')},
        'observed_exit_road_frames':sum(x['road_id']==22 for x in observed),
        'original_native_observed':not synthetic_cpu,
        'physical_roundabout_verified':False,'legal_verdict':None,'delivery_ready':False}
    (output/'preparation-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

def candidate_phase(requests,phase): return any(x['phase']==phase for x in requests)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--raw-folder',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--synthetic-cpu',action='store_true');a=p.parse_args()
    print(json.dumps(prepare(a.bundle,a.raw_folder,a.output_dir,a.synthetic_cpu),indent=2))
