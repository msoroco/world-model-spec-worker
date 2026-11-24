"""Independent source-bound comparison for pre-approach vehicle movement."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def audit(base, variant):
    base, variant = Path(base), Path(variant)
    for root in (base, variant):
        if any(not (root / name).is_file() for name in
               ('video_frames.jsonl', 'vehicle_poses.jsonl', 'emergency_context.json', 'road.xodr')):
            raise ValueError('Comparison original source missing')
    if sha(base / 'road.xodr') != sha(variant / 'road.xodr'):
        raise ValueError('Fixed road geometry changed')
    base_frames, visible_frames = rows(base / 'video_frames.jsonl'), rows(variant / 'video_frames.jsonl')
    base_poses, visible_poses = rows(base / 'vehicle_poses.jsonl'), rows(variant / 'vehicle_poses.jsonl')
    if len(base_frames) != 600 or base_frames != visible_frames or len(base_poses) != len(visible_poses):
        raise ValueError('Fixed frame and time join changed')
    initial = 0
    prep = 0
    for index, (left, right) in enumerate(zip(base_poses, visible_poses)):
        if (left['native_frame'] != right['native_frame'] or
                left['ego']['actor_id'] != right['ego']['actor_id'] or
                left['emergency']['actor_id'] != right['emergency']['actor_id'] or
                left['emergency']['special1_light_on'] != right['emergency']['special1_light_on']):
            raise ValueError('Fixed identity or flashing-light program changed')
        if index < 80:
            if left['ego'] != right['ego'] or left['emergency'] != right['emergency']:
                raise ValueError('Fixed initial trajectories changed')
            initial += 1
        elif 80 <= index < 100:
            if left['emergency']['speed_mps'] > .15 or right['emergency']['speed_mps'] < .2:
                raise ValueError('Pre-approach movement difference missing')
            prep += 1
        elif (left['emergency']['speed_mps'] < 1.5 or
              abs(left['emergency']['speed_mps'] - right['emergency']['speed_mps']) > .01):
            raise ValueError('Fixed full-approach speed changed')
    return {'format': 'c405647-2f-visible-movement-comparison-v1',
            'case_ids': [json.loads((base / 'emergency_context.json').read_text())['case_id'],
                         json.loads((variant / 'emergency_context.json').read_text())['case_id']],
            'fixed_initial_frames': initial, 'differing_preparation_frames': prep,
            'source_sha256': {'baseline': sha(base / 'vehicle_poses.jsonl'),
                              'visible_movement': sha(variant / 'vehicle_poses.jsonl')},
            'visual_visibility_verified': False, 'physical_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', default=str(HERE / 'current-fixture/controlled_1'))
    parser.add_argument('--visible', default=str(HERE / 'draft-visible/source'))
    args = parser.parse_args()
    print(json.dumps(audit(args.baseline, args.visible), sort_keys=True))
