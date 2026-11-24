"""Saved Native full-body exit-side measurement; no legal verdict."""
import hashlib
import json
import math
from pathlib import Path


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def vector(item,name):
    if not isinstance(item,list) or len(item)!=2 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in item):
        raise ValueError('Invalid Native vector: '+name)
    if abs(math.hypot(*item)-1)>.01:raise ValueError('Native vector not unit length: '+name)
    return item


def point(item,name):
    if not isinstance(item,list) or len(item)!=2 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in item):
        raise ValueError('Invalid Native point: '+name)
    return item


def dot(a,b):return a[0]*b[0]+a[1]*b[1]
def relative(a,b):return [a[0]-b[0],a[1]-b[1]]


def measure(samples_path,geometry_path):
    samples_path=Path(samples_path);geometry_path=Path(geometry_path)
    for path in (samples_path,geometry_path):
        if not path.is_file():raise ValueError('Missing required source: '+path.name)
    geometry=json.loads(geometry_path.read_text())
    if not isinstance(geometry.get('native_map_sha256'),str) or len(geometry['native_map_sha256'])!=64:
        raise ValueError('Native map hash missing')
    directions=geometry.get('road_directions_native')
    if not isinstance(directions,dict) or set(directions)!={'approach_forward','approach_opposing','destination_forward','destination_opposing'}:
        raise ValueError('Two-way Native direction evidence missing')
    for a,b in (('approach_forward','approach_opposing'),('destination_forward','destination_opposing')):
        if dot(vector(directions[a],a),vector(directions[b],b))>-.98:
            raise ValueError('Two-way Native direction evidence missing')
    dest=vector(directions['destination_forward'],'destination_forward')
    right=vector(geometry['destination_right_normal_native'],'destination_right_normal_native')
    # CARLA's Native XY frame is left handed: forward (0,-1) has right (1,0).
    expected_right=[-dest[1],dest[0]]
    if dot(right,expected_right)<.99:
        raise ValueError('Destination right axis differs from Native lane direction')
    center=point(geometry['destination_centerline_point_native_m'],'destination_centerline_point_native_m')
    boundary=point(geometry['destination_exit_point_native_m'],'destination_exit_point_native_m')
    entry=point(geometry['intersection_entry_point_native_m'],'intersection_entry_point_native_m')
    approach=vector(directions['approach_forward'],'approach_forward')
    rows=[json.loads(line) for line in samples_path.read_text().splitlines() if line.strip()]
    if len(rows)<2:raise ValueError('Too few Native motion samples')
    previous=-math.inf;first=None;prior_time=None;before_entry=False;entered=False;entry_bracket=None
    for row in rows:
        time=float(row['time_s'])
        if not math.isfinite(time) or time<=previous:raise ValueError('Native times not strictly increasing')
        previous=time
        vertices=row['native_body_xy_m']
        if not isinstance(vertices,list) or len(vertices)!=4:raise ValueError('Full Native footprint missing')
        vertices=[point(v,'body vertex') for v in vertices]
        forward=vector(row['native_forward_xy'],'actor forward')
        offsets=[dot(relative(v,entry),approach) for v in vertices]
        if not entered and max(offsets)<0:
            before_entry=True
        if before_entry and not entered and max(offsets)>=0:
            entered=True
            entry_bracket=[prior_time,time]
        fully_beyond=all(dot(relative(v,boundary),dest)>0 for v in vertices)
        if entered and fully_beyond and dot(forward,dest)>=math.cos(math.radians(20)):
            first=(prior_time,time,vertices)
            break
        prior_time=time
    if not entered:raise ValueError('No sampled intersection entry after pre-entry approach')
    if first is None:raise ValueError('No full-body destination exit with observed turn completion')
    low=min(dot(relative(v,center),right) for v in first[2])
    high=max(dot(relative(v,center),right) for v in first[2])
    side='right' if low>0 else 'left' if high<0 else 'straddles_centerline'
    return {'format':'c329610-exit-side-measurement-v1',
            'native_map_sha256':geometry['native_map_sha256'],
            'first_full_body_exit_time_bracket_s':[first[0],first[1]],
            'first_intersection_entry_time_bracket_s':entry_bracket,
            'body_right_offset_interval_m':[low,high],
            'geometric_side':side,'intersection_entry_observed':True,'full_body_exit_observed':True,
            'sources':{samples_path.name:sha(samples_path),geometry_path.name:sha(geometry_path)},
            'scope':'sampled Native geometry only; no legal verdict or intersample claim'}
