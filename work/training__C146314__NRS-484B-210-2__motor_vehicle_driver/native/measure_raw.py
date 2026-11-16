"""Derive right-pass engineering measures from retained Native actor sources.

This produces measurements, never a legal NRS 484B.210(2) safety verdict.
Synthetic inputs are accepted only as diagnostic fixtures and retain that label.
"""
import argparse
import json
import math
from pathlib import Path

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def hull(points):
    points = sorted(set((float(p[0]), float(p[1])) for p in points))
    require(len(points) >= 3, 'Body lacks planar vertices')
    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lower = []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2],lower[-1],p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2],upper[-1],p) <= 0:
            upper.pop()
        upper.append(p)
    polygon = lower[:-1]+upper[:-1]
    require(len(polygon) >= 3, 'Degenerate body footprint')
    return polygon


def project(poly, axis):
    values = [p[0]*axis[0]+p[1]*axis[1] for p in poly]
    return min(values), max(values)


def segment_distance(a, b, c, d):
    def orientation(p, q, r):
        return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    oa, ob = orientation(a,b,c), orientation(a,b,d)
    oc, od = orientation(c,d,a), orientation(c,d,b)
    if oa*ob < 0 and oc*od < 0:
        return 0.0
    def point_segment(p, x, y):
        dx,dy=y[0]-x[0],y[1]-x[1]
        t=max(0.0,min(1.0,((p[0]-x[0])*dx+(p[1]-x[1])*dy)/(dx*dx+dy*dy)))
        return math.hypot(p[0]-x[0]-t*dx,p[1]-x[1]-t*dy)
    return min(point_segment(a,c,d),point_segment(b,c,d),
               point_segment(c,a,b),point_segment(d,a,b))


def footprint_gap(ego, lead):
    a, b = hull(ego), hull(lead)
    axes = []
    for poly in (a,b):
        for p,q in zip(poly,poly[1:]+poly[:1]):
            axis = (q[1]-p[1], p[0]-q[0])
            length = math.hypot(*axis)
            axes.append((axis[0]/length,axis[1]/length))
    if all(not (project(a,axis)[1] < project(b,axis)[0] or
                project(b,axis)[1] < project(a,axis)[0]) for axis in axes):
        return 0.0
    return min(segment_distance(p,q,r,s)
               for p,q in zip(a,a[1:]+a[:1])
               for r,s in zip(b,b[1:]+b[:1]))


def measure(rows, frames):
    require(len(rows)==len(frames)==240, 'Expected 240 synchronized source frames')
    require({r['source_kind'] for r in rows} in
            ({'original_native'},{'synthetic_native_sample'}),
            'Source provenance is mixed or unsupported')
    kind = rows[0]['source_kind']
    measured=[]
    for i,(row,joined) in enumerate(zip(rows,frames)):
        require(row['frame']==joined['video_frame']==i and
                row['native_frame']==joined['native_frame'] and
                set(joined['views'])==set(VIEWS),
                'Actor and four-camera frame join differs')
        e,l=row['ego'],row['lead']
        for actor in (e,l):
            require(len(actor['body_native_xyz_m'])>=4 and
                    len(actor['velocity_native_xyz_mps'])==3 and
                    all(math.isfinite(float(x)) for p in actor['body_native_xyz_m'] for x in p),
                    'Raw body or velocity missing')
        ex,ey=e['center_native_xyz_m'][:2]
        lx,ly=l['center_native_xyz_m'][:2]
        ev,lv=e['velocity_native_xyz_mps'][0],l['velocity_native_xyz_mps'][0]
        closing=ev-lv
        longitudinal_gap=lx-ex
        lateral_right=ey<ly
        clearance=footprint_gap(e['body_native_xyz_m'],l['body_native_xyz_m'])
        ego_x=project(hull(e['body_native_xyz_m']),(1,0))
        lead_x=project(hull(l['body_native_xyz_m']),(1,0))
        overlap=ego_x[1]>=lead_x[0] and lead_x[1]>=ego_x[0]
        measured.append({'frame':i,'native_frame':row['native_frame'],
            'time_s':row['time_s'],'source_kind':kind,
            'observed_ego_lane_id':row['observed_ego_lane_id'],
            'observed_lead_lane_id':row['observed_lead_lane_id'],
            'observed_right_of_lead':lateral_right,
            'observed_longitudinal_gap_m':round(longitudinal_gap,6),
            'observed_relative_x_speed_mps':round(closing,6),
            'time_to_lead_center_s':round(longitudinal_gap/closing,6)
                if longitudinal_gap>0 and closing>0 else None,
            'observed_body_surface_gap_m':round(clearance,6),
            'longitudinal_body_overlap':overlap,
            'ego_brake_control':row['ego_control']['brake']})
    pass_samples=[r for r in measured if r['observed_right_of_lead'] and
                  r['longitudinal_body_overlap']]
    require(pass_samples and any(r['observed_longitudinal_gap_m']>0 for r in measured) and
            any(r['observed_longitudinal_gap_m']<0 for r in measured),
            'Right-side overtake not observed in raw sources')
    decelerations=[]
    for before,after in zip(rows,rows[1:]):
        dt=after['time_s']-before['time_s']
        require(dt>0, 'Nonmonotonic Native time')
        decelerations.append((before['ego']['velocity_native_xyz_mps'][0]-
                              after['ego']['velocity_native_xyz_mps'][0])/dt)
    return {'format':'c146314-right-pass-raw-measures-v1',
        'source_kind':kind,'diagnostic_only':kind!='original_native',
        'legal_safety_verdict':None,'frames':len(measured),
        'observed_right_pass_frames':len(pass_samples),
        'minimum_pass_body_surface_gap_m':min(r['observed_body_surface_gap_m'] for r in pass_samples),
        'maximum_ego_deceleration_mps2':round(max(decelerations),6),
        'maximum_ego_brake_control':max(r['ego_brake_control'] for r in measured),
        'observations':measured}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('capture_dir',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    data=measure(read_jsonl(args.capture_dir/'native-raw-actors.jsonl'),
                 read_jsonl(args.capture_dir/'video_frames.jsonl'))
    args.output.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    print(json.dumps({key:data[key] for key in data if key!='observations'}))
