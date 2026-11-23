import importlib.util
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("c227824_crossing_map", ROOT / "crossing_map.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CrossingMapTests(unittest.TestCase):
    def test_candidate_bytes_and_crossing_geometry(self):
        receipt = MODULE.verify(ROOT / "candidate-corridor.xodr")
        self.assertFalse(receipt["legal_highway_extent_verified"])
        self.assertFalse(receipt["official_signal_present"])
        self.assertEqual(receipt["roadway_polygon_xy_m"],
                         [[0.0, -3.5], [30.0, -3.5], [30.0, 3.5], [0.0, 3.5]])
        self.assertEqual(receipt["start_xy_m"][0], receipt["target_xy_m"][0])
        self.assertLess(receipt["start_xy_m"][1], -5.5)
        self.assertGreater(receipt["target_xy_m"][1], 5.5)
        root = ET.fromstring(MODULE.map_bytes())
        self.assertEqual(len(root.findall("road")), 1)

    def test_changed_lane_width_rejected(self):
        root = ET.fromstring(MODULE.map_bytes())
        lane = root.find("./road/lanes/laneSection/left/lane/width")
        lane.set("a", "4.0")
        with tempfile.TemporaryDirectory(dir=ROOT.parents[1] / ".runtime-work") as directory:
            path = Path(directory) / "changed.xodr"
            path.write_bytes(ET.tostring(root, encoding="utf-8"))
            with self.assertRaisesRegex(ValueError, "source differs"):
                MODULE.verify(path)


if __name__ == "__main__":
    unittest.main()
