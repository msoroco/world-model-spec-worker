"""Independent source comparison for the two selected parked departures."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def audit(clear,close):
    clear,close=Path(clear),Path(close)
    for name in ('road.xodr','video_frames.jsonl'):
        if sha(clear/name)!=sha(close/name):
            raise ValueError('Fixed map or original frame timing differs: '+name)
    first=json.loads((clear/'departure-context.json').read_text())
    second=json.loads((close/'departure-context.json').read_text())
    if first!=second:
        raise ValueError('Fixed highway and parking context differs')
    a,b=read_rows(clear/'departure-trace.jsonl'),read_rows(close/'departure-trace.jsonl')
    if len(a)!=600 or len(b)!=600:
        raise ValueError('Complete paired 600-frame source missing')
    for i,(left,right) in enumerate(zip(a,b)):
        for key in ('video_frame','native_frame','time_s','camera_native_frames',
                    'ego_road_id','ego_footprint_xy_m','ego_speed_mps'):
            if left.get(key)!=right.get(key):
                raise ValueError('Fixed ego/capture policy differs at '+str(i)+': '+key)
        if i<150 and left.get('traffic_speed_mps')!=right.get('traffic_speed_mps'):
            raise ValueError('Initial traffic speed policy differs')
    if not (a[0]['traffic_xy_m'][0]>a[0]['ego_xy_m'][0] and
            b[0]['traffic_xy_m'][0]<b[0]['ego_xy_m'][0]):
        raise ValueError('Requested initial traffic position contrast missing')
    return {'format':'c227853-source-comparison-v1','passed':True,
            'clear_trace_sha256':sha(clear/'departure-trace.jsonl'),
            'close_trace_sha256':sha(close/'departure-trace.jsonl'),
            'fixed_map_sha256':sha(clear/'road.xodr'),
            'fixed_frame_map_sha256':sha(clear/'video_frames.jsonl'),
            'deliberate_difference':'initial approaching traffic position',
            'physical_or_legal_result_claimed':False}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--clear',required=True)
    p.add_argument('--close',required=True)
    a=p.parse_args()
    print(json.dumps(audit(a.clear,a.close),sort_keys=True))
