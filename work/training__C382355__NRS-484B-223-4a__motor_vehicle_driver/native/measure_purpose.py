"""Measure ordered right-only-lane use and subsequent movement; no legal verdict."""
import hashlib
import json
import math
from pathlib import Path


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    path=Path(path)
    if not path.is_file():raise ValueError('Missing required source: '+path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def finite_pair(value,name):
    if not isinstance(value,list) or len(value)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in value):
        raise ValueError('Invalid Native '+name)
    return value


def measure_lane_use(samples_path,geometry_path):
    samples_path=Path(samples_path);geometry_path=Path(geometry_path)
    if not geometry_path.is_file():raise ValueError('Missing required source: '+geometry_path.name)
    geometry=json.loads(geometry_path.read_text())
    if not isinstance(geometry.get('native_map_sha256'),str) or len(geometry['native_map_sha256'])!=64:
        raise ValueError('Native map hash missing')
    expected={'approach_road_id':1,'right_only_lane_id':-2,
              'right_turn_connector_road_id':13,'straight_connector_road_id':14,
              'right_turn_destination_road_id':4,'straight_destination_road_id':2}
    if any(geometry.get(key)!=value for key,value in expected.items()):
        raise ValueError('Native road/lane survey differs from authored proposal')
    samples=rows(samples_path)
    if len(samples)<4:raise ValueError('Too few Native samples')
    approach=[];intersection=[];exit_rows=[];previous_frame=-1;previous_time=-math.inf
    for sample in samples:
        frame=sample.get('native_frame');time=sample.get('time_s')
        if type(frame) is not int or frame<=previous_frame or type(time) not in (int,float) or not math.isfinite(time) or time<=previous_time:
            raise ValueError('Native frame/time sequence invalid')
        previous_frame=frame;previous_time=time
        body=sample.get('native_body_xy_m')
        if not isinstance(body,list) or len(body)!=4:
            raise ValueError('Complete Native body missing')
        for point in body:finite_pair(point,'body vertex')
        forward=finite_pair(sample.get('native_forward_xy'),'heading')
        if abs(math.hypot(*forward)-1)>.01:raise ValueError('Native heading not unit length')
        if any(type(sample.get(key)) is not int for key in ('native_road_id','native_lane_id')):
            raise ValueError('Native road/lane identity missing')
        if max(point[0] for point in body)<-7:
            approach.append(sample)
        elif sample['native_road_id'] in (13,14):
            intersection.append(sample)
        elif sample['native_road_id']==2 and min(point[0] for point in body)>7:
            exit_rows.append(sample)
        elif sample['native_road_id']==4 and max(point[1] for point in body)<-7:
            exit_rows.append(sample)
    if len(approach)<2 or not intersection or not exit_rows:
        raise ValueError('Approach, intersection and completed exit not all observed')
    if approach[-1]['native_frame']>=intersection[0]['native_frame'] or intersection[-1]['native_frame']>=exit_rows[0]['native_frame']:
        raise ValueError('Lane occupancy and subsequent movement order invalid')
    if approach[0]['native_forward_xy'][0]<.95:
        raise ValueError('Approach heading not eastbound')
    last=exit_rows[-1];road=last['native_road_id'];forward=last['native_forward_xy']
    if road==4 and forward[1]<-.95:movement='right_turn_follows'
    elif road==2 and forward[0]>.95:movement='straight_follows'
    else:raise ValueError('Completed exit movement not measurable')
    connectors={row['native_road_id'] for row in intersection}
    required_connector=13 if movement=='right_turn_follows' else 14
    if connectors!={required_connector}:
        raise ValueError('Connector and completed movement disagree')
    body_inside=[];ids=[]
    for sample in approach:
        body_inside.append(all(-7.0<=point[1]<=-3.5 for point in sample['native_body_xy_m']))
        ids.append(sample['native_road_id']==1 and sample['native_lane_id']==-2)
    return {'format':'c382355-right-only-lane-use-v1',
            'approach_window_s':[approach[0]['time_s'],approach[-1]['time_s']],
            'intersection_window_s':[intersection[0]['time_s'],intersection[-1]['time_s']],
            'exit_window_s':[exit_rows[0]['time_s'],exit_rows[-1]['time_s']],
            'full_body_in_right_only_lane_approach_samples':all(body_inside),
            'right_only_lane_identity_fraction':sum(ids)/len(ids),
            'observed_subsequent_movement':movement,
            'right_only_lane_design_native_verified':geometry.get('right_only_lane_design_native_verified') is True,
            'source_hashes':{samples_path.name:sha(samples_path),geometry_path.name:sha(geometry_path)},
            'scope':'sampled Native body/lane IDs and ordered movement; lane purpose, design and legal outcome unverified'}
