"""Source-bound simultaneous backing/crosswalk overlap measurement, CPU schema."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
from geometry import CROSSWALK, INTERSECTION, overlap


def measure(source: Path, expected_sha256: str):
    raw=source.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_sha256:
        raise ValueError('Saved Native source hash differs')
    rows=[json.loads(line) for line in raw.splitlines()]
    if len(rows)!=480:raise ValueError('Exact 480-frame saved path required')
    events=[];backing_frames=0;prior_frame=None;prior_time=None;last_x=None
    for index,row in enumerate(rows):
        frame=row.get('native_frame');time=row.get('time_s')
        if row.get('video_frame')!=index or type(frame) is not int or \
           (prior_frame is not None and frame!=prior_frame+1):
            raise ValueError('Original frame join differs')
        if type(time) not in (int,float) or not math.isfinite(time) or \
           (prior_time is not None and abs(time-prior_time-.05)>1e-6):
            raise ValueError('Original 20 Hz timing differs')
        prior_frame=frame;prior_time=time
        body=row.get('body_xy_m')
        if not isinstance(body,list) or len(body)!=4 or any(
            not isinstance(v,list) or len(v)!=2 or any(type(c) not in (int,float) or
            not math.isfinite(c) for c in v) for v in body):
            raise ValueError('Original full-body footprint absent')
        polygon=row.get('crosswalk_polygon_xy_m')
        if row.get('native_crosswalk_survey') is not True or \
           not isinstance(polygon,list) or len(polygon)!=4 or any(
               not isinstance(p,list) or len(p)!=2 or any(type(v) not in (int,float)
               or not math.isfinite(v) for v in p) for p in polygon):
            raise ValueError('Original crosswalk map survey absent')
        xs=[p[0] for p in polygon];ys=[p[1] for p in polygon]
        observed=(min(xs),min(ys),max(xs),max(ys))
        if any(abs(a-b)>.6 for a,b in zip(observed,CROSSWALK)):
            raise ValueError('Original crosswalk polygon differs from authored target')
        reverse=row.get('signed_forward_velocity_m_s')
        if type(reverse) not in (int,float) or not math.isfinite(reverse):
            raise ValueError('Signed Native velocity absent')
        x=row.get('native_center_xy_m',[None])[0]
        if type(x) not in (int,float):raise ValueError('Native center absent')
        if last_x is not None and reverse<-.05 and x>=last_x:
            raise ValueError('Backing velocity disagrees with observed displacement')
        if last_x is not None and reverse>=-.05 and x<last_x-.001:
            raise ValueError('Nonbacking velocity disagrees with observed displacement')
        last_x=x
        cross=overlap(body,observed);intersection=overlap(body,INTERSECTION)
        if reverse<-.05 and intersection>0:
            raise ValueError('Selected crosswalk branch confounded by intersection backing')
        if reverse<-.05:backing_frames+=1
        if reverse<-.05 and cross>0:
            events.append({'video_frame':index,'crosswalk_overlap_m2':round(cross,5)})
    if backing_frames==0:
        raise ValueError('No observed reverse movement')
    return {'source_sha256':expected_sha256,'source_kind':'source_hashed_native_sample_schema',
            'backing_frames':backing_frames,
            'backing_crosswalk_event_frames':len(events),
            'max_backing_crosswalk_overlap_m2':max([e['crosswalk_overlap_m2'] for e in events],default=0),
            'first_backing_crosswalk_video_frame':events[0]['video_frame'] if events else None,
            'relation':'backing_over_crosswalk' if events else 'backing_clear_of_crosswalk',
            'scope':'sampled simultaneous reverse velocity and full body; no physical or legal verdict'}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('--sha256',required=True)
    a=p.parse_args();print(json.dumps(measure(a.source,a.sha256),indent=2))
