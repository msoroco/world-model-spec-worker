"""Independent saved-source audit of the signed bicycle roadway comparison."""
import argparse
import json
from pathlib import Path

from measure import measure

REQUIRED = ('video_frames.jsonl', 'bicycle-poses.jsonl', 'restriction-context.json')


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def inspect(root, suffix):
    root = Path(root)
    for name in REQUIRED:
        if not (root / name).is_file():
            raise ValueError('Missing required source: ' + name)
    context = json.loads((root / 'restriction-context.json').read_text())
    if not context.get('case_id', '').endswith('__' + suffix):
        raise ValueError('Comparison exact case identity differs')
    return context, rows(root / 'bicycle-poses.jsonl'), rows(root / 'video_frames.jsonl'), measure(
        root / 'bicycle-poses.jsonl', root / 'restriction-context.json')


def audit(shoulder_root, roadway_root):
    shoulder, shoulder_poses, shoulder_frames, left = inspect(shoulder_root, 'probe_01')
    roadway, roadway_poses, roadway_frames, right = inspect(roadway_root, 'probe_02')
    fixed = ('rider_class', 'blueprint_id', 'sign_id', 'sign_text', 'sign_x_m',
             'sign_orientation', 'native_sign_survey', 'native_roadway_survey',
             'native_shoulder_survey', 'roadway_xy_m')
    if any(shoulder.get(key) != roadway.get(key) for key in fixed):
        raise ValueError('Comparison fixed sign, subtype or road context differs')
    if len(shoulder_poses) != 600 or len(roadway_poses) != 600:
        raise ValueError('Comparison missing original rider frames')
    for a, b, fa, fb in zip(shoulder_poses, roadway_poses, shoulder_frames, roadway_frames):
        if a['video_frame'] != b['video_frame'] or abs(a['time_s'] - b['time_s']) > .005:
            raise ValueError('Comparison fixed rider timing differs')
        if abs(a['rider_xy_m'][0] - b['rider_xy_m'][0]) > .05:
            raise ValueError('Comparison fixed longitudinal route differs')
        if any(abs(x-y) > .05 for x, y in zip(a['velocity_xy_mps'], b['velocity_xy_mps'])):
            raise ValueError('Comparison fixed speed/controller differs')
        if fa['video_frame'] != fb['video_frame'] or abs(fa['time_s'] - fb['time_s']) > .005:
            raise ValueError('Comparison fixed camera timing differs')
        if set(fa.get('camera_native_frames', {})) != set(fb.get('camera_native_frames', {})):
            raise ValueError('Comparison fixed camera set differs')
    if shoulder['target_surface'] != 'shoulder' or roadway['target_surface'] != 'roadway':
        raise ValueError('Comparison declared surface differs')
    if left['roadway_occupied_after_sign_frames'] != 0 or right['roadway_occupied_after_sign_frames'] <= 0:
        raise ValueError('Comparison lacks measured roadway-use contrast')
    return {'format': 'worker-comparison-audit', 'passed': True,
            'comparison_variable': 'original bicycle roadway use after the same sign',
            'fixed_context_keys': list(fixed),
            'shoulder_roadway_frames': left['roadway_occupied_after_sign_frames'],
            'roadway_roadway_frames': right['roadway_occupied_after_sign_frames'],
            'legal_verdict_claimed': False, 'physical_visibility_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--shoulder', required=True)
    parser.add_argument('--roadway', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.shoulder, args.roadway), sort_keys=True))
