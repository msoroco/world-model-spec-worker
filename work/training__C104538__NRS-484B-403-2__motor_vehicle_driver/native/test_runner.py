import unittest
from types import SimpleNamespace

from cameras import camera_plan
from controller import PathController
from engineering import parameters
from runner import check, frame_map_row, map_survey, observed_speed_mps


class RunnerTest(unittest.TestCase):
    def test_all_eight_cpu_preflights(self):
        for case in ('witness_1', 'witness_2'):
            for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
                report = check(case, candidate)
                self.assertTrue(report['native_capture_pending'])
                self.assertFalse(report['selected'])

    def test_camera_fallback_is_distinct(self):
        self.assertNotEqual(camera_plan('primary')[2]['xyz_m'], camera_plan('fallback3')[2]['xyz_m'])
        self.assertEqual(camera_plan('primary')[0], camera_plan('fallback3')[0])

    def test_controller_uses_observed_pose(self):
        p = parameters('witness_2', 'primary')
        controller = PathController(p['native_route_xy_m'], 2.8, 35,
                                    target_speed_mps=p['target_speed_mps'], lookahead_m=p['lookahead_m'])
        row = controller.step(position_xy_m=(-50, 4), yaw_rad=0, speed_mps=0, dt_s=.05)
        self.assertEqual(row['route_error_m'], 0)
        self.assertEqual(row['observed_native_xy_m'], [-50, 4])
        with self.assertRaises(ValueError):
            controller.step(position_xy_m=(-50, 4), yaw_rad=0, speed_mps=0, dt_s=0)

    def test_frame_identity(self):
        self.assertEqual(frame_map_row(2, 42, .1)['carla_frame'], 42)
        with self.assertRaises(ValueError):
            frame_map_row(2, True, .1)

    def test_observed_speed_uses_current_velocity(self):
        class Actor:
            speed = 2.0
            def get_velocity(self):
                return SimpleNamespace(x=self.speed, y=0.0, z=0.0)
        actor = Actor()
        pre_tick = observed_speed_mps(actor)
        actor.speed = 0.25
        self.assertEqual(pre_tick, 2.0)
        self.assertEqual(observed_speed_mps(actor), 0.25)
        actor.speed = float('nan')
        with self.assertRaisesRegex(RuntimeError, 'nonfinite'):
            observed_speed_mps(actor)

    def test_synthetic_map_readback_and_adversarial_direction(self):
        class Location:
            def __init__(self, *, x, y, z):
                self.x, self.y, self.z = x, y, z
        carla = SimpleNamespace(Location=Location, LaneType=SimpleNamespace(Driving=1))
        class Map:
            reverse = False
            def get_waypoint(self, location, **_):
                lane = -1 if location.y > 0 else 1
                sign = -1 if lane == 1 else 1
                if self.reverse:
                    sign *= -1
                transform = SimpleNamespace(location=location,
                    get_forward_vector=lambda: SimpleNamespace(x=sign, y=0))
                return SimpleNamespace(road_id=1, lane_id=lane, lane_width=8, transform=transform)
            def get_all_landmarks(self):
                return [SimpleNamespace(id='4032', type='206', road_id=1, s=72)]
        mapping = Map()
        report = map_survey(carla, mapping)
        self.assertEqual(report['official_sign_status'], 'unreviewed')
        mapping.reverse = True
        with self.assertRaisesRegex(RuntimeError, 'direction'):
            map_survey(carla, mapping)


if __name__ == '__main__':
    unittest.main()
