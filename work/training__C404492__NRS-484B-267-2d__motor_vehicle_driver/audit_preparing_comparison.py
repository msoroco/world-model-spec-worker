"""Compare the selected moving and visibly preparing source-vehicle phases."""
import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(moving, preparing):
    moving, preparing = Path(moving), Path(preparing)
    left = rows(moving / 'vehicle_poses.jsonl')
    right = rows(preparing / 'vehicle_poses.jsonl')
    left_frames = rows(moving / 'video_frames.jsonl')
    right_frames = rows(preparing / 'video_frames.jsonl')
    if len(left) != len(right) or len(left) != 600 or left_frames != right_frames:
        raise ValueError('Original 600-frame camera/time policy differs')
    left_context = json.loads((moving / 'emergency_context.json').read_text())
    right_context = json.loads((preparing / 'emergency_context.json').read_text())
    if not left_context['case_id'].endswith('__controlled_1') or not right_context['case_id'].endswith('__preparing_movement'):
        raise ValueError('Wrong exact comparison cases')
    for key in ('assignment_id', 'review_kind', 'emergency_vehicle_authorized',
                'qualifying_flash_equipment_reviewed', 'officer_directed_otherwise',
                'ego_actor_id', 'emergency_actor_id', 'ego_driver_source',
                'ego_vehicle_source', 'emergency_authorization_source',
                'qualifying_flash_equipment_source', 'flashing_light_visual_source',
                'lane_boundary_source', 'officer_direction_review_source'):
        if left_context.get(key) != right_context.get(key):
            raise ValueError('Fixed statutory context differs: ' + key)
    for a, b, frame in zip(left, right, left_frames):
        if (a['video_frame'] != frame['video_frame'] or b['video_frame'] != frame['video_frame']
                or a['native_frame'] != frame['native_frame'] or b['native_frame'] != frame['native_frame']):
            raise ValueError('Original Native source join differs')
        for actor in ('ego', 'emergency'):
            for key in ('actor_id', 'heading_rad', 'half_length_m', 'half_width_m', 'y_m'):
                if a[actor][key] != b[actor][key]:
                    raise ValueError('Fixed actor geometry or lane differs: ' + actor + '.' + key)
        if a['emergency']['flashing_light_phase_on'] != b['emergency']['flashing_light_phase_on']:
            raise ValueError('Flashing-light phase differs')
    if left[0]['emergency']['speed_mps'] <= 0 or right[0]['emergency']['speed_mps'] != 0:
        raise ValueError('Moving versus stopped initial phase absent')
    if any(row['emergency']['speed_mps'] != 0 for row in right[:80]):
        raise ValueError('Preparing case lacks stopped phase')
    visible = sum(row['emergency'].get('visible_vehicle_movement') is True for row in right)
    if visible != 40 or right_context.get('preparing_to_move_reviewed') is not True:
        raise ValueError('Source-shaped visible preparation phase absent')
    if any(row['emergency']['speed_mps'] <= 0 for row in left):
        raise ValueError('Moving reference stopped unexpectedly')
    return {'format': 'c404492-visible-preparation-comparison-v1',
            'passed': True, 'moving_case_id': left_context['case_id'],
            'preparing_case_id': right_context['case_id'],
            'moving_source_sha256': sha(moving / 'vehicle_poses.jsonl'),
            'preparing_source_sha256': sha(preparing / 'vehicle_poses.jsonl'),
            'visible_preparation_frames': visible,
            'fixed_actor_geometry_lane_and_camera_policy': True,
            'diagnostic_only': True, 'physical_acceptance_claimed': False,
            'legal_result': None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--moving', type=Path, required=True)
    parser.add_argument('--preparing', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.moving, args.preparing), indent=2))


if __name__ == '__main__':
    main()
