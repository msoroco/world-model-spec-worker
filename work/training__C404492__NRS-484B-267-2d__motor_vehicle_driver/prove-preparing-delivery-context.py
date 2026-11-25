"""Exercise the independent original-source gate for visible preparation."""
import json
import argparse
import hashlib
from pathlib import Path

from delivery_audit import selected_statutory_context, visible_preparation_frames


CASE = 'training__C404492__NRS-484B-267-2d__motor_vehicle_driver__preparing_movement'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--poses', required=True, type=Path)
    args = parser.parse_args()
    source_keys = ('ego_driver_source', 'ego_vehicle_source',
                   'emergency_authorization_source',
                   'qualifying_flash_equipment_source',
                   'flashing_light_visual_source', 'lane_boundary_source',
                   'officer_direction_review_source',
                   'preparing_to_move_source', 'visible_vehicle_movement_source')
    context = {'case_id': CASE, 'review_kind': 'original_source_review',
               'reviewer': 'independent local reviewer',
               'emergency_vehicle_authorized': True,
               'qualifying_flash_equipment_reviewed': True,
               'officer_directed_otherwise': False,
               'preparing_to_move_reviewed': True,
               **{key: 'original-source:' + key for key in source_keys}}
    selected_statutory_context(context, CASE)
    rejected = []
    mutations = [('preparing_to_move_reviewed', False),
                 ('officer_directed_otherwise', True),
                 ('emergency_vehicle_authorized', False),
                 ('qualifying_flash_equipment_reviewed', False),
                 ('preparing_to_move_source', None),
                 ('visible_vehicle_movement_source', ''),
                 ('visible_vehicle_movement_source', 'synthetic-fixture:motion')]
    for key, value in mutations:
        changed = {**context, key: value}
        try:
            selected_statutory_context(changed, CASE)
        except ValueError:
            rejected.append(key)
        else:
            raise AssertionError('Unreviewed preparation context accepted: ' + key)
    poses = [json.loads(line) for line in args.poses.read_text().splitlines()]
    if len(poses) != 600:
        raise AssertionError('Diagnostic pose count differs')
    visible_count = visible_preparation_frames(poses)
    if visible_count != 40:
        raise AssertionError('Diagnostic visible-preparation count differs')
    missing = [{**pose, 'emergency': {**pose['emergency'],
                                     'visible_vehicle_movement': False}}
               for pose in poses]
    try:
        visible_preparation_frames(missing)
    except ValueError:
        rejected.append('visible_vehicle_movement_pose_frames')
    else:
        raise AssertionError('Absent source-observed movement accepted')
    print(json.dumps({'case_id': CASE, 'positive_passed': True,
                      'negative_checks': len(rejected),
                      'rejected_fields': rejected,
                      'source_sha256': hashlib.sha256(args.poses.read_bytes()).hexdigest(),
                      'visible_preparation_frames': visible_count,
                      'original_native_executed': False,
                      'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
