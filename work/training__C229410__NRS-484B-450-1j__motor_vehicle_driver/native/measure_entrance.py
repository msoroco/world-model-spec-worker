"""Source-bound vehicle-to-driveway raw geometry; no statutory reference-point choice."""
import argparse
import hashlib
import json
import math
from pathlib import Path

FRAMES=600
CAMERAS=('overview','entrance','near_side','approach')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    if not path.is_file():raise ValueError('Missing required source: '+path.name)
    data=[json.loads(line) for line in path.read_text().splitlines()]
    if len(data)!=FRAMES:raise ValueError('Original source must contain 600 frames')
    return data


def bbox(points):
    if not isinstance(points,list) or len(points)<4:raise ValueError('Original full vehicle body missing')
    if any(not isinstance(p,list) or len(p)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in p) for p in points):
        raise ValueError('Original body corner invalid')
    return min(p[0] for p in points),max(p[0] for p in points),min(p[1] for p in points),max(p[1] for p in points)


def gap(xmin,xmax,entrance):
    return max(0,entrance['x_min_m']-xmax,xmin-entrance['x_max_m'])


def measure(attempt):
    attempt=Path(attempt);context_path=attempt/'entrance-context.json'
    motion_path=attempt/'native-vehicle.jsonl';frames_path=attempt/'video_frames.jsonl'
    for path in (context_path,motion_path,frames_path):
        if not path.is_file():raise ValueError('Missing required source: '+path.name)
    context=json.loads(context_path.read_text());entrance=context.get('entrance')
    if context.get('source_kind')!='original_native' or any(context.get(key) is not True for key in
        ('fire_station_identity_reviewed','driveway_entrance_reviewed','highway_side_reviewed')):
        raise ValueError('Original fire-station entrance and road-side identity unreviewed')
    if not isinstance(entrance,dict) or any(type(entrance.get(k)) not in (int,float) for k in ('x_min_m','x_max_m','road_edge_y_m')):
        raise ValueError('Original entrance extent missing')
    motions,frames=rows(motion_path),rows(frames_path)
    previous=-1;stationary=[];source_sides=set()
    for i,(motion,frame) in enumerate(zip(motions,frames)):
        native=motion.get('native_frame')
        if type(native) is not int or native<=previous or frame.get('native_frame')!=native:
            raise ValueError('Original Native frame join differs')
        previous=native
        if motion.get('video_frame')!=i or frame.get('video_frame')!=i or abs(motion.get('time_s',-1)-i/20)>1e-6 or abs(frame.get('time_s',-1)-i/20)>1e-6:
            raise ValueError('Original video frame/time join differs')
        if frame.get('camera_native_frames')!={name:native for name in CAMERAS}:
            raise ValueError('Original four-camera join differs')
        xmin,xmax,ymin,ymax=bbox(motion.get('body_xy_m'))
        speed=motion.get('speed_mps')
        if type(speed) not in (int,float) or not math.isfinite(speed) or speed<0:
            raise ValueError('Original speed invalid')
        side='south' if (ymin+ymax)/2<0 else 'north'
        source_sides.add(side)
        if speed==0:
            stationary.append({'frame':i,'body_edge_gap_m':gap(xmin,xmax,entrance),
                'body_x_min_m':xmin,'body_x_max_m':xmax,'road_side':side})
    for name in CAMERAS:
        if not (attempt/(name+'.mkv')).is_file():raise ValueError('Missing required source: '+name+'.mkv')
    return {'format':'c229410-fire-station-entrance-raw-geometry-v1','frame_count':FRAMES,
        'rate_hz':20,'stationary_sample_count':len(stationary),
        'stationary_min_body_edge_gap_m':min((x['body_edge_gap_m'] for x in stationary),default=None),
        'stationary_max_body_edge_gap_m':max((x['body_edge_gap_m'] for x in stationary),default=None),
        'road_sides_seen':sorted(source_sides),'stationary_samples':stationary,
        'parking_activity_reviewed':context.get('parking_activity_reviewed') is True,
        'traffic_conflict_reviewed':context.get('traffic_conflict_reviewed') is True,
        'law_officer_device_direction_reviewed':context.get('law_officer_device_direction_reviewed') is True,
        'statutory_reference_point_method_adopted':False,'twenty_foot_clause_verdict':'unresolved',
        'opposite_side_seventy_five_foot_clause_verdict':'not_measured',
        'legal_verdict_claimed':False,'physical_acceptance_claimed':False,
        'source_sha256':{p.name:sha(p) for p in (context_path,motion_path,frames_path)},
        'camera_video_sha256':{name:sha(attempt/(name+'.mkv')) for name in CAMERAS}}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise ValueError('Use fresh measurement output')
    value=measure(args.attempt);args.output.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'stationary_min_body_edge_gap_m':value['stationary_min_body_edge_gap_m'],
        'statutory_reference_point_method_adopted':False}))


if __name__=='__main__':main()
