"""CPU checks of source-gated construction and original pass measurement."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rightside import CASES, SOURCE_ROLES, construct, measure_original, validate_scene


class FakeAdapter:
    def __init__(self):
        self.calls = []

    def spawn_cycle(self, point, kind):
        self.calls.append(('cycle', point, kind))
        return 'cycle'

    def spawn_motor_vehicle(self, point):
        self.calls.append(('motor', point))
        return 'motor'

    def spawn_impediment(self, identity, bounds, kind):
        self.calls.append(('impediment', identity, bounds, kind))
        return 'impediment'

    def set_other_route(self, actor, route, motion):
        self.calls.append(('other-route', actor, route, motion))

    def set_cycle_route(self, actor, route, offset, side, turning):
        self.calls.append(('cycle-route', actor, route, offset, side, turning))

    def destroy(self, actor):
        self.calls.append(('destroy', actor))


def scene(case):
    value = {
        'cell_id': 'C229023', 'actor': 'cycle_or_scooter_operator',
        'roadway_occupied': True, 'shoulder_occupied': False,
        'cycle_kind': case.cycle_kind, 'human_operator': True, 'moped': False,
        'other_is_motor_vehicle': True, 'cycle_id': 'ego', 'other_vehicle_id': 'target',
        'right_impediment': case.right_impediment, 'narrow_lane': case.narrow_lane,
        'traffic_speed_context': case.traffic_speed_context,
        'left_turn_preparation': case.left_turn_preparation,
        'target_motion': case.target_motion,
        'roadway_right_y_m': 0., 'lane_width_m': 3.5,
        'cycle_body_half_width_m': .35, 'other_body_half_width_m': .9,
        'passing_side': 'left',
        'cycle_route_xy': [[0., 1.], [60., 1.]],
        'other_route_xy': [[10., 2.], [40., 2.]],
        'requested_lateral_target_m': case.lateral_target_m,
        'right_impediment_id': 'obstruction' if case.right_impediment != 'none' else None,
        'right_impediment_body_bounds_xy': [0., 0., 20., 1.] if case.right_impediment != 'none' else None,
    }
    value.update({role + '_source_sha256': 'a' * 64 for role in SOURCE_ROLES})
    if case.left_turn_preparation:
        value['left_turn_intent_actor_id'] = 'ego'
        value['left_turn_intent_source_sha256'] = 'b' * 64
    return value


def history(value, case):
    rows = []
    for index in range(900):
        other_speed = 0. if case.target_motion == 'standing' else 2.
        row = {
            'original_frame': 200 + index, 'time_s': index / 20,
            'cycle_id': 'ego', 'other_vehicle_id': 'target',
            'cycle_station_m': -10 + index * .04,
            'other_station_m': other_speed * index / 20,
            'cycle_center_y_m': .35 + case.lateral_target_m,
            'cycle_speed_mps': 2.8, 'other_speed_mps': other_speed,
            'surface_clearance_m': .25, 'right_access_width_m': 1.,
            'right_impediment_id': value.get('right_impediment_id'),
            'left_turn_preparation': case.left_turn_preparation,
        }
        if case.target_motion == 'moving':
            row['cycle_station_m'] = -10 + index * .12
        row.update({role + '_source_sha256': value[role + '_source_sha256']
                    for role in SOURCE_ROLES})
        rows.append(row)
    return rows


class RightSideTest(unittest.TestCase):
    def test_all_cases_construct_and_measure(self):
        for case in CASES:
            with self.subTest(case=case.name):
                value = scene(case)
                adapter = FakeAdapter()
                constructed = construct(adapter, value, case)
                self.assertEqual(constructed['case_id'], case.name)
                self.assertIn('cycle-route', [call[0] for call in adapter.calls])
                self.assertEqual('impediment' in [call[0] for call in adapter.calls],
                                 case.right_impediment != 'none')
                measured = measure_original(history(value, case), value, case)
                self.assertEqual(measured['frame_count'], 900)
                self.assertIsNone(measured['legal_due_care'])
                self.assertLess(measured['initial_relative_station_m'], 0)
                self.assertGreater(measured['terminal_relative_station_m'], 0)

    def test_missing_obstruction_geometry_rejected(self):
        case = CASES[2]
        value = scene(case)
        value['right_impediment_body_bounds_xy'] = None
        with self.assertRaisesRegex(ValueError, 'impediment body geometry'):
            validate_scene(value, case)

    def test_missing_source_and_frame_rejected(self):
        case = CASES[0]
        value = scene(case)
        rows = history(value, case)
        rows[100]['lane_width_source_sha256'] = None
        with self.assertRaisesRegex(ValueError, 'original source changed'):
            measure_original(rows, value, case)
        rows = history(value, case)
        rows[100]['original_frame'] += 1
        with self.assertRaisesRegex(ValueError, 'frame/time join'):
            measure_original(rows, value, case)

    def test_nonpassing_trajectory_rejected(self):
        case = CASES[0]
        value = scene(case)
        rows = history(value, case)
        for row in rows:
            row['cycle_station_m'] = row['other_station_m'] - 10
        with self.assertRaisesRegex(ValueError, 'pass not observed'):
            measure_original(rows, value, case)


if __name__ == '__main__':
    unittest.main()
