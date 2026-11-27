"""CARLA-free exact capture contract negatives and source adapter integration."""

import ast
import copy
import json
from pathlib import Path

from rail_capture_runner import AID, BEHAVIORS, CAMERAS, TARGETS, check


def config(suffix):
    return {'case_id': AID + ('__selected_98183a3f__' if suffix.startswith('condition_') else '__') + suffix,
            'law_id': 'NRS-484B-450-1i', 'cell_id': 'C229398',
            'actor': 'motor_vehicle_driver', 'rate_hz': 20,
            'duration_frames': 600, 'duration_s': 30,
            'target_footprint_gap_m': TARGETS[suffix],
            'behavior_variant': BEHAVIORS[suffix],
            'approach_distance_m': 10.0, 'approach_speed_cap_mps': 1.5,
            'cameras': [{'name': name, 'width': 1920 if name == 'overview' else 1280,
                         'height': 1080 if name == 'overview' else 720,
                         'fps': 20, 'fov': 90} for name in CAMERAS],
            'physical_verified': False, 'legal_verdict': None}


def rejection(value, expected):
    try:
        check(value)
    except ValueError as error:
        assert expected in str(error), str(error)
        return
    raise AssertionError('Invalid exact Native request accepted')


def main():
    path = Path(__file__).with_name('rail_capture_runner.py')
    ast.parse(path.read_text())
    good_a, good_b = config('condition_a'), config('condition_b')
    assert all(check(config(suffix))['frames'] == 600 for suffix in TARGETS)
    for key, bad, message in [
        ('case_id', AID + '__wrong', 'Unknown exact'),
        ('target_footprint_gap_m', 14.5, 'target changed'),
        ('duration_frames', 599, 'window changed'),
        ('physical_verified', True, 'claims an outcome')]:
        altered = copy.deepcopy(good_a)
        altered[key] = bad
        rejection(altered, message)
    altered = copy.deepcopy(good_a)
    altered['cameras'].pop()
    rejection(altered, 'Four exact')
    altered = copy.deepcopy(good_a)
    altered['behavior_variant'] = 'stop_depart'
    rejection(altered, 'motion variant changed')
    print(json.dumps({'exact_cases': len(TARGETS), 'negative_count': 6,
                      'carla_imported': False, 'native_rail_observed': False,
                      'physical_or_legal_outcome_claimed': False}))


if __name__ == '__main__':
    main()
