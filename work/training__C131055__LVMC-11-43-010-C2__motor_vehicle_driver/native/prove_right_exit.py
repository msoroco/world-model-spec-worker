"""CPU proof for the authored right-exit Native request, not physical motion."""
import copy
import importlib.util
import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from geometry import check as geometry_check, open_drive
from roundabout_scene import LANES, request, validate
from runner import ASSIGNMENT, CAMERAS, check as runner_check, target


def rejected(call, fragment):
    try:
        call()
    except ValueError as exc:
        assert fragment in str(exc), str(exc)
        return
    raise AssertionError('Expected rejection: ' + fragment)


def main():
    geo = geometry_check()
    assert geo['right_exit_road'] == 8 and geo['ring_quarters'] == 4
    roads = ET.fromstring(open_drive()).findall('road')
    assert roads[7].get('name') == 'east-right-turn-exit'
    cases = {}
    for lane, radius in LANES.items():
        scene = request(lane)
        assert validate(scene)['intent'] == 'right_turn'
        assert scene['entry_arm'] == 'south' and scene['exit_arm'] == 'east'
        assert scene['controller']['exit_heading_deg'] == 0
        assert len(scene['controller']['circulatory_waypoints']) == 49
        assert abs(target(lane, 4)[0][1] + radius) < 1e-8
        assert abs(target(lane, 9.999)[0][0] - radius) < 1e-2
        assert target(lane, 10)[0] == (radius, 0)
        assert target(lane, 12)[0] == (radius + 10.4, 0)
        config = {
            'assignment_id': ASSIGNMENT, 'law_id': 'LVMC-11-43-010-C2',
            'cell_id': 'C131055', 'actor': 'motor_vehicle_driver',
            'selected_case_id': ASSIGNMENT + '__' + lane,
            'case': {'case_id': ASSIGNMENT + '__' + lane},
            'rate_hz': 20, 'duration_s': 30, 'frames': 600,
            'cameras': [{'name': camera[0]} for camera in CAMERAS],
            'physical_acceptance_claimed': False, 'legal_verdict': None,
        }
        assert runner_check(config)['native_executed'] is False
        changed = copy.deepcopy(config)
        changed['cameras'].pop()
        rejected(lambda: runner_check(changed), 'Four source cameras')
        changed = copy.deepcopy(config)
        changed['frames'] = 599
        rejected(lambda: runner_check(changed), '30-second')
        changed = copy.deepcopy(config)
        changed['law_id'] = 'LVMC-11-43-010-C1'
        rejected(lambda: runner_check(changed), 'Frozen identity')
        changed = copy.deepcopy(config)
        changed['legal_verdict'] = 'compliant'
        rejected(lambda: runner_check(changed), 'Premature physical or legal claim')
        changed_scene = copy.deepcopy(scene)
        changed_scene['controller']['exit_heading_deg'] = 180
        rejected(lambda: validate(changed_scene), 'Right-turn first-exit arc')
        cases[lane] = {'radius_m': radius, 'right_exit_road_id': 8,
                       'camera_count': len(CAMERAS), 'frames': 600}
    rejected(lambda: request('u_turn_left_lane'), 'Unknown lane policy')
    print(json.dumps({'assignment_id': ASSIGNMENT, 'synthetic_only': True,
                      'cases': cases, 'rejections': 6, 'original_native_executed': False},
                     sort_keys=True))


if __name__ == '__main__':
    main()
