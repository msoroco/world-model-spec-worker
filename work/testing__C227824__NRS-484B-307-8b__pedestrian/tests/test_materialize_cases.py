import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from materialize_cases import materialize
from saved_entry import CAMERAS


class MaterializeTests(unittest.TestCase):
    def setUp(self):
        private = ROOT.parents[1] / ".runtime-work"
        private.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=private)
        self.source = Path(self.temp.name)
        self.output = self.source.parent / (self.source.name + "-six")
        map_bytes = b"<OpenDRIVE/>\n"
        (self.source / "candidate-corridor.xodr").write_bytes(map_bytes)
        device = self.source / "device-review.json"
        camera = self.source / "camera-review.json"
        device.write_text('{"complete": true}\n')
        camera.write_text('{"complete": true}\n')
        self.base = {
            "map_source_sha256": hashlib.sha256(map_bytes).hexdigest(),
            "fixed_delta_seconds": .05, "planned_frames": 240,
            "target_xy_m": [2, 0], "speed_mps": 1,
            "walker_spawn_xyz_m": [0, 0, 1],
            "walker_blueprint_id": "walker.pedestrian.0001",
            "highway_polygon_xy_m": [[1, -1], [4, -1], [4, 1], [1, 1]],
            "route_id": "pedestrian-route", "facing_head_id": 7,
            "governing_pedestrian_device_ids": [],
            "device_inventory_review": {
                "complete": True, "source_path": device.name,
                "source_sha256": hashlib.sha256(device.read_bytes()).hexdigest()},
            "camera_placement_review": {
                "complete": True, "source_path": camera.name,
                "source_sha256": hashlib.sha256(camera.read_bytes()).hexdigest()},
            "camera_placements": {name: {"location_xyz_m": [0, 0, 3],
                                         "target_xyz_m": [2, 0, 1]}
                                  for name in CAMERAS},
        }
        (self.source / "no-device-base.json").write_text(json.dumps(self.base) + "\n")
        one = json.loads(json.dumps(self.base))
        one["governing_pedestrian_device_ids"] = [8]
        review = self.source / "one-device-review.json"
        review.write_text('{"complete": true, "reviewed_device_id": 8}\n')
        one["device_inventory_review"] = {
            "complete": True, "source_path": review.name,
            "source_sha256": hashlib.sha256(review.read_bytes()).hexdigest()}
        (self.source / "one-device-base.json").write_text(json.dumps(one) + "\n")

    def tearDown(self):
        if self.output.exists():
            import shutil
            shutil.rmtree(self.output)
        self.temp.cleanup()

    def test_six_private_prechecked_attempts(self):
        ids = materialize(self.source, self.output)
        self.assertEqual(len(ids), 6)
        for case_id in ids:
            self.assertTrue((self.output / case_id / "scene.json").is_file())
            self.assertTrue((self.output / case_id / "runner.py").is_file())
            self.assertTrue((self.output / case_id / "native_world.py").is_file())
            config = json.loads((self.output / case_id / "config.json").read_text())
            construction = json.loads((self.output / case_id / "construction.json").read_text())
            self.assertEqual(config["selected_case_id"], case_id)
            self.assertEqual(construction["case_id"], case_id)
        selected = self.output / ids[0]
        completed = subprocess.run(
            [sys.executable, str(selected / "runner.py"), "--check",
             "--output-dir", str(selected)], capture_output=True, text=True,
            check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn('"cpu_precheck": "passed"', completed.stdout)
        tests = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            cwd=selected, capture_output=True, text=True, check=False)
        self.assertEqual(tests.returncode, 0, tests.stderr)
        self.assertIn("Ran 1 test", tests.stderr)

    def test_changed_review_rejected_without_output(self):
        (self.source / "one-device-review.json").write_text('{"complete": false}\n')
        with self.assertRaisesRegex(ValueError, "review source hash differs"):
            materialize(self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_short_duration_rejected_without_output(self):
        for name in ("no-device-base.json", "one-device-base.json"):
            path = self.source / name
            base = json.loads(path.read_text())
            base["planned_frames"] = 3
            path.write_text(json.dumps(base) + "\n")
        with self.assertRaisesRegex(ValueError, "12-second 20 Hz"):
            materialize(self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_production_review_assets_copied_and_verified(self):
        map_bytes = (b'<OpenDRIVE><road><signals><signal id="head-1"/>'
                     b'</signals></road><controller id="controller-1">'
                     b'<control signalId="head-1"/></controller></OpenDRIVE>\n')
        (self.source / "candidate-corridor.xodr").write_bytes(map_bytes)
        route = self.base["route_id"]
        common = {"route_id": route, "source_evidence": "synthetic unit test only"}
        declarations = {
            "official-signal.json": {**common, "signal_source_id": "head-1"},
            "highway-survey.json": {**common,
                                     "polygon_xy_m": self.base["highway_polygon_xy_m"]},
            "driver-none.json": {**common, "governing_device_ids": [],
                                 "readback_api": "set_pedestrian_indication,get_state,get_countdown"},
            "driver-one.json": {**common, "governing_device_ids": [8],
                                "readback_api": "set_pedestrian_indication,get_state,get_countdown"},
        }
        for name, value in declarations.items():
            (self.source / name).write_text(json.dumps(value) + "\n")
        for base_name, driver in (("no-device-base.json", "driver-none.json"),
                                  ("one-device-base.json", "driver-one.json")):
            path = self.source / base_name
            scene = json.loads(path.read_text())
            device_path = self.source / scene["device_inventory_review"]["source_path"]
            device_path.write_text(json.dumps({"route_id": route,
                                               "source_evidence": "synthetic unit test only",
                                               "device_ids": scene["governing_pedestrian_device_ids"]}) + "\n")
            scene["device_inventory_review"]["source_sha256"] = self._binding(device_path.name)["sha256"]
            camera_path = self.source / scene["camera_placement_review"]["source_path"]
            camera_path.write_text(json.dumps({"route_id": route,
                                               "source_evidence": "synthetic unit test only",
                                               "camera_placements": scene["camera_placements"]}) + "\n")
            scene["camera_placement_review"]["source_sha256"] = self._binding(camera_path.name)["sha256"]
            scene["map_source_sha256"] = hashlib.sha256(map_bytes).hexdigest()
            scene["production_source_review"] = {
                "complete": True, "route_id": route,
                "facing_signal_source_id": "head-1",
                "controller_source_id": "controller-1",
                "official_signal": self._binding("official-signal.json"),
                "pedestrian_device_driver": self._binding(driver),
                "highway_boundary_survey": self._binding("highway-survey.json"),
            }
            path.write_text(json.dumps(scene) + "\n")
        ids = materialize(self.source, self.output)
        for case_id in ids:
            target = self.output / case_id
            for name in declarations:
                self.assertEqual((target / name).read_bytes(),
                                 (self.source / name).read_bytes())
        self.assertEqual(len(ids), 6)

    def test_changed_production_source_rejected_before_output(self):
        path = self.source / "no-device-base.json"
        scene = json.loads(path.read_text())
        scene["production_source_review"] = {
            "complete": True, "official_signal": {"path": "absent.json", "sha256": "0" * 64}}
        path.write_text(json.dumps(scene) + "\n")
        with self.assertRaisesRegex(ValueError, "official_signal source missing"):
            materialize(self.source, self.output)
        self.assertFalse(self.output.exists())

    def _binding(self, name):
        return {"path": name,
                "sha256": hashlib.sha256((self.source / name).read_bytes()).hexdigest()}


if __name__ == "__main__":
    unittest.main()
