import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from route_control import RouteControl


class RouteControlTest(unittest.TestCase):
    def test_advances_to_crossing_and_brakes_at_end(self):
        control = RouteControl([[-5, 0], [0, 0], [5, 0]])
        first = control.decide(-5, 0, 0, 0)
        self.assertEqual(first['target_index'], 1)
        self.assertGreater(first['throttle'], 0)
        middle = control.decide(0, 0, 0, 2)
        self.assertEqual(middle['target_index'], 2)
        last = control.decide(5, 0, 0, 0)
        self.assertTrue(last['requested_route_complete'])
        self.assertEqual(last['brake'], 1)

    def test_rejects_missing_route(self):
        with self.assertRaisesRegex(ValueError, 'positive route'):
            RouteControl([[0, 0]])

    def test_speed_and_steering_fallbacks_change_requested_control(self):
        route=[[0,0],[10,2.1]]
        primary=RouteControl(route)
        slower=RouteControl(route,speed_mps=3.0)
        tighter=RouteControl(route,reach_m=1.0,steer_divisor_deg=32.0)
        requested=primary.decide(0,0,0,3.6)
        self.assertEqual(requested['brake'],0.0)
        self.assertGreater(slower.decide(0,0,0,3.6)['brake'],0.0)
        self.assertGreater(tighter.decide(0,0,0,3.6)['steer'],requested['steer'])


if __name__ == '__main__':
    unittest.main()
