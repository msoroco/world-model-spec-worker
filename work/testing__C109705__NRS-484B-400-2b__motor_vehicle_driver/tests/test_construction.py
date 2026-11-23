import copy
import hashlib
import importlib.util
import math
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('departure_construction', Path(__file__).resolve().parents[1] / 'construction.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def survey(kind='mapped', reverse=False):
    return {
        'cell_id':'C109705','maneuver':'left_turn','map_name':'unverified_survey_target',
        'source_sha256':'a' * 64,
        'intersecting_roads':[
            {'road_id':1,'alley':False,'public_highway_source':'survey-road-1',
             'permitted_lanes':[{'from_xy_m':[0,-10],'to_xy_m':[0,0]},
                                {'from_xy_m':[2,0],'to_xy_m':[2,-10]}]},
            {'road_id':4,'alley':False,'public_highway_source':'survey-road-4',
             'permitted_lanes':[{'from_xy_m':[-10,0],'to_xy_m':[0,0]},
                                {'from_xy_m':[0,2],'to_xy_m':[-10,2]}]},
        ],
        'approach_road_id':1,'destination_road_id':4,
        'destination_centerline_kind':kind,
        'destination_centerline_xy_m':[[0,0], [0,-10] if reverse else [0,10]],
        'imaginary_line_derivation_source':'survey-edges' if kind == 'source_derived_imaginary' else None,
        'destination_half_width_m':4.2,
        'left_turn_route_waypoint_ids':[10,11,12,13],
        'ego_blueprint_id':'vehicle.test',
        'camera_plan':['dash','front','left','right'],
        'approach_policy':'fixed-route',
    }


class ConstructionTests(unittest.TestCase):
    def test_exact_pair_changes_departure_only(self):
        base = 'testing__C109705__NRS-484B-400-2b__motor_vehicle_driver__'
        s = survey()
        near = module.build(base + 'near_centerline', s)
        far = module.build(base + 'farther_from_centerline', s)
        for key in ('left_turn_route_waypoint_ids','approach_policy','controller_policy','camera_plan','duration_s','rate_hz'):
            self.assertEqual(near[key], far[key])
        self.assertEqual(near['departure_target_xy_m'], [1.7,10.0])
        self.assertEqual(far['departure_target_xy_m'], [2.7,10.0])
        self.assertIsNone(near['legal_lateral_cutoff'])

    def test_reverse_direction_and_imaginary_source(self):
        base = 'testing__C109705__NRS-484B-400-2b__motor_vehicle_driver__'
        result = module.build(base + 'imaginary_near_centerline', survey('source_derived_imaginary', True))
        self.assertEqual(result['departure_target_xy_m'], [-1.7,-10.0])
        s = survey('source_derived_imaginary')
        s['imaginary_line_derivation_source'] = None
        with self.assertRaisesRegex(ValueError, 'source derivation'):
            module.build(base + 'imaginary_near_centerline', s)

    def test_missing_opposition_and_disconnection(self):
        case = 'testing__C109705__NRS-484B-400-2b__motor_vehicle_driver__near_centerline'
        s = survey()
        s['intersecting_roads'][1]['permitted_lanes'][1]['to_xy_m'] = [10,2]
        with self.assertRaisesRegex(ValueError, 'two directional'):
            module.build(case, s)
        s = survey()
        s['destination_road_id'] = 7
        with self.assertRaisesRegex(ValueError, 'disconnected'):
            module.build(case, s)

    def test_controller_is_bounded_and_brakes_at_target(self):
        command = module.control([0,0], 0, [0,10], 4)
        self.assertTrue(-1 <= command['steer'] <= 1)
        self.assertTrue(0 <= command['throttle'] <= 0.35)
        self.assertEqual(module.control([0,0], 0, [0.1,0], 4)['brake'], 1)
        with self.assertRaisesRegex(ValueError, 'nonfinite'):
            module.control([0,0], math.nan, [1,0], 4)

    def test_native_map_hash_is_checked(self):
        case = 'testing__C109705__NRS-484B-400-2b__motor_vehicle_driver__near_centerline'
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / 'road.xodr'
            source.write_text('<OpenDRIVE/>\n')
            s = survey()
            s['source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
            self.assertEqual(module.build(case, s, map_source_path=source)['survey_source_sha256'], s['source_sha256'])
            source.write_text('<OpenDRIVE changed="1"/>\n')
            with self.assertRaisesRegex(ValueError, 'map differs'):
                module.build(case, s, map_source_path=source)


if __name__ == '__main__':
    unittest.main()
