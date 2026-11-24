"""Measure original solid-line geometry and lane transition without legal cutoff."""
import argparse
import hashlib
import json
import math
from pathlib import Path

FRAMES=600
CAMERAS=('overview','separator_side','entrance_view','traffic_view')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    if not path.is_file():raise ValueError('Missing required source: '+path.name)
    data=[json.loads(line) for line in path.read_text().splitlines()]
    if len(data)!=FRAMES:raise ValueError('Original source must contain 600 frames')
    return data


def body_range(points):
    if not isinstance(points,list) or len(points)<4:raise ValueError('Original full-body points missing')
    if any(not isinstance(p,list) or len(p)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in p) for p in points):
        raise ValueError('Original full-body point invalid')
    return min(p[1] for p in points),max(p[1] for p in points)


def measure(attempt):
    attempt=Path(attempt);context_path=attempt/'separator-context.json'
    motion_path=attempt/'native-motion.jsonl';frames_path=attempt/'video_frames.jsonl'
    for path in (context_path,motion_path,frames_path):
        if not path.is_file():raise ValueError('Missing required source: '+path.name)
    context=json.loads(context_path.read_text());sep=context.get('separator')
    if context.get('source_kind')!='original_native' or any(context.get(key) is not True for key in
        ('public_highway_reviewed','legal_controlled_access_reviewed','entrance_lane_function_reviewed','official_line_reviewed')):
        raise ValueError('Original controlled-access line and lane functions unreviewed')
    if not isinstance(sep,dict) or sep.get('form')!='solid' or sep.get('color')!='white' or type(sep.get('y_m')) not in (int,float):
        raise ValueError('Original solid-white separator missing')
    motion,frames=rows(motion_path),rows(frames_path)
    previous=-1;straddle=[];traffic_centers=[];lane_ids=set();last_outer=None
    for index,(row,frame) in enumerate(zip(motion,frames)):
        native=row.get('native_frame')
        if type(native) is not int or native<=previous or frame.get('native_frame')!=native:
            raise ValueError('Original Native frame join differs')
        previous=native
        if row.get('video_frame')!=index or frame.get('video_frame')!=index or abs(row.get('time_s',-1)-index/20)>1e-6 or abs(frame.get('time_s',-1)-index/20)>1e-6:
            raise ValueError('Original video frame/time join differs')
        if frame.get('camera_native_frames')!={name:native for name in CAMERAS}:
            raise ValueError('Original four-camera join differs')
        ego=row.get('ego',{});center=ego.get('center_xy_m')
        if not isinstance(center,list) or len(center)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in center):
            raise ValueError('Original ego center missing')
        ymin,ymax=body_range(ego.get('body_xy_m'))
        if ymin<sep['y_m']<ymax:straddle.append(index)
        if center[1]>sep['y_m']:traffic_centers.append(index)
        lane=row.get('lane_id')
        if lane not in (-1,-2):raise ValueError('Original lane readback differs')
        lane_ids.add(lane)
        if lane==-2:last_outer=index
    for name in CAMERAS:
        if not (attempt/(name+'.mkv')).is_file():raise ValueError('Missing required source: '+name+'.mkv')
    return {'format':'c245532-solid-white-separator-raw-geometry-v1','frame_count':FRAMES,
        'rate_hz':20,'first_body_straddle_frame':straddle[0] if straddle else None,
        'body_straddle_frame_count':len(straddle),
        'first_traffic_side_center_frame':traffic_centers[0] if traffic_centers else None,
        'last_outer_lane_frame':last_outer,'native_lane_ids_seen':sorted(lane_ids),
        'vehicle_driver_scope_reviewed':context.get('vehicle_driver_scope_reviewed') is True,
        'emergency_necessity_reviewed':context.get('emergency_necessity_reviewed') is True,
        'subsection_3_conditions_reviewed':context.get('subsection_3_conditions_reviewed') is True,
        'shoulder_permission_treated_as_crossing_authorization':False,
        'statutory_crossing_cutoff_adopted':False,'crossing_verdict':'unresolved',
        'legal_verdict_claimed':False,'physical_acceptance_claimed':False,
        'source_sha256':{p.name:sha(p) for p in (context_path,motion_path,frames_path)},
        'camera_video_sha256':{name:sha(attempt/(name+'.mkv')) for name in CAMERAS}}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise ValueError('Use fresh measurement output')
    value=measure(args.attempt);args.output.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'body_straddle_frame_count':value['body_straddle_frame_count'],
        'first_traffic_side_center_frame':value['first_traffic_side_center_frame'],
        'crossing_verdict':'unresolved'}))


if __name__=='__main__':main()
