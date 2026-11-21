"""Saved simultaneous reverse and corner-turn measurement; no legal outcome."""
from __future__ import annotations
import hashlib,json,math
from pathlib import Path
from geometry import CROSSWALK,INTERSECTION,overlap

def measure(source:Path,expected_sha256:str):
    raw=source.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_sha256:raise ValueError('Saved Native source hash differs')
    rows=[json.loads(line) for line in raw.splitlines()]
    if len(rows)!=480:raise ValueError('Exact 480-frame saved path required')
    prior_frame=None;prior_time=None;prior_pose=None;start_heading=None
    backing=0;turning=0;max_heading=0;corner_events=[];crosswalk_events=0;max_crosswalk_overlap=0
    for index,row in enumerate(rows):
        frame=row.get('native_frame');time=row.get('time_s')
        if row.get('video_frame')!=index or type(frame) is not int or (prior_frame is not None and frame!=prior_frame+1):
            raise ValueError('Original frame join differs')
        if type(time) not in (int,float) or not math.isfinite(time) or (prior_time is not None and abs(time-prior_time-.05)>1e-6):
            raise ValueError('Original 20 Hz timing differs')
        prior_frame=frame;prior_time=time
        body=row.get('body_xy_m')
        if not isinstance(body,list) or len(body)!=4 or any(not isinstance(v,list) or len(v)!=2 or any(type(c) not in (int,float) or not math.isfinite(c) for c in v) for v in body):
            raise ValueError('Original full-body footprint absent')
        survey=row.get('native_corner_survey')
        if survey is not True or row.get('intersection_polygon_xy_m')!=[[-7,-7],[7,-7],[7,7],[-7,7]] or row.get('crosswalk_polygon_xy_m')!=[[-19,-3.5],[-15,-3.5],[-15,3.5],[-19,3.5]]:
            raise ValueError('Original corner map survey absent')
        pose=row.get('native_center_xy_m');heading=row.get('heading_deg')
        reverse=row.get('signed_forward_velocity_m_s')
        if not isinstance(pose,list) or len(pose)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in pose) or type(heading) not in (int,float) or not math.isfinite(heading) or type(reverse) not in (int,float) or not math.isfinite(reverse):
            raise ValueError('Original pose/heading/signed velocity absent')
        polygon_area=abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in
                             zip(body,body[1:]+body[:1])))/2
        center=[sum(v[j] for v in body)/4 for j in (0,1)]
        edges=[(math.dist(a,b),math.degrees(math.atan2(b[1]-a[1],b[0]-a[0])))
               for a,b in zip(body,body[1:]+body[:1])]
        major=max(edges,key=lambda e:e[0])[1]
        axis_error=abs((major-heading+90)%180-90)
        if not (7<polygon_area<14) or math.dist(center,pose)>.6 or axis_error>15:
            raise ValueError('Original body footprint disagrees with pose/heading')
        if start_heading is None:start_heading=heading
        if prior_pose is not None:
            dx=pose[0]-prior_pose[0];dy=pose[1]-prior_pose[1]
            forward=dx*math.cos(math.radians(heading))+dy*math.sin(math.radians(heading))
            if reverse<-.05 and forward>=-.0001:raise ValueError('Backing velocity disagrees with observed displacement')
            if reverse>=-.05 and math.hypot(dx,dy)>.001:raise ValueError('Nonbacking velocity disagrees with observed displacement')
            change=abs((heading-prior_pose[2]+180)%360-180)
            if reverse<-.05 and change>.1:
                turning+=1
                if overlap(body,INTERSECTION)>0:corner_events.append(index)
        if reverse<-.05:
            backing+=1
            max_heading=max(max_heading,abs((heading-start_heading+180)%360-180))
            crosswalk_overlap=overlap(body,CROSSWALK)
            if crosswalk_overlap>0:crosswalk_events+=1
            max_crosswalk_overlap=max(max_crosswalk_overlap,crosswalk_overlap)
        prior_pose=(pose[0],pose[1],heading)
    if not backing:raise ValueError('No observed reverse movement')
    if crosswalk_events:raise ValueError('Corner branch confounded by crosswalk backing')
    return {'source_sha256':expected_sha256,'source_kind':'source_hashed_native_sample_schema',
            'backing_frames':backing,'corner_turning_frames':turning,
            'corner_event_frames':len(corner_events),'max_reverse_heading_change_deg':round(max_heading,5),
            'backing_crosswalk_event_frames':crosswalk_events,
            'max_backing_crosswalk_overlap_m2':round(max_crosswalk_overlap,5),
            'relation':'backing_around_street_corner' if turning>=20 and max_heading>=30 else 'backing_straight_through_intersection',
            'scope':'sampled reverse motion and corner heading, with crosswalk exclusion; no physical or legal verdict'}
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('--sha256',required=True)
    a=p.parse_args();print(json.dumps(measure(a.source,a.sha256),indent=2))
