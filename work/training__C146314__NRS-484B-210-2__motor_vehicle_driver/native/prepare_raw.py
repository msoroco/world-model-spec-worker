"""Bind original right-pass raw sources to measured saved observations.

Synthetic mode is a CPU diagnostic and never an original-capture receipt.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

import capture
import measure_raw

RAW=('native-map-readback.json','native-raw-actors.jsonl',
     'video_frames.jsonl','native-capture-report.json')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def require(ok,message):
    if not ok:raise ValueError(message)


def source_actor(actor,expected_id):
    require(actor.get('actor_id')==expected_id and
            actor.get('blueprint')=='vehicle.tesla.model3' and
            len(actor.get('body_native_xyz_m',[]))==8 and
            len(actor.get('center_native_xyz_m',[]))==3 and
            len(actor.get('velocity_native_xyz_mps',[]))==3 and
            all(math.isfinite(float(v)) for p in actor['body_native_xyz_m'] for v in p) and
            math.isfinite(float(actor['yaw_deg'])) and
            abs(math.sqrt(sum(float(v)**2 for v in actor['velocity_native_xyz_mps']))-
                float(actor['speed_mps']))<.01,
            'Original actor identity, body or speed differs')


def media_audit(raw,synthetic):
    if synthetic:return {}
    hashes={}
    for name,width,height,_,_,_,_ in capture.CAMERAS:
        path=raw/(name+'.mkv')
        hashes[path.name]=sha(path)
        process=subprocess.run(['ffprobe','-v','error','-count_frames',
            '-select_streams','v:0','-show_entries',
            'stream=codec_name,width,height,r_frame_rate,nb_read_frames',
            '-of','json',str(path)],capture_output=True,text=True,
            check=True,timeout=180)
        streams=json.loads(process.stdout).get('streams',[])
        require(len(streams)==1 and streams[0].get('codec_name')=='ffv1' and
                streams[0].get('width')==width and streams[0].get('height')==height and
                streams[0].get('r_frame_rate')=='20/1' and
                streams[0].get('nb_read_frames')=='240',
                'Original source camera codec, dimensions or duration differs')
    return hashes


def prepare(bundle,raw,output,synthetic_cpu=False):
    bundle,raw,output=map(Path,(bundle,raw,output))
    checked=capture.check_bundle(bundle)
    cfg=read(bundle/'config.json')
    require(not output.exists(),'Saved output must be fresh')
    source_hashes={name:sha(raw/name) for name in RAW}
    mapping=read(raw/RAW[0]);rows=measure_raw.read_jsonl(raw/RAW[1])
    frames=measure_raw.read_jsonl(raw/RAW[2]);report=read(raw/RAW[3])
    requested=measure_raw.read_jsonl(bundle/'requested-tracks.jsonl')
    kind='synthetic_native_sample' if synthetic_cpu else 'original_native'
    require(len(rows)==len(frames)==len(requested)==240,
            'Raw capture frame coverage differs')
    require(mapping.get('source_kind')==kind and
            mapping.get('road_sha256')==cfg['road_sha256'] and
            len(mapping.get('native_map_sha256',''))==64 and
            mapping.get('driving_lane_readback')=={
                str(n):{'road_id':210,'lane_id':n} for n in (-1,-2)} and
            type(mapping.get('ego_actor_id')) is int and
            type(mapping.get('lead_actor_id')) is int and
            mapping['ego_actor_id']!=mapping['lead_actor_id'] and
            mapping.get('legal_verdict') is None,
            'Original road, map or actor source differs')
    require(report.get('case_id')==checked['case_id'] and
            report.get('candidate_id')==checked['candidate_id'] and
            report.get('config_sha256')==sha(bundle/'config.json') and
            report.get('requested_frames')==report.get('observed_frames')==240 and
            report.get('error') is None and report.get('accepted') is False and
            report.get('delivery_ready') is False and
            report.get('legal_safety_verdict') is None,
            'Original capture attempt report differs')
    previous_time=None
    first_frame=rows[0].get('native_frame')
    require(type(first_frame) is int,'Original frame number missing')
    for i,(row,frame,request) in enumerate(zip(rows,frames,requested)):
        t=row.get('time_s')
        require(row.get('frame')==i and row.get('native_frame')==first_frame+i and
                row.get('source_kind')==kind and
                isinstance(t,(int,float)) and math.isfinite(t) and
                (previous_time is None or abs(t-previous_time-.05)<.005) and
                row.get('requested_ego_x_m')==request['ego_x_m'] and
                row.get('requested_ego_y_m')==request['ego_y_m'] and
                row.get('requested_lead_x_m')==request['lead_x_m'] and
                row.get('requested_lead_y_m')==request['lead_y_m'] and
                row.get('observed_ego_road_id')==210 and
                row.get('observed_lead_road_id')==210 and
                row.get('observed_ego_lane_id') in (-1,-2) and
                row.get('observed_lead_lane_id') in (-1,-2) and
                frame.get('video_frame')==i and
                frame.get('native_frame')==first_frame+i and
                abs(frame.get('time_s',float('inf'))-t)<1e-6 and
                set(frame.get('views',[]))==set(measure_raw.VIEWS),
                f'Original request, actor and four-view join differs at {i}')
        source_actor(row.get('ego',{}),mapping['ego_actor_id'])
        source_actor(row.get('lead',{}),mapping['lead_actor_id'])
        previous_time=t
    media_hashes=media_audit(raw,synthetic_cpu)
    result=measure_raw.measure(rows,frames)
    require(result['source_kind']==kind and
            result['diagnostic_only']==synthetic_cpu and
            result['legal_safety_verdict'] is None,
            'Measured provenance differs')
    output.mkdir(parents=True)
    measured=output/'right-pass-measures.json'
    measured.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    receipt={'format':'c146314-210-2-raw-to-saved-v1',
        'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
        'source_kind':kind,'config_sha256':sha(bundle/'config.json'),
        'raw_hashes':source_hashes,'media_hashes':media_hashes,
        'measures_sha256':sha(measured),
        'original_native_observed':not synthetic_cpu,
        'legal_safety_verdict':None,'delivery_ready':False}
    (output/'preparation-receipt.json').write_text(
        json.dumps(receipt,indent=2,allow_nan=False)+'\n')
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--raw-folder',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--synthetic-cpu',action='store_true')
    a=p.parse_args()
    print(json.dumps(prepare(a.bundle,a.raw_folder,a.output_dir,a.synthetic_cpu),indent=2))
