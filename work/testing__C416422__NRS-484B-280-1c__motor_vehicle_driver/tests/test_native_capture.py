import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("native_capture", ROOT / "native_capture.py")
native = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(native)


class Waypoint:
    def __init__(self, x, width=4, sidewalk=True):
        self.road_id, self.lane_id, self.lane_width = 9, -1, width
        self.transform = SimpleNamespace(location=SimpleNamespace(x=x, y=0))
        self.sidewalk = sidewalk

    def get_left_lane(self):
        return SimpleNamespace(lane_type="sidewalk", road_id=9, lane_id=2,
                               lane_width=2, transform=SimpleNamespace(
                                   location=SimpleNamespace(x=self.transform.location.x,
                                                            y=3.5))) if self.sidewalk else None

    def get_right_lane(self):
        return None


class Map:
    def __init__(self, sidewalk=True, missing=False):
        self.sidewalk, self.missing = sidewalk, missing
        self.calls = []

    def get_waypoint(self, location):
        self.calls.append(location.x)
        return None if self.missing else Waypoint(location.x, sidewalk=self.sidewalk)

    def to_opendrive(self):
        return "<OpenDRIVE>reviewed</OpenDRIVE>"


class NativeGeometryTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.scene = json.loads((ROOT / "scene.json").read_text())
        self.carla = SimpleNamespace(Location=lambda **values: SimpleNamespace(**values),
                                     LaneType=SimpleNamespace(Sidewalk="sidewalk"))

    def test_native_route_samples_edges_and_seals_original_map(self):
        mapping = Map()
        site = native.inspect_road(SimpleNamespace(get_map=lambda: mapping),
                                   self.carla, self.scene, self.root)
        start, end = round(self.scene["ego_start_xy_m"][0]), round(self.scene["ego_end_xy_m"][0])
        expected = list(range(start, end + 1, 5))
        if expected[-1] != end:
            expected.append(end)
        self.assertEqual(mapping.calls, expected)
        self.assertEqual(site["road"]["lateral_bounds_m"], [-2, 2])
        self.assertTrue(site["sidewalk_present"])
        self.assertEqual(site["sidewalk"]["lateral_bounds_m"], [2.5, 4.5])
        self.assertEqual(native.sha(self.root / "map.xodr"), site["map_source"]["sha256"])

    def test_native_missing_sidewalk_or_road_rejected(self):
        for mapping, error in ((Map(sidewalk=False), "sidewalk"), (Map(missing=True), "absent")):
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                native.inspect_road(SimpleNamespace(get_map=lambda m=mapping: m),
                                    self.carla, self.scene, self.root)


if __name__ == "__main__":
    unittest.main()
