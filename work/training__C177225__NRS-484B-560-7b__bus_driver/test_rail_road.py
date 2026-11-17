import unittest
import xml.etree.ElementTree as ET

from rail_road import LANE_WIDTH_M, open_drive, validate_authored_road


class RailRoadTest(unittest.TestCase):
    def test_two_driving_directions_and_full_bus_approaches(self):
        result = validate_authored_road()
        self.assertEqual([-1, 1], result['driving_lane_ids'])
        self.assertEqual([-70, 70], result['bus_start_stations_m'])
        self.assertIn('Native readback pending', result['scope'])
        root = ET.fromstring(open_drive())
        lanes = root.findall('road/lanes/laneSection/*/lane')
        widths = [float(lane.find('width').attrib['a'])
                  for lane in lanes if lane.attrib['type'] == 'driving']
        self.assertEqual([LANE_WIDTH_M, LANE_WIDTH_M], widths)


if __name__ == '__main__':
    unittest.main()
