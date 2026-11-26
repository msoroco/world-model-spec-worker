import json
from pathlib import Path
import unittest

import geometry
import runner


class FakePoint:
    def __init__(self, x, y):
        self.x, self.y = x, y


class FakePose:
    def __init__(self):
        self.location = FakePoint(0, 0)
        self.rotation = type('Rotation', (), {'yaw': 0})()


class FakeActor:
    def __init__(self):
        self.pose = FakePose()
        self.control = None

    def get_transform(self):
        return self.pose

    def get_velocity(self):
        return type('Velocity', (), {'length': lambda self: 4})()

    def apply_control(self, control):
        self.control = control


class FakeCarla:
    class VehicleControl:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)


class NativeRouteTests(unittest.TestCase):
    def test_distinct_connected_and_unavailable_maps(self):
        possible = geometry.check(True)
        unavailable = geometry.check(False)
        self.assertEqual(possible['junction_links'], [(1, 2), (1, 3)])
        self.assertEqual(unavailable['junction_links'], [(1, 2)])
        self.assertEqual(possible['same_destination_road_id'],
                         unavailable['same_destination_road_id'])
        self.assertFalse(possible['controlled_access_legally_verified'])

    def test_four_original_cameras_and_duration(self):
        self.assertTrue(runner.check(True)['passed'])
        self.assertTrue(runner.check(False)['passed'])
        self.assertEqual(runner.FRAMES, 900)
        self.assertEqual(len(runner.CAMERAS), 4)

    def test_pure_pursuit_commands_target_route(self):
        actor = FakeActor()
        straight = runner._follow(actor, [FakePoint(x, 0) for x in range(12)], 6, FakeCarla)
        self.assertGreater(actor.control.throttle, 0)
        self.assertEqual(straight['target_xy_m'][1], 0)
        curve = runner._follow(actor, [FakePoint(x, -x) for x in range(12)], 6, FakeCarla)
        self.assertLess(actor.control.steer, 0)
        self.assertLess(curve['target_xy_m'][1], 0)

    def test_materialized_case_identifies_construction(self):
        config = json.loads(Path('config.json').read_text())
        self.assertEqual(config['law_id'], 'NRS-484B-627-1c')
        self.assertEqual(config['duration_s'], 45)
        self.assertEqual(config['rate_hz'], 20)
        self.assertEqual(config['selected_case_id'], config['case_id'])
        self.assertEqual(config['take_alternate'] and config['alternate_possible'],
                         config['take_alternate'])


if __name__ == '__main__':
    unittest.main()
