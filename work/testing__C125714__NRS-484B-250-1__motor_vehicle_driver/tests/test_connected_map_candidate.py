"""CPU topology and geometry checks for the engineering median candidate."""
import math
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from connected_map_candidate import ROUTES, inspect


ROOT = Path(__file__).resolve().parents[1]


def lane_endpoints(road):
    geometry = road.find("./planView/geometry")
    x, y, heading, length = (float(geometry.get(key)) for key in
                             ("x", "y", "hdg", "length"))
    offset = (1.75 * math.sin(heading), -1.75 * math.cos(heading))
    start = (x+offset[0], y+offset[1])
    arc = geometry.find("arc")
    if arc is None:
        end = (start[0]+length*math.cos(heading),
               start[1]+length*math.sin(heading))
    else:
        curvature = float(arc.get("curvature"))
        end_heading = heading + length*curvature
        reference_end = (x + (math.sin(end_heading)-math.sin(heading))/curvature,
                         y + (math.cos(heading)-math.cos(end_heading))/curvature)
        end = (reference_end[0]+1.75*math.sin(end_heading),
               reference_end[1]-1.75*math.cos(end_heading))
    return start, end


class ConnectedMapCandidateTests(unittest.TestCase):
    def test_four_forward_lane_paths_are_geometrically_continuous(self):
        path = ROOT / "connected-median-candidate.xodr"
        proof = inspect(path)
        self.assertEqual(proof["junction_connection_count"], 4)
        roads = {int(road.get("id")): road for road in ET.parse(path).getroot().findall("road")}
        for route in ROUTES.values():
            for first, second in zip(route, route[1:]):
                end = lane_endpoints(roads[first])[1]
                start = lane_endpoints(roads[second])[0]
                self.assertLess(math.dist(end, start), 1e-9)
        ego_y = lane_endpoints(roads[10])[0][1]
        opposite_y = lane_endpoints(roads[20])[0][1]
        self.assertGreater(opposite_y-ego_y, 10)
        self.assertEqual(round(lane_endpoints(roads[31])[0][0], 6), 0)
        self.assertAlmostEqual(lane_endpoints(roads[140])[1][0], -1.75)
        self.assertAlmostEqual(lane_endpoints(roads[140])[1][1], 0)

    def test_left_arc_and_connection_are_required(self):
        root = ET.parse(ROOT / "connected-median-candidate.xodr").getroot()
        root.find("./road[@id='140']/planView/geometry").remove(
            root.find("./road[@id='140']/planView/geometry/arc"))
        with TemporaryDirectory() as folder:
            path = Path(folder) / "broken.xodr"
            path.write_bytes(ET.tostring(root))
            with self.assertRaisesRegex(ValueError, "left junction arc"):
                inspect(path)

    def test_missing_other_junction_connection_rejected(self):
        root = ET.parse(ROOT / "connected-median-candidate.xodr").getroot()
        junction = root.find("junction")
        target = next(c for c in junction.findall("connection") if c.get("incomingRoad") == "31")
        junction.remove(target)
        with TemporaryDirectory() as folder:
            path = Path(folder) / "broken.xodr"
            path.write_bytes(ET.tostring(root))
            with self.assertRaisesRegex(ValueError, "other has no junction connection"):
                inspect(path)

    def test_missing_lane_link_rejected(self):
        root = ET.parse(ROOT / "connected-median-candidate.xodr").getroot()
        connection = root.find("./junction/connection[@incomingRoad='10']")
        connection.remove(connection.find("laneLink"))
        with TemporaryDirectory() as folder:
            path = Path(folder) / "broken.xodr"
            path.write_bytes(ET.tostring(root))
            with self.assertRaisesRegex(ValueError, "ego lane connection differs"):
                inspect(path)


if __name__ == "__main__":
    unittest.main()
