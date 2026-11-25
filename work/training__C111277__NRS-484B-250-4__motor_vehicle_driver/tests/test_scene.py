import unittest
import xml.etree.ElementTree as ET

from controller import InoperativeSignalController, Observation
from runner import CAMERAS, check
from scene import NEAR_CROSSWALK_X, road_xml


class SceneTests(unittest.TestCase):
    def test_selected_geometry_and_cameras(self):
        result = check()
        self.assertEqual(result['scene']['crosswalk_near_x_m'], NEAR_CROSSWALK_X)
        self.assertEqual(len(CAMERAS), 4)
        root = ET.fromstring(road_xml())
        self.assertEqual(len(root.findall('junction/connection')), 2)
        self.assertEqual(len(root.findall(".//object[@type='crosswalk']")), 1)
        self.assertFalse(root.findall(".//object[@type='stopLine']"))

    def test_controller_approaches_then_stops(self):
        policy = InoperativeSignalController()
        base = dict(signal_installed=True, signal_uncovered=True,
                    signal_inoperative=True, signal_governs_ego_lane=True,
                    stop_line_present=False, near_crosswalk_present=True,
                    prior_stop_vehicle_approaching=True,
                    vehicle_in_intersection=False)
        far = policy.step(Observation(frame=0, ego_front_distance_to_boundary_m=20,
                                      ego_speed_mps=0, **base))
        near = policy.step(Observation(frame=1, ego_front_distance_to_boundary_m=4,
                                       ego_speed_mps=2, **base))
        stopped = policy.step(Observation(frame=2, ego_front_distance_to_boundary_m=3,
                                          ego_speed_mps=0, **base))
        self.assertEqual((far.phase, far.brake, far.throttle), ('approach', 0, .25))
        self.assertEqual((near.phase, near.brake), ('approach', 1))
        self.assertEqual((stopped.phase, stopped.brake), ('hold', 1))


if __name__ == '__main__':
    unittest.main()
