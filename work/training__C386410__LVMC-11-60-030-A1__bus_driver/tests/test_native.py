"""CARLA-free construction checks for exact bus location targets."""
import unittest
from geometry import check as check_geometry
from runner import CAMERAS, FRAMES, TARGET_X, check as check_runner


class NativeConstructionTest(unittest.TestCase):
    def test_one_way_zone_and_camera_contract(self):
        geometry = check_geometry()
        self.assertTrue(geometry['zone_x_m'][0] < TARGET_X['designated_terminus'] < geometry['zone_x_m'][1])
        self.assertGreater(TARGET_X['undesignated_street'], geometry['zone_x_m'][1])
        self.assertEqual(FRAMES, 600)
        self.assertEqual([(name, width, height) for name, width, height, *_ in CAMERAS],
            [('overview', 1920, 1080), ('approach', 1280, 720),
             ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)])
        self.assertTrue(check_runner()['passed'])


if __name__ == '__main__':
    unittest.main()
