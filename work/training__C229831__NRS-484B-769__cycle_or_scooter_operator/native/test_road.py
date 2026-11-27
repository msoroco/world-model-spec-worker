import math
import unittest
import xml.etree.ElementTree as ET

from road import lane_center_route, open_drive


class TestRoad(unittest.TestCase):
    def test_opendrive_junction_and_lane_links(self):
        root = ET.fromstring(open_drive())
        roads = {road.attrib["id"]: road for road in root.findall("road")}
        self.assertEqual(set(roads), {"1", "2", "13"})
        self.assertEqual(root.find("junction/connection").attrib["incomingRoad"], "1")
        self.assertEqual(root.find("junction/connection").attrib["connectingRoad"], "13")
        self.assertEqual(root.find("junction/connection/laneLink").attrib,
                         {"from": "-1", "to": "-1"})
        self.assertEqual(roads["13"].find("link/successor").attrib["elementId"], "2")
        self.assertAlmostEqual(float(roads["13"].find("planView/geometry/arc").attrib["curvature"]), -1 / 7)

    def test_continuous_right_turn_path_on_roadway_lane(self):
        points = lane_center_route()
        self.assertEqual(points[0], [-45, -1.75])
        self.assertAlmostEqual(points[-1][0], -1.75)
        self.assertAlmostEqual(points[-1][1], -32.0)
        self.assertLess(max(math.dist(a, b) for a, b in zip(points, points[1:])), 0.26)
        self.assertTrue(all(-3.5 < point[1] < 0 for point in points[:153]))
        self.assertTrue(all(-3.5 < point[0] < 0 for point in points[-100:]))


if __name__ == "__main__":
    unittest.main()
