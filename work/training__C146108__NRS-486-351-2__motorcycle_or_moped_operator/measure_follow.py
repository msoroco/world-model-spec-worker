"""Source-bound same-lane following counterpart for the controlled pass."""
import hashlib
import json
from pathlib import Path

from measure_pass import CAMERAS, FRAMES, LANE_Y, RATE_HZ, bounds, source_rows


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(attempt):
    attempt = Path(attempt)
    names = ('participant-poses.jsonl', 'video_frames.jsonl', 'pass-context.json', 'road.xodr')
    paths = {name: attempt / name for name in names}
    for name, path in paths.items():
        if not path.is_file():
            raise ValueError('Missing required source: ' + name)
    poses = source_rows(paths['participant-poses.jsonl'])
    frames = source_rows(paths['video_frames.jsonl'])
    context = json.loads(paths['pass-context.json'].read_text())
    if context.get('rider_class') != 'motorcycle' or context.get('passed_class') != 'motor_vehicle':
        raise ValueError('Following participant classifications differ')
    if 'one-way-two-lane' not in paths['road.xodr'].read_text():
        raise ValueError('One-way two-lane original road missing')
    if any(not (attempt / (camera + '.mkv')).is_file() for camera in CAMERAS):
        raise ValueError('Four original camera sources required')
    gaps = []
    previous_native = -1
    for index, (pose, frame) in enumerate(zip(poses, frames)):
        native = pose.get('native_frame')
        if type(native) is not int or native <= previous_native or frame.get('native_frame') != native:
            raise ValueError('Original Native frame join differs')
        previous_native = native
        if pose.get('video_frame') != index or frame.get('video_frame') != index or \
                abs(pose.get('time_s', -1) - index / RATE_HZ) > 1e-6 or \
                abs(frame.get('time_s', -1) - index / RATE_HZ) > 1e-6 or \
                frame.get('camera_native_frames') != {camera: native for camera in CAMERAS}:
            raise ValueError('Original four-view time/frame join differs')
        rider = bounds(pose.get('rider_body_xy_m'))
        other = bounds(pose.get('motor_body_xy_m'))
        for body in (rider, other):
            if body[2] < LANE_Y[0] or body[3] > LANE_Y[1]:
                raise ValueError('Participant body departed shared lane')
        gap = other[0] - rider[1]
        if gap <= 0:
            raise ValueError('Following source entered longitudinal overlap')
        gaps.append(gap)
    if len(gaps) != FRAMES:
        raise ValueError('Incomplete following source')
    return {'format': 'c146108-motorcycle-same-lane-follow-measurement-v1',
            'frame_count': FRAMES, 'rate_hz': RATE_HZ,
            'minimum_longitudinal_body_gap_m': min(gaps),
            'longitudinal_overlap_frames': 0,
            'same_lane_all_frames': True,
            'source_sha256': {name: sha(path) for name, path in paths.items()},
            'camera_video_sha256': {name: sha(attempt / (name + '.mkv')) for name in CAMERAS},
            'legal_verdict_claimed': False, 'physical_acceptance_claimed': False}
