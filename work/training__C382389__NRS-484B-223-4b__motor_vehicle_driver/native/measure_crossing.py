"""Measure straight intersection crossing and lane identity; no statutory verdict."""
import hashlib
import json
import math
from pathlib import Path


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    path=Path(path)
    if not path.is_file():raise ValueError('Missing required source: '+path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def point(value,label):
    if not isinstance(value,list) or len(value)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in value):
        raise ValueError('Invalid Native '+label)
    return value


def overlap(body):
    return max(p[0] for p in body)>=-7 and min(p[0] for p in body)<=7 and \
           max(p[1] for p in body)>=-7 and min(p[1] for p in body)<=7


def measure_crossing(samples_path,geometry_path):
    samples_path=Path(samples_path);geometry_path=Path(geometry_path)
    if not geometry_path.is_file():raise ValueError('Missing required source: '+geometry_path.name)
    geometry=json.loads(geometry_path.read_text())
    if not isinstance(geometry.get('native_map_sha256'),str) or len(geometry['native_map_sha256'])!=64:
        raise ValueError('Native map hash missing')
    expected={'approach_road_id':1,'straight_connector_road_id':14,
              'straight_destination_road_id':2,'right_only_lane_id':-2,
              'adjacent_through_lane_id':-1,'intersection_native_xy_bounds_m':[-7,-7,7,7]}
    if any(geometry.get(key)!=value for key,value in expected.items()):
        raise ValueError('Native road/lane survey differs from authored crossing')
    samples=rows(samples_path)
    if len(samples)<4:raise ValueError('Too few Native samples')
    previous_frame=-1;previous_time=-math.inf;approach=[];inside=[];exits=[]
    for sample in samples:
        frame=sample.get('native_frame');time=sample.get('time_s')
        if type(frame) is not int or frame<=previous_frame or type(time) not in (int,float) or not math.isfinite(time) or time<=previous_time:
            raise ValueError('Native frame/time sequence invalid')
        previous_frame=frame;previous_time=time
        body=sample.get('native_body_xy_m')
        if not isinstance(body,list) or len(body)!=4:raise ValueError('Complete Native body missing')
        for vertex in body:point(vertex,'body vertex')
        forward=point(sample.get('native_forward_xy'),'heading')
        if abs(math.hypot(*forward)-1)>.01:raise ValueError('Native heading not unit length')
        if any(type(sample.get(key)) is not int for key in ('native_road_id','native_lane_id')):
            raise ValueError('Native road/lane identity missing')
        if sample['native_road_id']==1 and max(p[0] for p in body)<-7:
            approach.append(sample)
        if sample['native_road_id']==14 and overlap(body):inside.append(sample)
        if sample['native_road_id']==2 and min(p[0] for p in body)>7:exits.append(sample)
    if len(approach)<2 or not inside or not exits:
        raise ValueError('Approach, intersection crossing and complete exit not all observed')
    if approach[-1]['native_frame']>=inside[0]['native_frame'] or inside[-1]['native_frame']>=exits[0]['native_frame']:
        raise ValueError('Crossing phase order invalid')
    if any(row['native_forward_xy'][0]<.95 for row in (approach[0],inside[0],exits[-1])):
        raise ValueError('Straight heading through intersection missing')
    lanes={row['native_lane_id'] for row in approach+inside+exits}
    if lanes not in ({-2},{-1}):raise ValueError('Lane identity changed during crossing')
    observed_lane=next(iter(lanes))
    fraction=sum(row['native_lane_id']==-2 for row in inside)/len(inside)
    return {'format':'c382389-right-only-lane-crossing-v1',
            'approach_window_s':[approach[0]['time_s'],approach[-1]['time_s']],
            'intersection_window_s':[inside[0]['time_s'],inside[-1]['time_s']],
            'complete_exit_window_s':[exits[0]['time_s'],exits[-1]['time_s']],
            'observed_approach_lane_id':observed_lane,
            'right_only_lane_intersection_sample_fraction':fraction,
            'straight_through_from_right_only_lane_observed':observed_lane==-2 and fraction==1,
            'right_only_lane_design_native_verified':geometry.get('right_only_lane_design_native_verified') is True,
            'source_hashes':{samples_path.name:sha(samples_path),geometry_path.name:sha(geometry_path)},
            'scope':'sampled Native body/lane IDs through a complete straight crossing; design, intersample occupancy and legal outcome unverified'}
