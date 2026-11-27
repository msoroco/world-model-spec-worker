"""Focused CPU proof of exact branch requests and original-survey rejection."""

import json
import os
from pathlib import Path
import tempfile

from controller import Observation, SUFFIXES, request
from survey import ASSIGNMENT, load


def prove():
    base = Observation(120, True, True, True, True, 0.0)
    assert len(SUFFIXES) == 8
    assert request('direction_indicated', base).route == 'indicated_turn'
    assert request('direction_contrary', base).route == 'contrary_turn'
    assert request('arrow_lit', base).target_speed_mps > 0
    assert request('arrow_expired', base).phase == 'wait_for_observed_arrow_end'
    assert request('pedestrian_yield', base).phase == 'pause_for_observed_pedestrian'
    assert request('traffic_yield', base).phase == 'pause_for_observed_traffic'
    assert request('pedestrian_overlap', base).phase == 'attempt_moving_overlap'
    assert request('traffic_overlap', base).phase == 'attempt_moving_overlap'
    gone = Observation(130, True, False, False, False, 0.0)
    assert request('arrow_expired', gone).phase == 'after_observed_arrow_end'
    assert request('arrow_lit', gone).target_speed_mps == 0
    assert request('pedestrian_yield', gone).target_speed_mps > 0
    assert request('traffic_yield', gone).target_speed_mps > 0
    with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as tmp:
        path = Path(tmp) / 'survey.json'
        case = ASSIGNMENT + '__direction_indicated'
        survey = {
            'case_id': case, 'source_kind': 'original_native_context_survey',
            'map_name': 'source_map', 'ego_spawn_xyz_yaw': [0, 0, 1, 0],
            'pedestrian_spawn_xyz_yaw': [2, 1, 1, 0],
            'other_traffic_spawn_xyz_yaw': [3, 2, 1, 90],
            'indicated_turn_waypoints_xy': [[0, 0], [1, 0], [2, 1]],
            'contrary_turn_waypoints_xy': [[0, 0], [1, 0], [2, -1]],
            'arrow_opendrive_id': 'source-id-123', 'arrow_direction': 'left',
            'arrow_facing_source': 'original_camera_and_native_head',
            'arrow_only_pixels_source': 'original_camera_pixels_pending_review',
            'intersection_bounds_m': [0, 5, -2, 2],
            'adjacent_crosswalk_bounds_m': [1, 3, 1, 2],
            'pedestrian_permission_source': 'original_device_review_pending',
            'other_traffic_permission_source': 'original_device_review_pending',
            'camera_poses': {'overview': {'xyz_m': [0, 0, 9], 'pitch_yaw_roll_deg': [-45, 0, 0]},
                             'reference_corner': {'xyz_m': [2, 2, 5], 'pitch_yaw_roll_deg': [-30, 0, 0]}},
        }
        path.write_text(json.dumps(survey) + '\n')
        assert load(path, case)['arrow_opendrive_id'] == 'source-id-123'
        missing = dict(survey)
        missing.pop('arrow_facing_source')
        path.write_text(json.dumps(missing) + '\n')
        try:
            load(path, case)
        except ValueError as exc:
            assert 'survey identity or source incomplete' in str(exc)
        else:
            raise AssertionError('Missing governing-head source accepted')
        path.unlink()
        try:
            load(path, case)
        except ValueError as exc:
            assert 'survey required' in str(exc)
        else:
            raise AssertionError('Missing original survey accepted')
    return {'exact_cases': len(SUFFIXES), 'controller_branches_checked': 8,
            'missing_original_source_negatives': 2,
            'native_executed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
