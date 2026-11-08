"""Convert a source-bound Native attempt and reviewed frames into saved diagnostics."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

import runner
import measure_saved

RAW=('native-map-readback.json','native-raw-actors.jsonl','video_frames.jsonl',
     'roundabout-review.jsonl','native-capture-report.json')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def finite(x):return type(x) in (int,float) and math.isfinite(x)
def fail(condition,message):
    if not condition:raise ValueError(message)

def prepare(bundle,raw,output,synthetic_cpu=False):
    bundle=Path(bundle);raw=Path(raw);output=Path(output)
    checked=runner.check(bundle);cfg=read(bundle/'config.json')
    fail(output!=raw and not output.exists(),'Saved output must be a new directory')
    hashes={name:sha(raw/name) for name in RAW}
    map_row=read(raw/RAW[0]);actors=rows(raw/RAW[1]);video=rows(raw/RAW[2])
    review=rows(raw/RAW[3]);report=read(raw/RAW[4])
    kind='synthetic_cpu' if synthetic_cpu else 'original_native'
    fail(len(actors)==len(video)==len(review)==240,'Raw frame coverage differs')
    fail(map_row.get('road_sha256')==cfg['road_sha256'] and
         map_row.get('island_geometry_sha256')==cfg['island_geometry_sha256'] and
         all(map_row.get('arc_lane_readback',{}).get(str(lane))=={'road_id':1,'lane_id':lane}
             for lane in (-1,-2)) and
         isinstance(map_row.get('native_map_sha256'),str) and len(map_row['native_map_sha256'])==64,
         'Raw map readback differs')
    fail(report.get('case_id')==checked['case_id'] and
         report.get('candidate_id')==checked['candidate_id'] and
         report.get('bundle_config_sha256')==sha(bundle/'config.json') and
         report.get('requested_frames')==report.get('observed_frames')==240 and
         report.get('error') is None and report.get('accepted') is False and
         report.get('delivery_ready') is False,'Raw capture report differs')
    fail(map_row.get('physical_roundabout_verified') is False and
         map_row.get('traffic_control_verified') is False and
         map_row.get('legal_verdict') is None,'Raw map overclaims verification')
    media={}
    if not synthetic_cpu:
        for name in ('forward.mkv','overview.mkv'):
            path=raw/name;media[name]=sha(path)
            probe=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
                '-show_entries','stream=codec_name,nb_read_frames','-of','json',str(path)],
                capture_output=True,text=True,check=True,timeout=120)
            streams=json.loads(probe.stdout).get('streams',[])
            fail(len(streams)==1 and streams[0].get('codec_name')=='ffv1' and
                 streams[0].get('nb_read_frames')=='240','Native video frame coverage differs')
    first=actors[0].get('native_frame')
    fail(type(first) is int,'Raw first Native frame differs')
    actor_id=map_row.get('ego_actor_id');saved=[];frames=[];previous_time=None
    for i,(row,mapping,review_row) in enumerate(zip(actors,video,review)):
        t=row.get('time_s');native=first+i
        fail(row.get('frame')==i and row.get('native_frame')==native and
             row.get('source_kind')==kind and row.get('witness')==cfg['direction_request'] and
             row.get('candidate_id')==cfg['candidate_id'] and
             row.get('observed_road_id')==1 and row.get('observed_lane_id') in (-1,-2) and
             row.get('requested_lane_id') in (-1,-2) and
             finite(t) and abs(t-(i+1)/20)<0.005 and
             (previous_time is None or abs(t-previous_time-0.05)<0.005) and
             row.get('physical_roundabout_verified') is False and
             row.get('traffic_control_verified') is False and row.get('legal_verdict') is None,
             'Raw actor/frame observation differs')
        fail(mapping.get('video_frame')==i and mapping.get('native_frame')==native and
             finite(mapping.get('time_s')) and abs(mapping['time_s']-t)<1e-6 and
             review_row.get('frame')==i and review_row.get('native_frame')==native and
             review_row.get('source_kind')==kind and
             review_row.get('review_provenance')==('synthetic_cpu' if synthetic_cpu else 'human_frame_review') and
             type(review_row.get('roundabout_visible')) is bool and
             review_row.get('video_sha256')==media.get('forward.mkv','synthetic_cpu') and
             finite(review_row.get('time_s')) and abs(review_row['time_s']-t)<1e-6,
             'Raw video and review join differs')
        ego=row.get('ego',{});center=ego.get('center_native_xyz_m');velocity=ego.get('velocity_native_xyz_mps')
        body=ego.get('body_native_xyz_m')
        fail(ego.get('actor_id')==actor_id and ego.get('blueprint')=='vehicle.tesla.model3' and
             isinstance(center,list) and len(center)==3 and all(finite(x) for x in center) and
             isinstance(velocity,list) and len(velocity)==3 and all(finite(x) for x in velocity) and
             isinstance(body,list) and len(body)==8 and
             all(isinstance(point,list) and len(point)==3 and all(finite(x) for x in point) for point in body) and
             finite(ego.get('yaw_deg')) and finite(ego.get('speed_mps')) and ego['speed_mps']>=0 and
             abs(math.sqrt(sum(x*x for x in velocity))-ego['speed_mps'])<0.01,
             'Raw actor identity, body or velocity differs')
        saved.append({'frame':i,'native_frame':native,'time_s':(i+1)/20,
            'source_kind':kind,'witness':cfg['direction_request'],
            'ego_actor_id':actor_id,'ego_blueprint':ego['blueprint'],
            'ego_x_m':center[0],'ego_y_m':center[1],
            'ego_heading_deg':ego['yaw_deg'],'ego_speed_mps':ego['speed_mps'],
            'ego_body_xy_m':[[p[0],p[1]] for p in body],
            'lane_id':row['observed_lane_id']})
        frames.append({'frame':i,'native_frame':native,'camera_frame':native,
            'time_s':(i+1)/20,'source_kind':kind,
            'roundabout_visible':review_row['roundabout_visible']})
        previous_time=t
    readback={'source_kind':kind,'center_xy_m':[0,0],'island_radius_m':15,
        'driving_lane_ids':[-2,-1],'road_sha256':cfg['road_sha256'],
        'native_map_sha256':map_row['native_map_sha256'],
        'review_provenance':'synthetic_cpu' if synthetic_cpu else 'human_frame_review',
        'roundabout_verified':False,'traffic_control_verified':False}
    output.mkdir(parents=True)
    for name,items in (('native-observed.jsonl',saved),('roundabout-frames.jsonl',frames)):
        (output/name).write_text(''.join(json.dumps(x,allow_nan=False)+'\n' for x in items))
    (output/'roundabout-readback.json').write_text(json.dumps(readback,indent=2)+'\n')
    measurement=measure_saved.measure(output)
    receipt={'format':'c234827-lvmc-raw-to-saved-v1','case_id':checked['case_id'],
        'candidate_id':checked['candidate_id'],'source_kind':kind,'raw_hashes':hashes,
        'media_hashes':media,'saved_hashes':measurement['source_hashes'],
        'measurement':measurement,'original_native_observed':not synthetic_cpu,
        'roundabout_verified':False,'traffic_control_verified':False,
        'legal_verdict':None,'delivery_ready':False}
    (output/'preparation-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--raw-folder',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--synthetic-cpu',action='store_true')
    args=parser.parse_args()
    print(json.dumps(prepare(args.bundle,args.raw_folder,args.output_dir,args.synthetic_cpu),indent=2))
