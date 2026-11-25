"""Exercise saved-only analysis through exact original source and pixel joins."""
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
from analysis import report
from native_camera_capture import CAMERAS, capture_with_cameras


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / ".runtime-work/c111610-analysis-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = HERE.name + "__arrow_ped_crosswalk"
        (self.root / "config.json").write_text(json.dumps({
            "assignment_id": HERE.name, "selected_case_id": self.case,
            "cameras": list(CAMERAS)}) + "\n")
        refs = []
        for name in ("map", "signal", "route", "crosswalk"):
            path = self.root / (name + ".json")
            path.write_text(json.dumps({"name": name}) + "\n")
            refs.append({"path": path.name,
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        site = {"case_id": self.case, "cell_id": "C111610",
                "actor": "motor_vehicle_driver", "original_sources": refs,
                "map_source_path": "map.json", "signal_source_path": "signal.json",
                "route_source_path": "route.json", "crosswalk_source_path": "crosswalk.json",
                "native_map_name": "TownTest", "official_head_id": "17",
                "ego_approach_id": "north", "facing_relation": True,
                "arrow_movement": "left", "ego_route_xy": [[0,-8],[0,0],[-8,0]],
                "intersection_polygon_xy": [[-3,-3],[3,-3],[3,3],[-3,3]],
                "adjacent_crosswalk_polygon_xy": [[3,-3],[6,-3],[6,3],[3,3]]}
        (self.root / "site.json").write_text(json.dumps(site) + "\n")
        self.site = site
        stream = io.BytesIO()
        Image.new("RGB", (3, 2), (10, 20, 30)).save(stream, "PNG")
        png = stream.getvalue()
        user = {"id": "p1", "kind": "pedestrian", "xy": [4,0],
                "lawful_presence_source": "reviewed-crossing-log"}
        def step(i):
            lit = i != 1
            aspect = {"frame": 100+i, "elapsed_seconds": i/20,
                      "head_id": "17", "facing_approach_id": "north",
                      "arrow_color": "yellow", "arrow_direction": "left",
                      "arrow_lit": lit, "source_kind": "display_sensor",
                      "source_id": "head-camera-17", "native_head_state": "Yellow",
                      "concurrent_indications": []}
            event = {"frame": 100+i, "official_head_id": "17",
                     "facing_approach_id": "north", "arrow_movement": "left",
                     "lit_aspects": ["flashing_yellow_turn_arrow"] if lit else [],
                     "concurrent_indications": [], "ego_movement": "left",
                     "concurrently_permitted_movement": None,
                     "ego_xy": [[0,-8],[0,0],[-8,0]][i], "other_users": [user]}
            cameras = {name: {"frame": 100+i, "png_bytes": png} for name in CAMERAS}
            return aspect, event, cameras
        self.dims = {name: (3, 2) for name in CAMERAS}
        capture_with_cameras(site, self.root, step, frames=3,
                             diagnostic=True, dimensions=self.dims)

    def test_source_bound_report_and_camera_tamper(self):
        value = report(self.root, diagnostic=True, dimensions=self.dims)
        self.assertEqual(value["case_id"], self.case)
        self.assertEqual(value["measurements"]["camera_decode_observation"]["value"]["decoded_images"], 12)
        self.assertFalse(value["legal_verdict_claimed"])
        source = self.root / "overview.png.zip"
        source.write_bytes(source.read_bytes() + b"tamper")
        with self.assertRaisesRegex(ValueError, "camera source hash"):
            report(self.root, diagnostic=True, dimensions=self.dims)

    def test_delivery_rejects_diagnostic_sources(self):
        with self.assertRaisesRegex(ValueError, "original reviewed Native arrow site"):
            report(self.root)


if __name__ == "__main__":
    unittest.main()
