import json
from pathlib import Path
import unittest

from geometry import check as geometry_check
from route import CASE_LATERAL_M, check_scene
from runner import CAMERAS, check, control, survey, select_subject_blueprint, select_sign_blueprint


class FakeCarla:
    class LaneType:
        Any = 'any'

    class Location:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z


class FakeMap:
    def __init__(self, wrong=False):
        self.wrong = wrong

    def get_waypoint(self, loc, **kwargs):
        transform = type('T', (), {'location': loc})()
        lane = -1 if loc.y == 6 else (-1 if self.wrong else -2)
        return type('WP', (), {'road_id': 1, 'lane_id': lane,
                               'transform': transform})()


class NativeDraft(unittest.TestCase):
    def test_source_specific_native_assets(self):
        class Library:
            def filter(self, pattern):
                assets = {
                    'vehicle.*': ['vehicle.tesla.model3'],
                    'vehicle.*ambulance*': ['vehicle.ford.ambulance'],
                    'vehicle.*truck*': ['vehicle.utility.truck'],
                    'static.prop.*sign*': ['static.prop.streetsign'],
                }
                return [type('BP', (), {'id': item})() for item in assets.get(pattern, [])]
        library = Library()
        self.assertEqual(select_subject_blueprint(library, 'none').id,
                         'vehicle.tesla.model3')
        self.assertEqual(select_subject_blueprint(library, 'emergency_vehicle').id,
                         'vehicle.ford.ambulance')
        self.assertEqual(select_subject_blueprint(library, 'right_of_way_maintenance').id,
                         'vehicle.utility.truck')
        self.assertEqual(select_sign_blueprint(library).id, 'static.prop.streetsign')
        with self.assertRaisesRegex(RuntimeError, 'blueprint unavailable'):
            select_subject_blueprint(library, 'mobility_device')

    def test_geometry_route_and_camera_contract(self):
        config = json.loads(Path('config.json').read_text())
        self.assertEqual(check(config)['frames'], 600)
        self.assertEqual(len(CAMERAS), 4)
        self.assertEqual(geometry_check()['trail_lane_id'], -2)
        self.assertEqual(len(survey(FakeCarla, FakeMap())), 8)
        with self.assertRaisesRegex(RuntimeError, 'lane survey failed'):
            survey(FakeCarla, FakeMap(True))
        scene = {'barrier_x_m': 8.0, 'barrier_clear_gap_m': 3.5,
                 'vehicle_width_m': 2.0, 'trail_lateral_bounds_m': [-2.0, 2.0]}
        self.assertTrue(check_scene(scene)['connected_inside_route_requested'])
        location = FakeCarla.Location(-50, CASE_LATERAL_M[config['route_case']], 2)
        velocity = type('V', (), {'x': 0.0, 'y': 0.0})()
        self.assertGreater(control(config, 0, location, velocity)['throttle'], 0)


if __name__ == '__main__':
    unittest.main()
