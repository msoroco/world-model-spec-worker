"""Measure original full-body overlap with a sourced access aisle; no legal parking verdict."""
import argparse
import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    values = [json.loads(line) for line in path.read_text().splitlines()]
    if len(values) != FRAMES:
        raise ValueError('Original source must contain 600 frames')
    return values


def body_bbox(points):
    if not isinstance(points, list) or len(points) < 4:
        raise ValueError('Original full-body corners incomplete')
    if any(not isinstance(p, list) or len(p) not in (2, 3) or any(type(v) not in (int, float) or not math.isfinite(v) for v in p) for p in points):
        raise ValueError('Original body corner invalid')
    return min(p[0] for p in points), max(p[0] for p in points), min(p[1] for p in points), max(p[1] for p in points)


def area(box, aisle):
    return max(0, min(box[1], aisle['x_max_m']) - max(box[0], aisle['x_min_m'])) * max(0, min(box[3], aisle['y_max_m']) - max(box[2], aisle['y_min_m']))


def measure(attempt):
    attempt = Path(attempt)
    context_path = attempt / 'aisle-context.json'
    motion_path = attempt / 'native-vehicle.jsonl'
    frames_path = attempt / 'video_frames.jsonl'
    for path in (context_path, motion_path, frames_path):
        if not path.is_file():
            raise ValueError('Missing required source: ' + path.name)
    context = json.loads(context_path.read_text())
    aisle = context.get('access_aisle')
    if context.get('source_kind') != 'original_native' or context.get('premises_public_access_reviewed') is not True or context.get('access_aisle_designation_reviewed') is not True:
        raise ValueError('Original premises and access-aisle designation not established')
    if not isinstance(aisle, dict) or not all(type(aisle.get(k)) in (int, float) for k in ('x_min_m','x_max_m','y_min_m','y_max_m')):
        raise ValueError('Original access-aisle boundary missing')
    motions, frames = rows(motion_path), rows(frames_path)
    first_overlap = None; overlap_samples = 0; stationary_overlap_samples = 0
    first_stationary = None; last_stationary = None
    previous_native = -1
    for index, (motion, frame) in enumerate(zip(motions, frames)):
        native = motion.get('native_frame')
        if type(native) is not int or native <= previous_native or frame.get('native_frame') != native:
            raise ValueError('Original Native frame join differs')
        previous_native = native
        if motion.get('video_frame') != index or frame.get('video_frame') != index or abs(motion.get('time_s',-1)-index/20)>1e-6 or abs(frame.get('time_s',-1)-index/20)>1e-6:
            raise ValueError('Original video frame/time join differs')
        if frame.get('camera_native_frames') != {name: native for name in CAMERAS}:
            raise ValueError('Original four-camera join differs')
        box = body_bbox(motion.get('body_xy_m'))
        speed = motion.get('speed_mps')
        if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
            raise ValueError('Original vehicle speed invalid')
        overlap = area(box, aisle)
        if overlap > 0:
            overlap_samples += 1
            if first_overlap is None:first_overlap = index
        if speed == 0:
            if first_stationary is None:first_stationary = index
            last_stationary = index
            if overlap > 0:stationary_overlap_samples += 1
    for name in CAMERAS:
        if not (attempt / (name + '.mkv')).is_file():
            raise ValueError('Missing required source: ' + name + '.mkv')
    return {'format':'c200542-access-aisle-footprint-measurement-v1',
            'frame_count':FRAMES,'rate_hz':20,'first_overlap_frame':first_overlap,
            'overlap_samples':overlap_samples,'stationary_overlap_samples':stationary_overlap_samples,
            'first_stationary_frame':first_stationary,'last_stationary_frame':last_stationary,
            'parked_classification':'requires_independent_source_review',
            'legal_verdict_claimed':False,'physical_acceptance_claimed':False,
            'source_sha256':{p.name:sha(p) for p in (context_path,motion_path,frames_path)},
            'camera_video_sha256':{name:sha(attempt/(name+'.mkv')) for name in CAMERAS}}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise ValueError('Use a fresh measurement output')
    result=measure(args.attempt)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'stationary_overlap_samples':result['stationary_overlap_samples'],
                      'parked_classification':result['parked_classification']}))


if __name__=='__main__':main()
