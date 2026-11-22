import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from opendrive_route_preflight import preflight


class RoutePreflightTests(unittest.TestCase):
    def setUp(self):
        self.map = ROOT / "connected-median-candidate.xodr"
        self.scene = ROOT / "cases" / "opposite_makes_left" / "scene.json"

    def test_all_seven_routes_have_forward_lane_paths(self):
        scenes = [ROOT / "scene.json", *sorted((ROOT / "cases").glob("*/scene.json"))]
        result = preflight(self.map, scenes)
        self.assertEqual(len(result["cases"]), 7)
        for parties in result["cases"].values():
            for party in ("ego", "other"):
                self.assertLessEqual(parties[party]["maximum_anchor_error_m"], 0.9)

    def test_source_hash_and_off_lane_anchor_rejected(self):
        scene = json.loads(self.scene.read_text())
        with TemporaryDirectory() as directory:
            path = Path(directory) / "scene.json"
            scene["crossing"]["map_source_sha256"] = "0" * 64
            path.write_text(json.dumps(scene))
            with self.assertRaisesRegex(ValueError, "SHA mismatch"):
                preflight(self.map, [path])
            scene["crossing"]["map_source_sha256"] = preflight(self.map, [self.scene])["map_sha256"]
            scene["other_route_xy_m"][3] = [28, 18]
            path.write_text(json.dumps(scene))
            with self.assertRaisesRegex(ValueError, "off a driving lane"):
                preflight(self.map, [path])

    def test_backtracking_anchor_rejected(self):
        scene = json.loads((ROOT / "scene.json").read_text())
        scene["ego_route_xy_m"][1] = [-20, -5.75]
        scene["ego_route_xy_m"][2] = [-25, -5.75]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "scene.json"
            path.write_text(json.dumps(scene))
            with self.assertRaisesRegex(ValueError, "forward road/lane"):
                preflight(self.map, [path])


if __name__ == "__main__":
    unittest.main()
