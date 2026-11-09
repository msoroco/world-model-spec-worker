"""Source-bound raw preparation and moving footprint/zone overlap measurement."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from check import check

RAW=('native-map-readback.json','native-raw-actors.jsonl','video_frames.jsonl',
     'frame-review.jsonl','native-capture-report.json')
SAVED=('native-observed.jsonl','camera-frames.jsonl','frame-review.jsonl')
MARKERS=((40,-3.4),(40,-.1),(60,-3.4),(60,-.1))


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(line) for line in Path(path).read_text().splitlines()]
def require(ok,message):
    if not ok:raise ValueError(message)
def finite(value):return type(value) in (int,float) and math.isfinite(value)


def media_hashes(raw,synthetic):
    if synthetic:return {}
    result={}
    for name in ('forward.mkv','overview.mkv'):
        result[name]=sha(raw/name)
        process=subprocess.run(['ffprobe','-v','error','-count_frames',
            '-select_streams','v:0','-show_entries','stream=codec_name,nb_read_frames',
            '-of','json',str(raw/name)],capture_output=True,text=True,check=True,timeout=120)
        streams=json.loads(process.stdout).get('streams',[])
        require(len(streams)==1 and streams[0].get('codec_name')=='ffv1' and
                streams[0].get('nb_read_frames')=='240','original FFV1 frames')
    return result


def validate_vehicle(ego,actor_id):
    require(type(ego) is dict and ego.get('actor_id')==actor_id and
            ego.get('blueprint')=='vehicle.tesla.model3','ego identity')
    center=ego.get('center_native_xyz_m');velocity=ego.get('velocity_native_xyz_mps')
    body=ego.get('body_native_xyz_m')
    require(type(center) is list and len(center)==3 and all(map(finite,center)) and
            type(velocity) is list and len(velocity)==3 and all(map(finite,velocity)) and
            finite(ego.get('speed_mps')) and ego['speed_mps']>=0 and
            abs(math.sqrt(sum(v*v for v in velocity))-ego['speed_mps'])<.01 and
            type(body) is list and len(body)==8 and
            all(type(p) is list and len(p)==3 and all(map(finite,p)) for p in body),
            'finite ego pose/body/speed')
    xs=[p[0] for p in body];ys=[p[1] for p in body]
    require(3<=max(xs)-min(xs)<=7 and 1.3<=max(ys)-min(ys)<=7 and
            abs((max(xs)+min(xs))/2-center[0])<1 and
            abs((max(ys)+min(ys))/2-center[1])<1,
            'ego body geometry')


def prepare(bundle,raw,output,synthetic=False):
    bundle,raw,output=map(Path,(bundle,raw,output))
    checked=check(bundle);cfg=read(bundle/'config.json')
    require(not output.exists(),'saved output must be fresh')
    hashes={name:sha(raw/name) for name in RAW}
    mapping=read(raw/RAW[0]);report=read(raw/RAW[-1])
    actors=rows(raw/RAW[1]);videos=rows(raw/RAW[2]);reviews=rows(raw/RAW[3])
    requested=rows(bundle/'requested-tracks.jsonl')
    kind='synthetic_cpu' if synthetic else 'original_native'
    require(len(actors)==len(videos)==len(reviews)==len(requested)==240,
            '240 raw joins')
    markers=mapping.get('native_zone_delimiters')
    require(mapping.get('source_kind')==kind and
            mapping.get('road_sha256')==sha(bundle/'alley-zone.xodr') and
            type(mapping.get('native_map_sha256')) is str and
            len(mapping['native_map_sha256'])==64 and
            mapping.get('lane_readback')=={
                str(lane):{'road_id':374,'lane_id':lane} for lane in (-1,-2)} and
            mapping.get('generated_alley_lanes_verified') is True and
            mapping.get('zone_rectangle_xy_m')==cfg['zone_rectangle_xy_m'] and
            type(mapping.get('ego_actor_id')) is int and
            type(markers) is list and len(markers)==4 and
            len({m.get('actor_id') for m in markers})==4 and
            all(type(m.get('actor_id')) is int and
                type(m.get('blueprint')) is str and
                ('bollard' in m['blueprint'] or 'streetbarrier' in m['blueprint']) and
                type(m.get('xyz_m')) is list and len(m['xyz_m'])==3 and
                all(map(finite,m['xyz_m'])) and
                abs(m['xyz_m'][0]-MARKERS[i][0])<.5 and
                abs(m['xyz_m'][1]-MARKERS[i][1])<.5
                for i,m in enumerate(markers)) and
            mapping.get('physical_zone_designation_verified') is False and
            mapping.get('legal_verdict') is None,'generated road and delimiter binding')
    require(report.get('case_id')==checked['case_id'] and
            report.get('candidate_id')==checked['candidate_id'] and
            report.get('config_sha256')==sha(bundle/'config.json') and
            report.get('requested_frames')==report.get('observed_frames')==240 and
            report.get('error') is None and report.get('accepted') is False and
            report.get('delivery_ready') is False and
            report.get('generated_alley_lanes_verified') is True and
            report.get('physical_zone_designation_verified') is False and
            report.get('legal_verdict') is None,'unaccepted capture report')
    media=media_hashes(raw,synthetic)
    first=actors[0].get('native_frame')
    require(type(first) is int,'first Native frame')
    observed=[];camera=[]
    for i,(row,video,review,request) in enumerate(zip(actors,videos,reviews,requested)):
        native=first+i;t=row.get('time_s')
        require(row.get('frame')==i and row.get('native_frame')==native and
                row.get('source_kind')==kind and finite(t) and
                abs(t-(i+1)/20)<.005 and
                row.get('requested_ego_x_m')==request['requested_ego_x_m'] and
                row.get('requested_ego_y_m')==request['requested_ego_y_m'] and
                row.get('observed_road_id')==374 and
                row.get('observed_lane_id')==request['requested_lane_id'] and
                row.get('physical_zone_designation_verified') is False and
                row.get('actual_zone_overlap_observed') is False and
                row.get('legal_verdict') is None,f'actor/request join {i}')
        validate_vehicle(row.get('ego'),mapping['ego_actor_id'])
        require(video.get('video_frame')==i and video.get('native_frame')==native and
                finite(video.get('time_s')) and abs(video['time_s']-t)<1e-6 and
                review.get('frame')==i and review.get('native_frame')==native and
                finite(review.get('time_s')) and abs(review['time_s']-t)<1e-6 and
                review.get('source_kind')==kind and
                review.get('review_provenance')==(
                    'synthetic_cpu' if synthetic else 'human_frame_review') and
                review.get('forward_video_sha256')==media.get('forward.mkv','synthetic_cpu') and
                review.get('overview_video_sha256')==media.get('overview.mkv','synthetic_cpu') and
                type(review.get('zone_boundary_pixel_reviewed')) is bool and
                (type(review.get('zone_boundary_visible')) is bool
                 if review['zone_boundary_pixel_reviewed'] else
                 review.get('zone_boundary_visible') is None),f'video/review join {i}')
        observed.append({'frame':i,'native_frame':native,'time_s':t,
                         'source_kind':kind,'ego':row['ego'],
                         'observed_lane_id':row['observed_lane_id']})
        camera.append({'frame':i,'native_frame':native,'video_frame':i,
                       'time_s':t,'source_kind':kind})
    output.mkdir(parents=True)
    for name,data in zip(SAVED,(observed,camera,reviews)):
        (output/name).write_text(''.join(json.dumps(item,allow_nan=False)+'\n' for item in data))
    receipt={'format':'c10374-zone-raw-to-saved-v1',
        'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
        'source_kind':kind,'config_sha256':sha(bundle/'config.json'),
        'raw_hashes':hashes,'media_hashes':media,
        'saved_hashes':{name:sha(output/name) for name in SAVED},
        'original_native_observed':not synthetic,
        'physical_zone_designation_verified':False,
        'legal_verdict':None,'delivery_ready':False}
    (output/'preparation-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


def measure(bundle,saved):
    bundle,saved=map(Path,(bundle,saved));check(bundle)
    cfg=read(bundle/'config.json');receipt=read(saved/'preparation-receipt.json')
    observations,cameras,reviews=(rows(saved/name) for name in SAVED)
    require(receipt.get('config_sha256')==sha(bundle/'config.json') and
            receipt.get('source_kind') in ('synthetic_cpu','original_native') and
            receipt.get('original_native_observed')==(receipt['source_kind']=='original_native') and
            receipt.get('physical_zone_designation_verified') is False and
            receipt.get('legal_verdict') is None and receipt.get('delivery_ready') is False and
            all(receipt['saved_hashes'][name]==sha(saved/name) for name in SAVED) and
            len(observations)==len(cameras)==len(reviews)==240,'prepared source and joins')
    xmin,xmax,ymin,ymax=cfg['zone_rectangle_xy_m']
    moving_overlap=reviewed=visible=0
    first_overlap=None;last_overlap=None
    for i,(row,cam,review) in enumerate(zip(observations,cameras,reviews)):
        require(row['frame']==cam['frame']==review['frame']==i and
                row['native_frame']==cam['native_frame']==review['native_frame'] and
                row['source_kind']==cam['source_kind']==review['source_kind']==receipt['source_kind'],
                f'prepared frame {i}')
        body=row['ego']['body_native_xyz_m'];xs=[p[0] for p in body];ys=[p[1] for p in body]
        overlap=max(xs)>=xmin and min(xs)<=xmax and max(ys)>=ymin and min(ys)<=ymax
        if overlap and row['ego']['speed_mps']>.1:
            moving_overlap+=1
            if first_overlap is None:first_overlap=i
            last_overlap=i
        reviewed+=int(review['zone_boundary_pixel_reviewed'])
        visible+=int(review['zone_boundary_pixel_reviewed'] and
                     review['zone_boundary_visible'] is True)
    return {'format':'c10374-zone-prepared-measurement-v1',
        'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
        'source_kind':receipt['source_kind'],
        'requested_zone_route':cfg['requested_zone_route'],
        'moving_body_rectangle_overlap_frames':moving_overlap,
        'first_moving_overlap_frame':first_overlap,
        'last_moving_overlap_frame':last_overlap,
        'reviewed_boundary_frames':reviewed,
        'reviewed_visible_boundary_frames':visible,
        'authored_rectangle_is_designated_zone':False,
        'original_native_observed':receipt['original_native_observed'],
        'legal_verdict':None,'delivery_ready':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--raw-folder',type=Path);p.add_argument('--saved-folder',type=Path,required=True)
    p.add_argument('--synthetic-cpu',action='store_true');a=p.parse_args()
    if a.raw_folder:print(json.dumps(prepare(a.bundle,a.raw_folder,a.saved_folder,a.synthetic_cpu)))
    else:print(json.dumps(measure(a.bundle,a.saved_folder)))
