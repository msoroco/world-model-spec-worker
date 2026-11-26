"""Exercise the connected right turn and controller on CPU requests."""
import math
import unittest
import xml.etree.ElementTree as ET

from controller import EngineeringKnobs, PathController
from capture import check as capture_check
from geometry import APPROACH_M, check, open_drive, route
from measure_observed import CASE_PREFIX


class BusinessRightTurnGeometry(unittest.TestCase):
    def test_exact_capture_request(self):
        config = {'case_id': CASE_PREFIX + 'a', 'law_id': 'NRS-484B-413-2',
                  'cell_id': 'C42417', 'actor': 'motor_vehicle_driver',
                  'rate_hz': 20, 'duration_s': 30,
                  'layout': 'business_district', 'maneuver': 'right_turn',
                  'precipitation': 'rain', 'signal_distance_m': 40,
                  'controller_lookahead_base_m': 4.0}
        self.assertEqual(capture_check(config)['signal_start_x_m'], -40)
        config['case_id'] = CASE_PREFIX + 'b'
        config['signal_distance_m'] = 20
        self.assertEqual(capture_check(config)['signal_start_x_m'], -20)
        config['layout'] = 'other_area'
        with self.assertRaisesRegex(ValueError, 'business district'):
            capture_check(config)

    def test_connected_right_turn(self):
        result = check()
        self.assertGreater(result['authored_route_points'], 1500)
        document = ET.fromstring(open_drive())
        self.assertEqual(document.findall('road')[0].find('link/successor').get('elementId'), '2')
        self.assertLess(float(document.findall('road')[1].find('planView/geometry/arc').get('curvature')), 0)

    def test_signal_stations_fit_before_turn(self):
        points = route()
        turn_index = round(APPROACH_M / .1)
        self.assertEqual(points[turn_index], [0.0, -1.75])
        self.assertEqual(points[turn_index - 400], [-40.0, -1.75])
        self.assertEqual(points[turn_index - 200], [-20.0, -1.75])
        self.assertLess(points[-1][1], -17.9)

    def test_controller_follows_observed_pose(self):
        knobs = EngineeringKnobs(target_speed_mps=5.0)
        controller = PathController([[x, -y] for x, y in route()], 2.7, 30.0, knobs)
        straight = None
        for x in range(-130, -39):
            straight = controller.step(position_xy_m=(float(x), 1.75),
                                       yaw_rad=0.0, speed_mps=5.0, dt_s=.05)
        self.assertLess(abs(straight['steer']), .05)
        self.assertLess(straight['route_error_m'], .11)
        for x in range(-39, 1):
            controller.step(position_xy_m=(float(x), 1.75),
                            yaw_rad=0.0, speed_mps=5.0, dt_s=.05)
        entry = controller.step(position_xy_m=(0.0, 1.75),
                                yaw_rad=0.0, speed_mps=5.0, dt_s=.05)
        self.assertGreater(entry['steer'], 0)
        self.assertTrue(math.isfinite(entry['route_error_m']))


if __name__ == '__main__':
    unittest.main()
