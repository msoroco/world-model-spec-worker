"""Measure original school-zone trajectory and person position without legal thresholds."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from review_context import verified_sources

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
    return value


def inside(point,zone):
    return zone['x_min_m']<=point[0]<=zone['x_max_m'] and zone['y_min_m']<=point[1]<=zone['y_max_m']


def measure(attempt):
    attempt=Path(attempt);context_path=attempt/'school-context.json'
    motion_path=attempt/'native-motion.jsonl';frames_path=attempt/'video_frames.jsonl'
    for path in (context_path,motion_path,frames_path):
        if not path.is_file():raise ValueError('Missing required source: '+path.name)
    context=json.loads(context_path.read_text());zone=context.get('zone')
    if context.get('source_kind')!='original_native':
        raise ValueError('Original school-zone context missing')
    if context.get('path_is_kinematic') is not False:
        raise ValueError('Physically driven original path required')
    review=verified_sources(attempt,context)
    if not isinstance(zone,dict) or any(type(zone.get(k)) not in (int,float) for k in ('x_min_m','x_max_m','y_min_m','y_max_m')):
        raise ValueError('Original zone extent missing')
    motions,frames=rows(motion_path),rows(frames_path)
    previous=-1;headings=[];inside_frames=[];person_inside=[];positions=[]
    for index,(row,frame) in enumerate(zip(motions,frames)):
        native=row.get('native_frame')
        if type(native) is not int or native<=previous or frame.get('native_frame')!=native:
            raise ValueError('Original Native frame join differs')
        previous=native
        if row.get('video_frame')!=index or frame.get('video_frame')!=index or abs(row.get('time_s',-1)-index/20)>1e-6 or abs(frame.get('time_s',-1)-index/20)>1e-6:
            raise ValueError('Original video frame/time join differs')
        if frame.get('camera_native_frames')!={name:native for name in CAMERAS}:
            raise ValueError('Original four-camera join differs')
        ego=row.get('ego',{});person=row.get('other_person',{})
        control=row.get('control')
        if row.get('kinematic_path_only') is not False or not isinstance(control,dict) or any(
            type(control.get(key)) not in (int,float) or not math.isfinite(control[key])
            for key in ('steer','throttle','brake')):
            raise ValueError('Original physical vehicle control missing')
        point=xy(ego);person_point=xy(person);heading=ego.get('heading_deg')
        if type(heading) not in (int,float) or not math.isfinite(heading):
            raise ValueError('Original heading missing')
        headings.append(heading);positions.append(point)
        if inside(point,zone):inside_frames.append(index)
        if inside(person_point,zone):person_inside.append(index)
    for name in CAMERAS:
        if not (attempt/(name+'.mkv')).is_file():raise ValueError('Missing required source: '+name+'.mkv')
    cumulative=sum(abs(((b-a+180)%360)-180) for a,b in zip(headings,headings[1:]))
    return {'format':'c263073-school-zone-turn-raw-motion-v1','frame_count':FRAMES,
        'rate_hz':20,'first_ego_zone_frame':inside_frames[0] if inside_frames else None,
        'ego_zone_frame_count':len(inside_frames),'other_person_zone_frame_count':len(person_inside),
        'initial_heading_deg':headings[0],'final_heading_deg':headings[-1],
        'cumulative_absolute_heading_change_deg':cumulative,
        'path_is_kinematic':context.get('path_is_kinematic') is True,
        'child_age_or_presence_radius_adopted':False,'legal_heading_threshold_adopted':False,
        'session_operation_civil_time_reviewed':context.get('session_operation_civil_time_reviewed') is True,
        'beacon_and_sign_state_reviewed':context.get('beacon_and_sign_state_reviewed') is True,
        'all_five_exceptions_reviewed':context.get('all_five_exceptions_reviewed') is True,
        'independent_source_review':review,
        'u_turn_legal_verdict':'unresolved','physical_acceptance_claimed':False,
        'source_sha256':{p.name:sha(p) for p in (context_path,motion_path,frames_path)},
        'camera_video_sha256':{name:sha(attempt/(name+'.mkv')) for name in CAMERAS}}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise ValueError('Use fresh measurement output')
    value=measure(args.attempt);args.output.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'cumulative_absolute_heading_change_deg':value['cumulative_absolute_heading_change_deg'],
        'u_turn_legal_verdict':'unresolved'}))


if __name__=='__main__':main()
