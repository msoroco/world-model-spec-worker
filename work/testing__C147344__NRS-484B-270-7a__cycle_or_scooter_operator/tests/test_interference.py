"""CPU geometry, source and original-measurement checks for C147344."""

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from interference import CASES, construct, measure_original, validate_scene


def scene_for(case):
    bicycle_id = 'ebike-1'
    motor_id = 'car-1'
    scene = {
        'cell_id': 'C147344', 'actor': 'cycle_or_scooter_operator',
        'law_id': 'NRS-484B-270-7a',
        'road_layout': 'one_way_multilane', 'maneuver': 'travel',
        'bicycle_id': bicycle_id,
        'electric_bicycle': {
            'class': 1, 'fully_operable_pedals': True, 'saddle': True,
            'moped': False, 'electric_scooter': False, 'motor_watts': 500,
            'assistance_only_while_pedaling': True,
            'assistance_ceases_at_mph': 20, 'wheel_diameter_m': .65},
        'motor_vehicle': {'statutory_motor_vehicle': True,
                          'vehicle_id': motor_id},
        'bicycle_path': case.bicycle_path,
        'motor_response': case.motor_response,
        'routes': {'bicycle': [[0, -3.5], [100, -3.5], [200, 0]],
                   'motor_vehicle': [[20, 0], [220, 0]]},
        'lane_assignments': {'bicycle_initial': 'right',
                             'motor_initial': 'middle'},
        'intention_declaration': None if case.authored_target is None else {
            'actor_id': bicycle_id, 'target_id': motor_id,
            'value': case.authored_target,
            'source_sha256': 'a' * 64,
            'start_frame': 0, 'end_frame': 599}}
    for source in ('reviewed_road', 'electric_bicycle_classification',
                   'motor_vehicle_classification', 'route_geometry',
                   'operator_control', 'authored_plan'):
        scene[source + '_source_sha256'] = 'a' * 64
    return scene


def rows_for(scene, case):
    rows = []
    for i in range(600):
        row = {'original_frame': 1000 + i, 'time_s': i / 20,
               'bicycle_id': scene['bicycle_id'],
               'motor_vehicle_id': scene['motor_vehicle']['vehicle_id'],
               'bicycle_speed_mps': 5.0, 'motor_speed_mps': 7.0,
               'body_gap_m': 4.0,
               'motor_brake': .4 if case.motor_response == 'brake' and
                                  300 <= i <= 340 else 0.0,
               'bicycle_lane': 'middle' if case.bicycle_path == 'merge'
                               and i >= 300 else 'right',
               'motor_lane': 'middle'}
        for source in ('bicycle_motion', 'motor_motion', 'body_geometry',
                       'lane_geometry', 'motor_control', 'camera_frames'):
            row[source + '_sha256'] = 'b' * 64
        rows.append(row)
    return rows


class Adapter:
    def __init__(self):
        self.calls = []

    def spawn_electric_bicycle(self, point, classification):
        self.calls.append(('bicycle', point, classification['class']))
        return 'ebike'

    def spawn_motor_vehicle(self, point, classification):
        self.calls.append(('motor', point, classification['vehicle_id']))
        return 'motor'

    def set_motor_route(self, actor, route, response):
        self.calls.append(('motor_route', actor, response))

    def set_bicycle_route(self, actor, route, path):
        self.calls.append(('bicycle_route', actor, path))

    def destroy(self, actor):
        self.calls.append(('destroy', actor))


class InterferenceTest(unittest.TestCase):
    def test_every_case_constructs_two_actors_and_correct_paths(self):
        for case in CASES:
            with self.subTest(case=case.suffix):
                scene = scene_for(case)
                adapter = Adapter()
                built = construct(adapter, scene, case)
                self.assertEqual(built['owned'], ('ebike', 'motor'))
                self.assertIn(('bicycle_route', 'ebike', case.bicycle_path),
                              adapter.calls)
                self.assertIn(('motor_route', 'motor', case.motor_response),
                              adapter.calls)

    def test_qualifying_electric_bicycle_is_source_gated(self):
        scene = scene_for(CASES[0])
        scene['electric_bicycle']['motor_watts'] = 751
        with self.assertRaisesRegex(ValueError, 'qualifying Class 1'):
            validate_scene(scene, CASES[0])

    def test_intention_binding_is_source_gated(self):
        scene = scene_for(CASES[0])
        scene['intention_declaration']['target_id'] = 'wrong-car'
        with self.assertRaisesRegex(ValueError, 'authored intent'):
            validate_scene(scene, CASES[0])

    def test_unplanned_case_rejects_authored_intent(self):
        scene = scene_for(CASES[2])
        scene['intention_declaration'] = copy.deepcopy(
            scene_for(CASES[0])['intention_declaration'])
        with self.assertRaisesRegex(ValueError, 'unplanned control'):
            validate_scene(scene, CASES[2])

    def test_original_measurement_all_cases(self):
        for case in CASES:
            with self.subTest(case=case.suffix):
                scene = scene_for(case)
                result = measure_original(rows_for(scene, case), scene, case)
                self.assertEqual(result['frame_count'], 600)
                self.assertIsNone(result['legal_judgment'])
                self.assertFalse(result['intent_inferred_from_motion'])

    def test_missing_original_packet_rejected(self):
        case = CASES[0]
        scene = scene_for(case)
        rows = rows_for(scene, case)
        rows[230].pop('motor_motion_sha256')
        with self.assertRaisesRegex(ValueError, 'motor_motion'):
            measure_original(rows, scene, case)

    def test_motion_and_intent_are_not_conflated(self):
        planned, ordinary = CASES[0], CASES[2]
        scene_a, scene_b = scene_for(planned), scene_for(ordinary)
        a = measure_original(rows_for(scene_a, planned), scene_a, planned)
        b = measure_original(rows_for(scene_b, ordinary), scene_b, ordinary)
        self.assertEqual(a['maximum_motor_brake'], b['maximum_motor_brake'])
        self.assertIsNotNone(a['declared_intention'])
        self.assertIsNone(b['declared_intention'])


if __name__ == '__main__':
    unittest.main()
