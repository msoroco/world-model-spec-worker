"""Source-bound motion indicator audit for the subsection 4 preparation branch.

This measures a vehicle becoming mobile after a stationary span. Whether that
movement was visible to the approaching driver requires original camera review.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def audit(root):
    root = Path(root)
    required = ('video_frames.jsonl', 'vehicle_poses.jsonl', 'emergency_context.json')
    if any(not (root / name).is_file() for name in required):
        raise ValueError('Frame, pose and context sources required')
    frames, poses = rows(root / required[0]), rows(root / required[1])
    context = json.loads((root / required[2]).read_text())
    if len(frames) != 600 or len(poses) != 600:
        raise ValueError('Full 600-frame original span required')
    if not context.get('visibility_review_source') or not context.get('reviewer'):
        raise ValueError('Independent visibility source and reviewer required')
    expected = context.get('native_source_hashes', {})
    for name in required[:2]:
        if expected.get(name) != sha(root / name):
            raise ValueError('Original source hash differs: ' + name)
    speeds = []
    last_frame = -1
    for index, (frame, pose) in enumerate(zip(frames, poses)):
        native = frame.get('native_frame')
        if (frame.get('video_frame') != index or pose.get('video_frame') != index or
                pose.get('native_frame') != native or type(native) is not int or native <= last_frame):
            raise ValueError('Original frame and pose join differs')
        vehicle = pose.get('emergency', {})
        if vehicle.get('actor_id') != context.get('emergency_actor_id'):
            raise ValueError('Source vehicle actor differs')
        speed = vehicle.get('speed_mps')
        if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
            raise ValueError('Source vehicle motion missing')
        speeds.append(speed)
        last_frame = native
    if max(speeds[:80]) > .15 or min(speeds[120:180]) < .5:
        raise ValueError('Stationary-to-moving source indicator not measured')
    first_move = next((i for i, speed in enumerate(speeds) if speed > .5), None)
    if first_move is None or first_move < 80 or first_move > 120:
        raise ValueError('Preparation movement transition outside source span')
    return {'case_id': context['case_id'], 'indicator': 'vehicle_movement',
            'first_motion_frame': first_move, 'source_sha256': {name: sha(root / name) for name in required},
            'visual_visibility_verified': False, 'physical_acceptance_claimed': False,
            'legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.source), sort_keys=True))
