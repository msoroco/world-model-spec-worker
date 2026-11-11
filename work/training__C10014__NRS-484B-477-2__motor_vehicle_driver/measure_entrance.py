"""Measure observed stationary alley footprint overlap with an entrance corridor.

The geometric overlap is a source-bound observation, not a finding that access
was legally blocked. Native alley and property designation remain separate proof.
"""
import hashlib
import json
import math
from pathlib import Path

RATE_HZ=20
STOP_SPEED_MPS=.1
MIN_STOP_S=2.0


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def point(value,name):
    if not isinstance(value,(list,tuple)) or len(value)!=2:
        raise ValueError('Invalid original point: '+name)
    result=tuple(float(v) for v in value)
    if not all(math.isfinite(v) for v in result):
        raise ValueError('Nonfinite original point: '+name)
    return result


def bounds(value,name):
    if not isinstance(value,list) or len(value)!=4:
        raise ValueError('Missing '+name)
    result=tuple(float(v) for v in value)
    if not all(math.isfinite(v) for v in result) or not (result[0]<result[2] and result[1]<result[3]):
        raise ValueError('Invalid '+name)
    return result


def clip_edge(vertices,inside,intersection):
    if not vertices:return []
    output=[];before=vertices[-1];before_inside=inside(before)
    for current in vertices:
        current_inside=inside(current)
        if current_inside!=before_inside:output.append(intersection(before,current))
        if current_inside:output.append(current)
        before=current;before_inside=current_inside
    return output


def clipped_polygon(vertices,box):
    xmin,ymin,xmax,ymax=box
    result=list(vertices)
    for axis,limit,keep_greater in ((0,xmin,True),(0,xmax,False),
                                     (1,ymin,True),(1,ymax,False)):
        def inside(p):return p[axis]>=limit-1e-9 if keep_greater else p[axis]<=limit+1e-9
        def cross(a,b):
            delta=b[axis]-a[axis]
            if abs(delta)<1e-12:return a
            factor=(limit-a[axis])/delta
            return (a[0]+factor*(b[0]-a[0]),a[1]+factor*(b[1]-a[1]))
        result=clip_edge(result,inside,cross)
    return result


def entrance_overlap_m(body,entrance):
    clipped=clipped_polygon(body,entrance)
    if len(clipped)<3:return 0.0
    area=abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in
                 zip(clipped,clipped[1:]+clipped[:1])))/2
    if area<=1e-9:return 0.0
    return max(v[0] for v in clipped)-min(v[0] for v in clipped)


def measure(samples_path,geometry_path):
    samples_path=Path(samples_path);geometry_path=Path(geometry_path)
    for path in (samples_path,geometry_path):
        if not path.is_file():raise ValueError('Missing required source: '+path.name)
    geometry=json.loads(geometry_path.read_text())
    entrance=bounds(geometry.get('driveway_entrance_native_xy_bounds_m'),'entrance bounds')
    access=bounds(geometry.get('abutting_property_access_native_xy_bounds_m'),'access bounds')
    if access[3]!=entrance[1] or access[0]!=entrance[0] or access[2]!=entrance[2]:
        raise ValueError('Entrance/access geometry is disconnected')
    alley_road=geometry.get('alley_native_road_id');alley_lane=geometry.get('alley_native_lane_id')
    if type(alley_road) is not int or type(alley_lane) is not int:
        raise ValueError('Missing Native alley road/lane identity')
    rows=[json.loads(line) for line in samples_path.read_text().splitlines() if line.strip()]
    if len(rows)<int(RATE_HZ*MIN_STOP_S):raise ValueError('Too few original Native samples')
    frames=[];times=[];stopped=[];overlap=[]
    for row in rows:
        frame=row.get('native_frame');time=row.get('time_s');speed=row.get('speed_mps')
        if type(frame) is not int or frame<0 or type(time) not in (float,int) or not math.isfinite(time):
            raise ValueError('Invalid original frame/time')
        if type(speed) not in (float,int) or not math.isfinite(speed) or speed<0:
            raise ValueError('Invalid original speed')
        if frames and (frame<=frames[-1] or time<=times[-1] or abs((time-times[-1])-1/RATE_HZ)>.002):
            raise ValueError('Original frame/time order or rate invalid')
        body=[point(v,'native_body_xy_m') for v in row.get('native_body_xy_m',[])]
        if len(body)!=4:raise ValueError('Original full body missing')
        center=point(row.get('native_center_xy_m'),'native_center_xy_m')
        heading=point(row.get('native_forward_xy'),'native_forward_xy')
        if abs(math.hypot(*heading)-1)>.01:raise ValueError('Original heading is not unit length')
        if not all(math.isfinite(v) for v in center):raise ValueError('Invalid original center')
        in_alley=row.get('native_road_id')==alley_road and row.get('native_lane_id')==alley_lane
        frames.append(frame);times.append(time)
        stopped.append(in_alley and speed<=STOP_SPEED_MPS)
        overlap.append(entrance_overlap_m(body,entrance))
    intervals=[];start=None
    for i,flag in enumerate(stopped+[False]):
        if flag and start is None:start=i
        if not flag and start is not None:
            if i-start>=int(RATE_HZ*MIN_STOP_S):intervals.append((start,i))
            start=None
    if not intervals:raise ValueError('No observed stationary alley interval')
    a,b=max(intervals,key=lambda pair:pair[1]-pair[0])
    return {'format':'c10014-entrance-observation-v1',
            'source_sha256':{'native_samples.jsonl':sha(samples_path),
                             'road_geometry.json':sha(geometry_path)},
            'original_frames':len(rows),'stop_first_frame':frames[a],
            'stop_last_frame':frames[b-1],
            'stop_duration_s':round((b-a)/RATE_HZ,5),
            'max_entrance_overlap_m':round(max(overlap[a:b]),6),
            'mean_entrance_overlap_m':round(sum(overlap[a:b])/(b-a),6),
            'native_design_verified':geometry.get('native_alley_and_access_design_verified') is True,
            'legal_blocking_verdict_claimed':False}
