"""Compare source-bound right/other lane synthetic saved pairs under fixed conditions."""
import argparse
import hashlib
import json
from pathlib import Path

import measure_saved

CASE=Path(__file__).resolve().parent.parent

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]

def compare(candidate='primary',case=CASE):
    case=Path(case);bundles={w:case/'offline'/'bundles'/w/candidate
        for w in ('reference','contrast')}
    cfg={w:json.loads((path/'config.json').read_text()) for w,path in bundles.items()}
    measures={w:measure_saved.measure(path) for w,path in bundles.items()}
    if (cfg['reference']['road_sha256']!=cfg['contrast']['road_sha256'] or
        cfg['reference']['requested_speed_mps']!=cfg['contrast']['requested_speed_mps'] or
        cfg['reference']['camera_policy']!=cfg['contrast']['camera_policy'] or
        cfg['reference']['requested_lane_id']!=-2 or
        cfg['contrast']['requested_lane_id']!=-1 or
        cfg['contrast']['requested_arc_radius_m']-cfg['reference']['requested_arc_radius_m']!=3.5):
        raise ValueError('C132497 controlled configuration differs')
    a=rows(bundles['reference']/'saved'/'native-observed.jsonl')
    b=rows(bundles['contrast']/'saved'/'native-observed.jsonl')
    ca=rows(bundles['reference']/'saved'/'camera-frames.jsonl')
    cb=rows(bundles['contrast']/'saved'/'camera-frames.jsonl')
    if len(a)!=len(b)!=240 or len(ca)!=len(cb)!=240:
        raise ValueError('C132497 controlled pair frame count differs')
    for i,(left,right,lf,rf) in enumerate(zip(a,b,ca,cb)):
        if (left['frame']!=right['frame'] or left['time_s']!=right['time_s'] or
            left['ego_speed_mps']!=right['ego_speed_mps'] or
            lf['right_lane_visible']!=rf['right_lane_visible'] or
            left['lane_id']!=-2 or right['lane_id']!=-1):
            raise ValueError(f'C132497 controlled saved pair differs at {i}')
    if (not measures['reference']['right_lane_used'] or
        measures['contrast']['right_lane_used'] or
        measures['reference']['requested_right_turn_heading_change_deg']!=
        measures['contrast']['requested_right_turn_heading_change_deg']):
        raise ValueError('C132497 measured lane comparison differs')
    return {'format':'c132497-controlled-saved-comparison-v1',
        'candidate_id':candidate,'fixed_road_sha256':cfg['reference']['road_sha256'],
        'fixed_frame_speed_camera_rows':240,
        'reference_lane_id':-2,'contrast_lane_id':-1,
        'reference_circulation_frames':measures['reference']['phase_frames']['circulation'],
        'contrast_circulation_frames':measures['contrast']['phase_frames']['circulation'],
        'source_hashes':{w:{name:sha(path/'saved'/name) for name in
            ('native-observed.jsonl','camera-frames.jsonl','lane-readback.json')}
            for w,path in bundles.items()},
        'original_native_observed':False,'legal_verdict':None,'delivery_ready':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--candidate',default='primary')
    print(json.dumps(compare(p.parse_args().candidate)))
