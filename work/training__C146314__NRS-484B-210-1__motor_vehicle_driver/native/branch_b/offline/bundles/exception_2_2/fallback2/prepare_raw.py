"""Preserve paragraph (b) Native actor and video observations as saved rows."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from check import check

RAW=('native-map-readback.json','native-raw-actors.jsonl','video_frames.jsonl',
     'frame-review.jsonl','native-capture-report.json')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def finite(value):return type(value) in (int,float) and math.isfinite(value)
def require(ok,message):
    if not ok:raise ValueError(message)


def actor(value,expected_id):
    require(type(value) is dict and value.get('actor_id')==expected_id and
        value.get('blueprint')=='vehicle.tesla.model3',
        'Native vehicle identity/blueprint')
    center=value.get('center_native_xyz_m');velocity=value.get('velocity_native_xyz_mps')
    body=value.get('body_native_xyz_m')
    require(type(center) is list and len(center)==3 and all(map(finite,center)) and
        type(velocity) is list and len(velocity)==3 and all(map(finite,velocity)) and
        type(body) is list and len(body)==8 and
        all(type(p) is list and len(p)==3 and all(map(finite,p)) for p in body) and
        finite(value.get('yaw_deg')) and finite(value.get('speed_mps')) and
        value['speed_mps']>=0 and
        abs(math.sqrt(sum(v*v for v in velocity))-value['speed_mps'])<.01,
        'Native vehicle pose/body/speed')
    xy={(round(p[0],4),round(p[1],4)) for p in body}
    require(len(xy)==4 and all(sum(abs(p[0]-x)<.0001 and abs(p[1]-y)<.0001
        for p in body)==2 for x,y in xy), 'Native eight-vertex body projection')
    xs=[p[0] for p in body];ys=[p[1] for p in body]
    require(3<=max(xs)-min(xs)<=7 and 1.3<=max(ys)-min(ys)<=7 and
        abs((max(xs)+min(xs))/2-center[0])<1 and
        abs((max(ys)+min(ys))/2-center[1])<1,
        'Native body dimensions/center')
    return value


def prepare(bundle,raw,output,synthetic_cpu=False):
    bundle,raw,output=map(Path,(bundle,raw,output))
    checked=check(bundle);cfg=read(bundle/'config.json')
    require(not output.exists(),'saved output must be fresh')
    hashes={name:sha(raw/name) for name in RAW}
    mapping=read(raw/'native-map-readback.json')
    capture=read(raw/'native-capture-report.json')
    observed=rows(raw/'native-raw-actors.jsonl')
    video=rows(raw/'video_frames.jsonl')
    review=rows(raw/'frame-review.jsonl')
    requested=rows(bundle/'requested-tracks.jsonl')
    kind='synthetic_cpu' if synthetic_cpu else 'original_native'
    require(len(observed)==len(video)==len(review)==len(requested)==240,
        'Native frame coverage')
    parked=cfg['parked_vehicle_requested']
    expected_lanes={str(n):{'road_id':211,'lane_id':n} for n in (-2,-1,1,2)}
    require(mapping.get('source_kind')==kind and
        mapping.get('road_sha256')==sha(bundle/'four-lane-pass.xodr') and
        type(mapping.get('native_map_sha256')) is str and
        len(mapping['native_map_sha256'])==64 and
        mapping.get('driving_lane_readback')==expected_lanes and
        mapping.get('four_driving_lanes_verified') is True and
        mapping.get('pavement_condition_verified') is False and
        mapping.get('parked_actor_spawned') is parked and
        type(mapping.get('ego_actor_id')) is int and
        type(mapping.get('lead_actor_id')) is int and
        mapping['ego_actor_id']!=mapping['lead_actor_id'] and
        (type(mapping.get('parked_actor_id')) is int if parked
            else mapping.get('parked_actor_id') is None) and
        mapping.get('legal_verdict') is None,
        'Native map/actor source binding')
    if parked:
        require(mapping['parked_actor_id'] not in
            (mapping['ego_actor_id'],mapping['lead_actor_id']),
            'parked actor distinct identity')
    require(capture.get('case_id')==checked['case_id'] and
        capture.get('candidate_id')==checked['candidate_id'] and
        capture.get('config_sha256')==sha(bundle/'config.json') and
        capture.get('requested_frames')==capture.get('observed_frames')==240 and
        capture.get('error') is None and capture.get('accepted') is False and
        capture.get('delivery_ready') is False and
        capture.get('four_driving_lanes_verified') is True and
        capture.get('parked_actor_spawned') is parked and
        capture.get('legal_verdict') is None,
        'Native unaccepted capture report')
    media={}
    if not synthetic_cpu:
        for name in ('forward.mkv','overview.mkv'):
            media[name]=sha(raw/name)
            probe=subprocess.run(['ffprobe','-v','error','-count_frames',
                '-select_streams','v:0',
                '-show_entries','stream=codec_name,nb_read_frames',
                '-of','json',str(raw/name)],capture_output=True,text=True,
                check=True,timeout=120)
            streams=json.loads(probe.stdout).get('streams',[])
            require(len(streams)==1 and streams[0].get('codec_name')=='ffv1' and
                streams[0].get('nb_read_frames')=='240',
                'original FFV1 video coverage')
    first=observed[0].get('native_frame')
    require(type(first) is int,'first Native frame')
    saved=[];cameras=[];reviews=[];previous_time=None
    for i,(row,frame,view,request) in enumerate(zip(observed,video,review,requested)):
        native=first+i;t=row.get('time_s')
        require(row.get('frame')==i and row.get('native_frame')==native and
            row.get('source_kind')==kind and finite(t) and
            abs(t-(i+1)/20)<.005 and
            (previous_time is None or abs(t-previous_time-.05)<.005) and
            row.get('requested_ego_x_m')==request['ego_x_m'] and
            row.get('requested_ego_y_m')==request['ego_y_m'] and
            row.get('requested_lead_x_m')==request['lead_x_m'] and
            row.get('requested_parked_vehicle') is parked and
            row.get('observed_ego_road_id')==211 and
            row.get('observed_ego_lane_id') in (-1,-2) and
            row.get('observed_lead_road_id')==211 and
            row.get('observed_lead_lane_id') in (-1,-2) and
            row.get('observed_parked_road_id')==(211 if parked else None) and
            row.get('observed_parked_lane_id')==(-2 if parked else None) and
            row.get('four_driving_lanes_verified') is True and
            row.get('pavement_condition_verified') is False and
            row.get('legal_verdict') is None,
            f'Native actor/request join {i}')
        require(frame.get('video_frame')==i and
            frame.get('native_frame')==native and
            finite(frame.get('time_s')) and
            abs(frame['time_s']-t)<1e-6 and
            view.get('frame')==i and view.get('native_frame')==native and
            finite(view.get('time_s')) and abs(view['time_s']-t)<1e-6 and
            view.get('source_kind')==kind and
            view.get('review_provenance')==
                ('synthetic_cpu' if synthetic_cpu else 'human_frame_review') and
            view.get('forward_video_sha256')==media.get('forward.mkv','synthetic_cpu') and
            view.get('overview_video_sha256')==media.get('overview.mkv','synthetic_cpu') and
            type(view.get('parked_pixel_reviewed')) is bool and
            type(view.get('lane_pixel_reviewed')) is bool and
            (type(view.get('parked_vehicle_visible')) is bool
                if view['parked_pixel_reviewed'] else view.get('parked_vehicle_visible') is None) and
            (type(view.get('lane_occupancy_visible')) is bool
                if view['lane_pixel_reviewed'] else view.get('lane_occupancy_visible') is None),
            f'Native video/review join {i}')
        ego=actor(row.get('ego'),mapping['ego_actor_id'])
        lead=actor(row.get('lead'),mapping['lead_actor_id'])
        require(parked or row.get('parked_vehicle') is None,
                f'unexpected parked actor {i}')
        vehicle=actor(row.get('parked_vehicle'),mapping['parked_actor_id']) if parked else None
        require((vehicle is None)==(not parked) and
            (not parked or vehicle['speed_mps']<=.1),
            f'parked vehicle stationary state {i}')
        saved.append({'frame':i,'native_frame':native,'time_s':t,
            'source_kind':kind,'observed_ego_road_id':211,
            'observed_ego_lane_id':row['observed_ego_lane_id'],
            'observed_lead_road_id':211,
            'observed_lead_lane_id':row['observed_lead_lane_id'],
            'observed_parked_road_id':row['observed_parked_road_id'],
            'observed_parked_lane_id':row['observed_parked_lane_id'],
            'ego':ego,'lead':lead,'parked_vehicle':vehicle})
        cameras.append({'frame':i,'native_frame':native,'time_s':t,
            'video_frame':i,'source_kind':kind})
        reviews.append(view)
        previous_time=t
    output.mkdir(parents=True)
    for name,values in (('native-observed.jsonl',saved),
                        ('camera-frames.jsonl',cameras),
                        ('frame-review.jsonl',reviews)):
        (output/name).write_text(''.join(json.dumps(value,allow_nan=False)+'\n'
                                       for value in values))
    receipt={'format':'c146314-paragraph-b-raw-to-saved-v1',
        'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
        'source_kind':kind,'config_sha256':sha(bundle/'config.json'),
        'raw_hashes':hashes,'media_hashes':media,
        'saved_hashes':{name:sha(output/name) for name in
            ('native-observed.jsonl','camera-frames.jsonl','frame-review.jsonl')},
        'original_native_observed':not synthetic_cpu,
        'human_condition_reviewed':all(r['parked_pixel_reviewed'] and
            r['lane_pixel_reviewed'] for r in reviews),
        'pavement_condition_verified':False,'legal_verdict':None,
        'delivery_ready':False}
    (output/'preparation-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--raw-folder',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--synthetic-cpu',action='store_true')
    a=p.parse_args()
    print(json.dumps(prepare(a.bundle,a.raw_folder,a.output_dir,a.synthetic_cpu)))
