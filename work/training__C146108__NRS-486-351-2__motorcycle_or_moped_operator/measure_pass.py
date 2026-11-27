"""Measure a same-lane pass from retained original Native pose and frame sources."""
import argparse
import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
RATE_HZ = 20
LANE_Y = (-6.0, 0.0)
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_rows(path):
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if len(rows) != FRAMES:
        raise ValueError('Original source does not contain 600 frames: ' + path.name)
    return rows


def bounds(points):
    if not isinstance(points, list) or len(points) != 4:
        raise ValueError('Original body corners incomplete')
    if any(not isinstance(p, list) or len(p) != 2 or
           any(type(v) not in (int, float) or not math.isfinite(v) for v in p) for p in points):
        raise ValueError('Original body corner invalid')
    return min(p[0] for p in points), max(p[0] for p in points), min(p[1] for p in points), max(p[1] for p in points)


def measure(attempt):
    attempt = Path(attempt)
    paths = {name: attempt / name for name in ('participant-poses.jsonl', 'video_frames.jsonl', 'pass-context.json', 'road.xodr')}
    for name, path in paths.items():
        if not path.is_file():
            raise ValueError('Missing required source: ' + name)
    poses = source_rows(paths['participant-poses.jsonl'])
    frames = source_rows(paths['video_frames.jsonl'])
    context = json.loads(paths['pass-context.json'].read_text())
    if context.get('rider_class') != 'motorcycle' or context.get('passed_class') != 'motor_vehicle':
        raise ValueError('Native participant classifications are not the requested motorcycle and other vehicle')
    if not all((attempt / (name + '.mkv')).is_file() for name in CAMERAS):
        raise ValueError('Missing required four original camera videos')
    if 'one-way-two-lane' not in paths['road.xodr'].read_text():
        raise ValueError('Original one-way multilane road source missing')
    first_behind = first_overlap = first_clear = None
    min_lateral_gap = math.inf
    overlap_frames = 0
    previous_native = -1
    for index, (pose, frame) in enumerate(zip(poses, frames)):
        native = pose.get('native_frame')
        if type(native) is not int or native <= previous_native or frame.get('native_frame') != native:
            raise ValueError('Original Native frame join differs')
        previous_native = native
        if pose.get('video_frame') != index or frame.get('video_frame') != index:
            raise ValueError('Original video frame join differs')
        if abs(pose.get('time_s', -1) - index / RATE_HZ) > 1e-6 or abs(frame.get('time_s', -1) - index / RATE_HZ) > 1e-6:
            raise ValueError('Original frame time differs')
        if frame.get('camera_native_frames') != {name: native for name in CAMERAS}:
            raise ValueError('Four original camera frames are not synchronized')
        rider = bounds(pose.get('rider_body_xy_m'))
        motor = bounds(pose.get('motor_body_xy_m'))
        for body in (rider, motor):
            if body[2] < LANE_Y[0] or body[3] > LANE_Y[1]:
                raise ValueError('Participant body departed shared lane at frame ' + str(index))
        if rider[1] < motor[0] and first_behind is None:
            first_behind = index
        if rider[1] >= motor[0] and rider[0] <= motor[1]:
            overlap_frames += 1
            if first_overlap is None:
                first_overlap = index
            lateral_gap = max(motor[2] - rider[3], rider[2] - motor[3], 0.0)
            min_lateral_gap = min(min_lateral_gap, lateral_gap)
        if rider[0] > motor[1] and first_overlap is not None and first_clear is None:
            first_clear = index
    if first_behind is None or first_overlap is None or first_clear is None or not first_behind < first_overlap < first_clear:
        raise ValueError('Original source does not show a complete same-lane behind-to-ahead pass')
    return {'format': 'c146108-motorcycle-same-lane-pass-measurement-v1',
            'frame_count': FRAMES, 'rate_hz': RATE_HZ, 'shared_lane_bounds_y_m': list(LANE_Y),
            'first_behind_frame': first_behind, 'first_overlap_frame': first_overlap,
            'first_clear_ahead_frame': first_clear, 'longitudinal_overlap_frames': overlap_frames,
            'minimum_lateral_surface_gap_during_overlap_m': min_lateral_gap,
            'source_sha256': {name: sha(path) for name, path in paths.items()},
            'camera_video_sha256': {name: sha(attempt / (name + '.mkv')) for name in CAMERAS},
            'subsection_3_exception_status': 'inapplicable_to_motorcycle_and_car_pair',
            'driver_consent_status': 'unobserved', 'legal_verdict_claimed': False,
            'physical_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Use a fresh measurement output')
    result = measure(args.attempt)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'first_overlap_frame': result['first_overlap_frame'],
                      'first_clear_ahead_frame': result['first_clear_ahead_frame'],
                      'legal_verdict_claimed': False}))


if __name__ == '__main__':
    main()
