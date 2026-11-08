"""Measure source-bound raw-to-saved right-pass geometry without a legal verdict."""
import argparse
import hashlib
import json
import math
from pathlib import Path

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text())
def rows(path): return [json.loads(x) for x in Path(path).read_text().splitlines()]
def require(ok,message):
    if not ok: raise ValueError(message)

def bounds(actor):
    body=actor['body_native_xyz_m']
    xs=[p[0] for p in body];ys=[p[1] for p in body]
    return min(xs),max(xs),min(ys),max(ys)

def measure(bundle,saved):
    bundle,saved=Path(bundle),Path(saved)
    cfg=read(bundle/'config.json');receipt=read(saved/'preparation-receipt.json')
    names=('native-observed.jsonl','camera-frames.jsonl','frame-review.jsonl')
    require(receipt.get('config_sha256')==sha(bundle/'config.json') and
            receipt.get('saved_hashes')=={name:sha(saved/name) for name in names} and
            receipt.get('delivery_ready') is False and
            receipt.get('legal_verdict') is None,
            'prepared receipt/source binding')
    actor,camera,review=(rows(saved/name) for name in names)
    require(len(actor)==len(camera)==len(review)==240,
            'prepared frame coverage')
    pass_frames=0;clearance=None;right_frames=0
    for i,(row,frame,view) in enumerate(zip(actor,camera,review)):
        require(row['frame']==frame['frame']==view['frame']==i and
                row['native_frame']==frame['native_frame']==view['native_frame'] and
                row['time_s']==frame['time_s']==view['time_s'] and
                row['source_kind']==frame['source_kind']==view['source_kind']==
                    receipt['source_kind'] and
                frame['video_frame']==i and
                view['review_provenance']==('synthetic_cpu' if
                    receipt['source_kind']=='synthetic_cpu' else 'human_frame_review'),
                f'prepared actor/video/review join {i}')
        ego,lead=bounds(row['ego']),bounds(row['lead'])
        right=(ego[3]<lead[2] and row['observed_ego_lane_id']==-2)
        right_frames+=int(right)
        pass_frames+=int(right and ego[0]>lead[1])
        obj=row['obstruction']
        require((obj is not None)==cfg['right_lane_obstruction_requested'],
                f'prepared obstruction coverage {i}')
        if obj is not None:
            other=bounds(obj)
            dx=max(ego[0]-other[1],0,other[0]-ego[1])
            dy=max(ego[2]-other[3],0,other[2]-ego[3])
            distance=math.hypot(dx,dy)
            clearance=distance if clearance is None else min(clearance,distance)
    return {'format':'c146314-prepared-measurement-v1',
        'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
        'source_kind':receipt['source_kind'],'frames':240,
        'ego_body_right_of_lead_frames':right_frames,
        'ego_body_ahead_and_right_of_lead_frames':pass_frames,
        'min_ego_body_to_obstruction_body_gap_m':None if clearance is None
            else round(clearance,6),
        'original_native_observed':receipt['original_native_observed'],
        'one_way_designation_verified':False,
        'pavement_condition_verified':False,
        'obstruction_significance_verified':False,
        'accepted':False,'legal_verdict':None,'delivery_ready':False}

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--saved-dir',type=Path,required=True)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    result=measure(a.bundle,a.saved_dir)
    if a.output:a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
