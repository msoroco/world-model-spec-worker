"""Measure original backing and moving-traffic sequence without a right-of-way verdict."""
import argparse
import hashlib
import json
import math
from pathlib import Path

FRAMES=600
CAMERAS=('overview','approach','reference_corner','driver_reference')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    if not path.is_file():raise ValueError('Missing required source: '+path.name)
    data=[json.loads(line) for line in path.read_text().splitlines()]
    if len(data)!=FRAMES:raise ValueError('Original source must contain 600 frames')
    return data


def xy(actor):
    value=actor.get('center_xy_m')
    if not isinstance(value,list) or len(value)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in value):
        raise ValueError('Original actor position missing')
    velocity=actor.get('velocity_xy_mps')
    if not isinstance(velocity,list) or len(velocity)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in velocity):
        raise ValueError('Original actor velocity missing')
    body=actor.get('body_xy_m')
    if not isinstance(body,list) or len(body)<4:raise ValueError('Original actor body missing')
    return value,velocity


def inside(point,region):
    return region['x_min_m']<=point[0]<=region['x_max_m'] and region['y_min_m']<=point[1]<=region['y_max_m']


def measure(attempt):
    attempt=Path(attempt);context_path=attempt/'traffic-context.json'
    motion_path=attempt/'native-motion.jsonl';frames_path=attempt/'video_frames.jsonl'
    for path in (context_path,motion_path,frames_path):
        if not path.is_file():raise ValueError('Missing required source: '+path.name)
    context=json.loads(context_path.read_text());region=context.get('conflict_region')
    if context.get('source_kind')!='original_native' or context.get('other_highway_use_reviewed') is not True or context.get('driver_control_reviewed') is not True:
        raise ValueError('Original highway-use or driver-control source unreviewed')
    if context.get('section_stem_recovered') is not True:
        raise ValueError('Parent statutory section source unreviewed')
    if not isinstance(region,dict) or any(type(region.get(k)) not in (int,float) for k in ('x_min_m','x_max_m','y_min_m','y_max_m')):
        raise ValueError('Original conflict region missing')
    motion,frames=rows(motion_path),rows(frames_path)
    previous=-1;backing=[];other_moving=[];joint=[];ego_entry=None;other_entry=None;min_gap=None
    actor_ids=None
    for index,(row,frame) in enumerate(zip(motion,frames)):
        native=row.get('native_frame')
        if type(native) is not int or native<=previous or frame.get('native_frame')!=native:
            raise ValueError('Original Native frame join differs')
        previous=native
        if row.get('video_frame')!=index or frame.get('video_frame')!=index or abs(row.get('time_s',-1)-index/20)>1e-6 or abs(frame.get('time_s',-1)-index/20)>1e-6:
            raise ValueError('Original video frame/time join differs')
        if frame.get('camera_native_frames')!={name:native for name in CAMERAS}:
            raise ValueError('Original four-camera join differs')
        ego_row,other_row=row.get('ego',{}),row.get('other',{})
        ego,ev=xy(ego_row);other,ov=xy(other_row)
        if context.get('fixture_kind')!='synthetic_diagnostic_only':
            ids=(ego_row.get('actor_id'),other_row.get('actor_id'))
            if any(type(v) is not int for v in ids) or ids[0]==ids[1] or (actor_ids is not None and ids!=actor_ids):
                raise ValueError('Distinct original vehicle actor identity missing or changed')
            actor_ids=ids
            if not all(str(v.get('blueprint_id','')).startswith('vehicle.') for v in (ego_row,other_row)):
                raise ValueError('Original vehicle classification missing')
        if ev[0]<-.1:backing.append(index)
        if math.hypot(*ov)>.1:other_moving.append(index)
        if inside(ego,region) and ego_entry is None:ego_entry=index
        if inside(other,region) and other_entry is None:other_entry=index
        if ev[0]<-.1 and math.hypot(*ov)>.1:
            joint.append(index)
            gap=math.hypot(ego[0]-other[0],ego[1]-other[1])
            min_gap=gap if min_gap is None else min(min_gap,gap)
    for name in CAMERAS:
        if not (attempt/(name+'.mkv')).is_file():raise ValueError('Missing required source: '+name+'.mkv')
    return {'format':'c230259-backing-moving-traffic-raw-sequence-v1','frame_count':FRAMES,
        'rate_hz':20,'backing_frame_count':len(backing),'other_moving_frame_count':len(other_moving),
        'simultaneous_backing_and_other_moving_frame_count':len(joint),
        'minimum_center_gap_during_simultaneous_motion_m':min_gap,
        'ego_first_conflict_region_frame':ego_entry,'other_first_conflict_region_frame':other_entry,
        'pedestrian_presence_reviewed':context.get('pedestrian_presence_reviewed') is True,
        'section_stem_recovered':context.get('section_stem_recovered') is True,
        'right_of_way_verdict':'unresolved','legal_verdict_claimed':False,'physical_acceptance_claimed':False,
        'source_sha256':{p.name:sha(p) for p in (context_path,motion_path,frames_path)},
        'camera_video_sha256':{name:sha(attempt/(name+'.mkv')) for name in CAMERAS}}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise ValueError('Use fresh measurement output')
    value=measure(args.attempt);args.output.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'backing_frame_count':value['backing_frame_count'],
        'simultaneous_backing_and_other_moving_frame_count':value['simultaneous_backing_and_other_moving_frame_count'],
        'right_of_way_verdict':'unresolved'}))


if __name__=='__main__':main()
