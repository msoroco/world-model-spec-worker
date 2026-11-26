"""Saved original on-structure speed measurement; no legal verdict."""
import argparse
import json
import math
from pathlib import Path

MPH_PER_MPS=2.2369362921


def measure(history_path,context_path):
    rows=[json.loads(line) for line in Path(history_path).read_text().splitlines()]
    context=json.loads(Path(context_path).read_text())
    if len(rows)!=600 or [r['video_frame'] for r in rows]!=list(range(600)):
        raise ValueError('missing original 600-frame bridge history')
    if not all(rows[i]['native_frame']<rows[i+1]['native_frame'] for i in range(599)):
        raise ValueError('nonmonotonic original Native frames')
    if not all(abs(r['time_s']-i/20)<.005 for i,r in enumerate(rows)):
        raise ValueError('original 20 Hz timing missing')
    if not context.get('native_bridge_survey') or len(context.get('native_sign_survey',[]))!=2:
        raise ValueError('Native bridge or sign survey missing')
    if context.get('bridge_x_m')!=[0.0,100.0] or context.get('sign_limit_mph')!=25.0:
        raise ValueError('structural boundary or sign value missing')
    if len({r.get('subject_id') for r in rows})!=1 or rows[0].get('subject_id') is None:
        raise ValueError('original subject identity missing')
    on=[];speed=[]
    for r in rows:
        pos=r.get('position_xyz_m');vel=r.get('velocity_xyz_mps')
        if not isinstance(pos,list) or len(pos)!=3 or not all(type(v) in (int,float) and math.isfinite(v) for v in pos):
            raise ValueError('original position missing')
        if not isinstance(vel,list) or len(vel)!=3 or not all(type(v) in (int,float) and math.isfinite(v) for v in vel):
            raise ValueError('original velocity missing')
        on.append(0<=pos[0]<=100 and pos[2]>=6)
        speed.append(math.sqrt(sum(v*v for v in vel))*MPH_PER_MPS)
    on_speeds=[v for flag,v in zip(on,speed) if flag]
    if not on_speeds:raise ValueError('no original elevated-structure occupancy')
    return {'frames':600,'on_structure_frames':len(on_speeds),
            'maximum_on_structure_mph':max(on_speeds),
            'on_structure_samples_above_posted_maximum':sum(v>25 for v in on_speeds),
            'posted_maximum_mph':25.0,'department_determination_verified':False,
            'physical_sign_pixels_verified':False,'legal_conclusion':None,
            'physical_review_required':True}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--history',required=True);p.add_argument('--context',required=True)
    a=p.parse_args();print(json.dumps(measure(a.history,a.context),sort_keys=True))
