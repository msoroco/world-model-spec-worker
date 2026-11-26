import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runner import check, main
from build_construction import build
from saved_entry import CAMERAS


class RunnerTests(unittest.TestCase):
    def setUp(self):
        safe = Path(__file__).resolve().parents[3] / ".runtime-work"
        safe.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=safe)
        self.root = Path(self.temp.name)
        map_bytes = b"<OpenDRIVE/>\n"
        (self.root / "candidate-corridor.xodr").write_bytes(map_bytes)
        config, measurement, construction = build()
        for name, value in (("config.json", config),
                            ("measurement-contract.json", measurement),
                            ("construction.json", construction)):
            (self.root / name).write_text(json.dumps(value) + "\n")
        for item in construction["files"]:
            target = self.root / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(item["content"])
        (self.root / "device-review.json").write_text('{"complete": true}\n')
        (self.root / "camera-review.json").write_text('{"complete": true}\n')
        self.scene = {
            "law_id": "NRS-484B-307-8b", "cell_id": "C227824",
            "actor": "pedestrian",
            "case_id": "testing__C227824__NRS-484B-307-8b__pedestrian__red_no_device_entry",
            "map_source_sha256": hashlib.sha256(map_bytes).hexdigest(),
            "fixed_delta_seconds": .05, "planned_frames": 3,
            "entry_request": "entry", "target_xy_m": [2, 0], "speed_mps": 1,
            "walker_spawn_xyz_m": [0, 0, 1],
            "walker_blueprint_id": "walker.pedestrian.0001",
            "highway_polygon_xy_m": [[1, -1], [4, -1], [4, 1], [1, 1]],
            "route_id": "pedestrian-route", "facing_head_id": 7,
            "governing_pedestrian_device_ids": [],
            "requested_pedestrian_indication": "none",
            "device_inventory_review": {
                "complete": True, "source_path": "device-review.json",
                "source_sha256": hashlib.sha256((self.root / "device-review.json").read_bytes()).hexdigest()},
            "camera_placement_review": {
                "complete": True, "source_path": "camera-review.json",
                "source_sha256": hashlib.sha256((self.root / "camera-review.json").read_bytes()).hexdigest()},
            "camera_placements": {name: {"location_xyz_m": [0, 0, 3],
                                          "target_xyz_m": [2, 0, 1]}
                                  for name in CAMERAS},
        }
        self.write_scene()

    def tearDown(self):
        self.temp.cleanup()

    def write_scene(self):
        (self.root / "scene.json").write_text(json.dumps(self.scene) + "\n")

    def test_cpu_precheck_does_not_start_carla(self):
        with patch("runner.run_native") as native:
            with self.assertRaisesRegex(ValueError, 'selected offline diagnostic sources missing'):
                main(["--output-dir", str(self.root), "--check"])
            native.assert_not_called()
        self.assertEqual(check(self.root), self.scene)

    def test_wrong_exact_scene_identity_rejected(self):
        self.scene["actor"] = "motor_vehicle_driver"
        self.write_scene()
        with self.assertRaisesRegex(ValueError, "exact law, cell or actor differs"):
            check(self.root)

    def test_runtime_offline_check_uses_materialized_cwd(self):
        with patch("runner.Path.cwd", return_value=self.root), patch("runner.run_native") as native:
            with self.assertRaisesRegex(ValueError, 'selected offline diagnostic sources missing'):
                main(["--check"])
            native.assert_not_called()

    def test_acquisition_requires_reviewed_original_source(self):
        with patch("runner.run_native", return_value={"native_capture_sealed": True}) as native:
            with self.assertRaisesRegex(ValueError, 'reviewed original pedestrian source directory required'):
                main(["--output-dir", str(self.root), "--host", "localhost", "--port", "2400"])
            native.assert_not_called()

    def test_changed_map_and_incomplete_review_rejected(self):
        (self.root / "candidate-corridor.xodr").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "OpenDRIVE map differs"):
            check(self.root)
        (self.root / "candidate-corridor.xodr").write_text("<OpenDRIVE/>\n")
        self.scene["device_inventory_review"]["complete"] = False
        self.write_scene()
        with self.assertRaisesRegex(ValueError, "governing-device review missing"):
            check(self.root)

    def test_unbound_camera_and_bad_walker_rejected(self):
        self.scene["camera_placements"].pop("overview")
        self.write_scene()
        with self.assertRaisesRegex(ValueError, "four reviewed camera placements"):
            check(self.root)
        self.scene["camera_placements"]["overview"] = {
            "location_xyz_m": [0, 0, 3], "target_xyz_m": [2, 0, 1]}
        self.scene["walker_spawn_xyz_m"] = [0, 0, float("nan")]
        self.write_scene()
        with self.assertRaisesRegex(ValueError, "walker spawn missing or invalid"):
            check(self.root)

    def test_changed_or_escaping_review_source_rejected(self):
        (self.root / "device-review.json").write_text('{"complete": false}\n')
        with self.assertRaisesRegex(ValueError, "review source hash differs"):
            check(self.root)
        self.scene["device_inventory_review"]["source_path"] = "../other.json"
        self.write_scene()
        with self.assertRaisesRegex(ValueError, "review source missing or escapes attempt"):
            check(self.root)

    def test_changed_case_specific_config_rejected(self):
        config = json.loads((self.root / "config.json").read_text())
        config["selected_case_id"] = "other-case"
        (self.root / "config.json").write_text(json.dumps(config) + "\n")
        with self.assertRaisesRegex(ValueError, "case identity differs: config.json"):
            check(self.root)

    def test_changed_materialized_source_rejected(self):
        (self.root / "native_signal.py").write_text("# altered source\n")
        with self.assertRaisesRegex(ValueError, "construction source differs: native_signal.py"):
            check(self.root)


if __name__ == "__main__":
    unittest.main()
