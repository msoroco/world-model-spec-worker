"""Saved Native approach/turn lane occupancy prototype; no legal verdict."""
import hashlib
import json
import math
from pathlib import Path


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _point(value,name):
    if not isinstance(value,list) or len(value)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in value):
        raise ValueError('Invalid Native point: '+name)
    return value


def _body(row):
    body=row.get('native_body_xy_m')
    if not isinstance(body,list) or len(body)!=4:raise ValueError('Complete Native body missing')
    return [_point(point,'body vertex') for point in body]


def _overlap(body,bounds):
    low_x,low_y,high_x,high_y=bounds
    return max(p[0] for p in body)>=low_x and min(p[0] for p in body)<=high_x and \
           max(p[1] for p in body)>=low_y and min(p[1] for p in body)<=high_y


def measure(samples_path,geometry_path):
    samples_path=Path(samples_path);geometry_path=Path(geometry_path)
    for path in (samples_path,geometry_path):
        if not path.is_file():raise ValueError('Missing required source: '+path.name)
    geometry=json.loads(geometry_path.read_text())
    if not isinstance(geometry.get('native_map_sha256'),str) or len(geometry['native_map_sha256'])!=64:
        raise ValueError('Native map hash missing')
    if geometry.get('approach_road_id')!=1 or geometry.get('turn_connector_road_id')!=13:
        raise ValueError('Approach/turn Native road survey missing')
    if geometry.get('right_turn_lane_id')!=-2 or geometry.get('right_turn_lane_native_y_bounds_m')!=[-7.0,-3.5]:
        raise ValueError('Right-turn-lane Native survey missing')
    if geometry.get('intersection_native_xy_bounds_m')!=[-7,-7,7,7]:
        raise ValueError('Intersection Native bounds missing')
    rows=[json.loads(line) for line in samples_path.read_text().splitlines() if line.strip()]
    if len(rows)<4:raise ValueError('Too few Native motion samples')
    prior_frame=-1;prior_time=-math.inf;approach=[];turn=[];exit_rows=[]
    for row in rows:
        frame=row.get('native_frame');time=row.get('time_s')
        if type(frame) is not int or frame<=prior_frame or type(time) not in (int,float) or \
           not math.isfinite(time) or time<=prior_time:
            raise ValueError('Native frame/time sequence invalid')
        prior_frame=frame;prior_time=time
        body=_body(row);forward=_point(row.get('native_forward_xy'),'forward')
        if abs(math.hypot(*forward)-1)>.01:raise ValueError('Native forward is not a unit vector')
        if any(type(row.get(key)) is not int for key in ('native_road_id','native_lane_id')):
            raise ValueError('Native road/lane identity missing')
        inside=_overlap(body,[-7,-7,7,7])
        if not inside and max(p[0] for p in body)<-7:approach.append((row,body))
        elif inside:turn.append((row,body))
        elif max(p[1] for p in body)<-7:exit_rows.append((row,body))
    if len(approach)<2 or not turn or not exit_rows:
        raise ValueError('Approach, turn and complete exit not all observed')
    first=approach[0][0];last=exit_rows[-1][0]
    if first['native_forward_xy'][0]<.95 or last['native_forward_xy'][1]>-.95:
        raise ValueError('Observed right-turn heading change missing')
    low_y,high_y=geometry['right_turn_lane_native_y_bounds_m']
    full_body=[all(low_y<=p[1]<=high_y for p in body) for _,body in approach]
    lane_identity=[row['native_road_id']==1 and row['native_lane_id']==-2 for row,_ in approach]
    connector=[row['native_road_id']==13 and row['native_lane_id']==-2 for row,_ in turn]
    return {'format':'c382355-right-turn-lane-samples-v1',
      'approach_window_s':[approach[0][0]['time_s'],approach[-1][0]['time_s']],
      'turn_window_s':[turn[0][0]['time_s'],turn[-1][0]['time_s']],
      'full_body_in_right_turn_lane_approach_samples':all(full_body),
      'approach_lane_identity_fraction':sum(lane_identity)/len(lane_identity),
      'turn_connector_identity_fraction':sum(connector)/len(connector),
      'right_turn_observed_at_complete_exit':True,
      'right_turn_lane_design_native_verified':geometry.get('right_turn_lane_design_native_verified') is True,
      'source_hashes':{samples_path.name:sha(samples_path),geometry_path.name:sha(geometry_path)},
      'scope':'original sampled body/lane IDs only; design, intersample occupancy and legal outcome unverified'}
