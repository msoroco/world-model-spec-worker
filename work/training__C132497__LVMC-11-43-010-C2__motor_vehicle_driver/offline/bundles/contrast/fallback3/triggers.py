"""Measure three fallback triggers from source-bound saved diagnostics."""
import argparse
import hashlib
import json
import math
from pathlib import Path

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]

def route(bundle,saved=None):
    bundle=Path(bundle);saved=Path(saved) if saved is not None else bundle/'saved'
    cfg=json.loads((bundle/'config.json').read_text())
    readback=json.loads((saved/'lane-readback.json').read_text())
    observed=rows(saved/'native-observed.jsonl')
    camera=rows(saved/'camera-frames.jsonl')
    if (cfg['tracks_sha256']!=sha(bundle/'requested-tracks.jsonl') or
        cfg['road_sha256']!=sha(bundle/'right-exit-road.xodr') or
        readback.get('road_sha256')!=cfg['road_sha256'] or
        readback.get('request_sha256')!=cfg['tracks_sha256'] or
        readback.get('source_kind')!='synthetic_cpu' or
        readback.get('right_lane_id')!=-2 or
        readback.get('physical_roundabout_verified') is not False or
        len(observed)!=len(camera)!=240):
        raise ValueError('C132497 trigger source differs')
    visible=0;deviation=0
    for i,(row,frame) in enumerate(zip(observed,camera)):
        if (row.get('frame')!=i or frame.get('frame')!=i or
            row.get('native_frame')!=frame.get('camera_frame') or
            row.get('time_s')!=frame.get('time_s') or
            row.get('source_kind')!='synthetic_cpu' or
            frame.get('source_kind')!='synthetic_cpu' or
            row.get('lane_id')!=cfg['requested_lane_id'] or
            type(frame.get('right_lane_visible')) is not bool):
            raise ValueError('C132497 trigger frame join differs')
        if i<40 and frame['right_lane_visible']:visible+=1
        if row.get('phase')=='circulation':
            x,y=row['ego_x_m'],row['ego_y_m']
            if not all(type(v) in (int,float) and math.isfinite(v) for v in (x,y)):
                raise ValueError('C132497 trigger pose differs')
            deviation=max(deviation,abs(math.hypot(x-22,y+22)-cfg['requested_arc_radius_m']))
    triggered={'fallback1':visible<20,'fallback2':deviation>.2,
        'fallback3':not (readback.get('physical_roundabout_verified') is True and
            readback.get('lane_allocation_verified') is True and
            readback.get('actual_right_exit_verified') is True)}
    return {'format':'c132497-measured-fallback-triggers-v1',
        'case_id':cfg['case_id'],'candidate_id':cfg['candidate_id'],
        'first_40_visible_frames':visible,
        'maximum_lane_center_deviation_m':round(deviation,6),
        'triggered':triggered,
        'source_hashes':{name:sha(saved/name) for name in
            ('native-observed.jsonl','camera-frames.jsonl','lane-readback.json')},
        'selected_candidate':None,'delivery_ready':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('bundle',type=Path)
    p.add_argument('--saved-dir',type=Path);a=p.parse_args()
    print(json.dumps(route(a.bundle,a.saved_dir)))
