"""Saved original velocity and lane measurements; no compliance verdict."""
import argparse
import json
import math
from pathlib import Path

MPH_PER_MPS = 2.2369362921
LIMIT_MPH = 80.0


def measure(path):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines()]
    if len(rows) != 600 or [r['video_frame'] for r in rows] != list(range(600)):
        raise ValueError('missing original 600-frame speed history')
    if not all(rows[i]['native_frame'] < rows[i+1]['native_frame'] for i in range(599)):
        raise ValueError('nonmonotonic original Native frames')
    if not all(abs(r['time_s']-i/20) < .005 for i,r in enumerate(rows)):
        raise ValueError('original 20 Hz time history missing')
    if len({r.get('subject_id') for r in rows}) != 1 or rows[0].get('subject_id') is None:
        raise ValueError('original subject identity missing')
    lanes = [r.get('lane_id') for r in rows]
    if any(v not in (-1,-2) for v in lanes):
        raise ValueError('original lane readback missing')
    speeds = []
    for r in rows:
        v = r.get('velocity_xyz_mps')
        if not isinstance(v,list) or len(v)!=3 or not all(type(x) in (int,float) and math.isfinite(x) for x in v):
            raise ValueError('original velocity vector missing')
        speeds.append(math.sqrt(sum(x*x for x in v))*MPH_PER_MPS)
    first_dest = next((i for i,l in enumerate(lanes) if l == -2), None)
    return {'frames':600, 'minimum_mph':min(speeds), 'maximum_mph':max(speeds),
            'samples_above_80_mph':sum(s>LIMIT_MPH for s in speeds),
            'first_destination_lane_frame':first_dest,
            'starts_lane_minus_1':lanes[0]==-1,
            'ends_lane_minus_2':lanes[-1]==-2,
            'speed_samples_mph':speeds,
            'legal_conclusion':None, 'physical_review_required':True}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--history',required=True);a=p.parse_args()
    print(json.dumps(measure(a.history),sort_keys=True))
