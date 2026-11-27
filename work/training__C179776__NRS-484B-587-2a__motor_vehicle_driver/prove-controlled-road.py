"""Offline original-road design checks; no CARLA or legal designation claim."""

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('controlled_access_road', ROOT / 'native' / 'controlled_access_road.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def rejects(action, expected):
    try:
        action()
    except ValueError as error:
        assert expected in str(error), str(error)
        return str(error)
    raise AssertionError('Invalid road or target accepted')


positive = {name: module.inspect(name) for name in ('marked_lane', 'paved_shoulder')}
assert positive['marked_lane']['outside_target_frames'] == 0
assert positive['paved_shoulder']['fully_shoulder_target_frames'] >= 250
assert all(not value['physical_motion_verified'] and not value['controlled_access_designation_verified'] for value in positive.values())
assert all(module.planned_xy('marked_lane', i / 20)[0] == module.planned_xy('paved_shoulder', i / 20)[0] for i in range(600))
assert module.planned_xy('marked_lane', 0)[0] > module.planned_xy('marked_lane', 29.95)[0]
source = module.open_drive()
negative = {
    'unknown_case': rejects(lambda: module.inspect('other'), 'Unknown exact lane target'),
    'wrong_shoulder_type': rejects(lambda: module.inspect('paved_shoulder', source.replace('id="2" type="shoulder"', 'id="2" type="driving"')), 'Road lane types differ'),
    'wrong_shoulder_width': rejects(lambda: module.inspect('paved_shoulder', source.replace('id="2" type="shoulder" level="false"><width sOffset="0" a="2"', 'id="2" type="shoulder" level="false"><width sOffset="0" a="1"')), 'Road lane widths differ'),
    'short_road': rejects(lambda: module.inspect('marked_lane', source.replace('length="180" id="1"', 'length="80" id="1"')), 'Authored road extent differs'),
    'short_episode': rejects(lambda: module.planned_xy('marked_lane', 30), 'Outside recorded episode'),
}
print(json.dumps({'passed': True, 'positive': positive, 'negative': negative,
                  'comparison_fixed': ['road XML', 'longitudinal route', 'vehicle body', 'rate', 'duration'],
                  'deliberate_difference': 'requested lateral path only'}, sort_keys=True))
