"""Check the moving-versus-stopped synthetic source contrast and frame join."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit(mutated=False):
    moving = HERE / 'current-fixture/controlled_1'
    stopped = HERE / 'current-fixture/stopped_referral'
    if sha(moving / 'road.xodr') != sha(stopped / 'road.xodr') or sha(moving / 'video_frames.jsonl') != sha(stopped / 'video_frames.jsonl'):
        raise ValueError('Stopped comparison changed road or frame/time join')
    a, b = rows(moving / 'vehicle_poses.jsonl'), rows(stopped / 'vehicle_poses.jsonl')
    if mutated:
        b[230]['emergency']['speed_mps'] = 2
    if len(a) != 600 or len(b) != 600 or a[:100] != b[:100]:
        raise ValueError('Stopped comparison changed initial actor trajectories')
    for i, (left, right) in enumerate(zip(a, b)):
        if (left['video_frame'] != i or right['video_frame'] != i or
                left['native_frame'] != right['native_frame'] or
                left['emergency']['special1_light_on'] != right['emergency']['special1_light_on']):
            raise ValueError('Stopped comparison changed fixed frame or lamp state')
    if (not all(abs(row['emergency']['speed_mps']) <= .15 for row in b[220:300]) or
            not all(row['emergency']['speed_mps'] > 1 for row in a[220:300])):
        raise ValueError('Stopped comparison lacks distinct source motion')
    if (not all(abs(row['ego']['y_m'] + 2.5) <= .15 and row['ego']['speed_mps'] <= .15
                for row in b[120:300]) or
            any(row['emergency']['x_m'] + row['emergency']['half_length_m'] <
                row['ego']['x_m'] - row['ego']['half_length_m'] for row in b)):
        raise ValueError('Stopped source or subject holding position differs')
    first = json.loads((moving / 'emergency_context.json').read_text())
    second = json.loads((stopped / 'emergency_context.json').read_text())
    for name in ('emergency_vehicle_authorized', 'qualifying_flash_equipment_reviewed',
                 'officer_directed_otherwise', 'emergency_authorization_source',
                 'qualifying_flash_equipment_source'):
        if first.get(name) != second.get(name):
            raise ValueError('Stopped comparison changed source qualification')
    return {'format': 'c405647-2f-stopped-comparison-audit-v1',
            'comparison_id': HERE.name + '__stopped_referral_comparison',
            'case_ids': [HERE.name + '__controlled_1', HERE.name + '__stopped_referral'],
            'fixed_road_sha256': sha(moving / 'road.xodr'),
            'fixed_frame_map_sha256': sha(moving / 'video_frames.jsonl'),
            'initial_actor_frames': 100,
            'deliberate_difference': 'moving source continues and passes versus stops',
            'diagnostic_only': True, 'original_native_observed': False,
            'nrs_484b_607_exact_text_supplied': False, 'legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.negative), indent=2))
