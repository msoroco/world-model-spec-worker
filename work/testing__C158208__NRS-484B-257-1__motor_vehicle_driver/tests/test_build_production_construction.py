import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build_production_construction import build
from camera_sources import CAMERAS
from native_attempt import REVIEW_SOURCES
from test_source_tick_capture import CONTEXT, GEOMETRY
from branch_site_preflight import SURVEY_FOR_FINDING
from build_semantic_proposals import KINDS, case_settings
from branch_site_preflight import REFERENCE_FINDINGS


class ProductionConstructionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.site_path = self.root / "reviewed-site.json"
        pose = {"location": {"x": 0.0, "y": 5.0, "z": 1.0},
                "rotation": {"pitch": 0.0, "yaw": 0.0, "roll": 0.0}}
        through_pose = {"location": {"x": 5.0, "y": -5.0, "z": 1.0},
                        "rotation": {"pitch": 0.0, "yaw": 90.0, "roll": 0.0}}
        self.site = {"review_status": "reviewed", "cell_id": "C158208",
                     "source_provenance": "native_operator_review",
                     "capture_geometry": GEOMETRY, "reviewed_context": CONTEXT,
                     "ego_view_station_m": 8.0,
                     "native_scene": {
                         "ego": {"blueprint_id": "vehicle.test.ego", "transform": pose},
                         "through_vehicle": {"blueprint_id": "vehicle.test.through", "transform": through_pose,
                                             "motion_plan": {"target_speed_mps": 4.0, "start_delay_s": 0.0,
                                                             "steering_mode": "follow_reviewed_route_axis"}},
                         "cameras": {name: {"attach_to": "ego", "transform": pose,
                                            "fov_degrees": 90.0} for name in CAMERAS},
                         "yield_sign_landmark_id": "synthetic-sign"},
                     "source_bindings": {}}
        self.site["finding_sources"] = {name: SURVEY_FOR_FINDING[name] for name in CONTEXT}
        self.site["finding_sources"]["planned_through_traffic_phase"] = "through_highway_survey"
        self.site["planned_through_traffic_phase"] = "occupied_at_reference"
        self.site["planned_response_mode"] = "response"
        for name in REVIEW_SOURCES:
            data = b"<OpenDRIVE>synthetic test only</OpenDRIVE>" if name == "native_map" else name.encode()
            filename = name + ".txt"
            (self.root / filename).write_bytes(data)
            self.site["source_bindings"][name] = {"path": filename,
                                                   "sha256": hashlib.sha256(data).hexdigest()}
        self.site["map_opendrive_sha256"] = self.site["source_bindings"]["native_map"]["sha256"]
        self.write_site()

    def write_site(self):
        self.site_path.write_text(json.dumps(self.site, indent=2) + "\n")

    def test_embeds_exact_review_sources_without_selecting_manifest(self):
        output = self.root / "production-construction.json"
        result = build("nearest_view_response", self.site_path, output)
        construction = json.loads(output.read_text())
        files = {item["path"]: item["content"] for item in construction["files"]}
        scene = json.loads(files["scene.json"])
        self.assertFalse(construction["diagnostic_only"])
        self.assertEqual(construction["case_id"], result["case_id"])
        self.assertEqual(scene["site_sha256"], hashlib.sha256(self.site_path.read_bytes()).hexdigest())
        self.assertEqual(scene["capture_geometry"], GEOMETRY)
        self.assertEqual(files[self.site_path.name], self.site_path.read_text())
        self.assertEqual(files["analysis.py"], (ROOT / "analysis.py").read_text())
        self.assertEqual(files["prepare_derived_media.py"], (ROOT / "prepare_derived_media.py").read_text())
        self.assertEqual(files["native_capture_finalize.py"], (ROOT / "native_capture_finalize.py").read_text())
        self.assertEqual(files["through_traffic_control.py"], (ROOT / "through_traffic_control.py").read_text())
        self.assertIn("close_capture(Path(args.output_dir), release)", files["runner.py"])
        self.assertTrue(set(self.site["source_bindings"][name]["path"] for name in REVIEW_SOURCES).issubset(files))
        self.assertEqual(files["statutory_branch_measurement.py"],
                         (ROOT / "statutory_branch_measurement.py").read_text())
        with self.assertRaisesRegex(ValueError, "already exists"):
            build("nearest_view_response", self.site_path, output)

        materialized = self.root / "materialized"
        materialized.mkdir()
        for path, content in files.items():
            target = materialized / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        positive = subprocess.run([sys.executable, str(materialized / "runner.py"), "--check"],
                                  env=environment, capture_output=True, text=True)
        self.assertEqual(positive.returncode, 0, positive.stderr)
        self.assertIn(construction["case_id"], positive.stdout)
        (materialized / "yield_sign.txt").write_text("tampered")
        negative = subprocess.run([sys.executable, str(materialized / "runner.py"), "--check"],
                                  env=environment, capture_output=True, text=True)
        self.assertNotEqual(negative.returncode, 0)
        self.assertIn("yield_sign original source hash differs", negative.stderr)

    def test_refuses_stale_source_and_missing_scene(self):
        (self.root / "yield_sign.txt").write_text("tampered")
        with self.assertRaisesRegex(ValueError, "source hash differs"):
            build("nearest_view_response", self.site_path, self.root / "out.json")
        (self.root / "yield_sign.txt").write_text("yield_sign")
        self.site.pop("native_scene")
        self.write_site()
        with self.assertRaisesRegex(ValueError, "reviewed through-vehicle Native scene required"):
            build("nearest_view_response", self.site_path, self.root / "out.json")

    def test_rejects_incomplete_actor_camera_and_sign_source(self):
        self.site["native_scene"]["ego"]["transform"]["location"].pop("x")
        self.write_site()
        with self.assertRaisesRegex(ValueError, "ego x must be finite"):
            build("nearest_view_response", self.site_path, self.root / "out.json")
        self.site["native_scene"]["ego"]["transform"]["location"]["x"] = 0.0
        self.site["native_scene"]["cameras"]["approach"]["fov_degrees"] = 180.0
        self.write_site()
        with self.assertRaisesRegex(ValueError, "fov outside physical range"):
            build("nearest_view_response", self.site_path, self.root / "out.json")
        self.site["native_scene"]["cameras"]["approach"]["fov_degrees"] = 90.0
        self.site["native_scene"].pop("yield_sign_landmark_id")
        self.write_site()
        with self.assertRaisesRegex(ValueError, "exactly one reviewed Native yield sign"):
            build("nearest_view_response", self.site_path, self.root / "out.json")

    def test_rejects_opposed_route_and_overlapping_spawns(self):
        self.site["native_scene"]["ego"]["transform"]["rotation"]["yaw"] = 180.0
        self.write_site()
        with self.assertRaisesRegex(ValueError, "ego spawn heading opposes"):
            build("nearest_view_response", self.site_path, self.root / "out.json")
        self.site["native_scene"]["ego"]["transform"]["rotation"]["yaw"] = 0.0
        self.site["native_scene"]["through_vehicle"]["transform"]["rotation"]["yaw"] = -90.0
        self.write_site()
        with self.assertRaisesRegex(ValueError, "through_vehicle spawn heading opposes"):
            build("nearest_view_response", self.site_path, self.root / "out.json")
        self.site["native_scene"]["through_vehicle"]["transform"]["rotation"]["yaw"] = 90.0
        self.site["native_scene"]["through_vehicle"]["transform"]["location"].update(x=0.0, y=5.0)
        self.write_site()
        with self.assertRaisesRegex(ValueError, "spawn poses overlap"):
            build("nearest_view_response", self.site_path, self.root / "out.json")

    def test_each_statutory_branch_builds_source_gated_native_bundle(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                settings = case_settings(kind)
                reference = next((name for name in REFERENCE_FINDINGS
                                  if kind.startswith(name)), "nearest_view")
                self.site["reviewed_context"] = {
                    "yield_sign_governs_approach": True,
                    "through_highway_confirmed": True,
                    "no_officer_control": True,
                    "no_signal_control": True,
                    **{name: True for name in REFERENCE_FINDINGS[reference]},
                }
                self.site["finding_sources"] = {
                    name: SURVEY_FOR_FINDING[name]
                    for name in self.site["reviewed_context"]}
                self.site["finding_sources"]["planned_through_traffic_phase"] = "through_highway_survey"
                self.site["stopping_reference_station_m"] = 8.0
                self.site["planned_through_traffic_phase"] = settings["through_traffic_phase"]
                self.site["planned_response_mode"] = settings["response_mode"]
                self.write_site()
                output = self.root / (kind + ".json")
                result = build(kind, self.site_path, output)
                construction = json.loads(output.read_text())
                files = {item["path"]: item["content"] for item in construction["files"]}
                self.assertEqual(result["case_id"], construction["case_id"])
                self.assertEqual(json.loads(files["config.json"])["selected_case_id"], result["case_id"])
                self.assertEqual(files["statutory_branch_measurement.py"],
                                 (ROOT / "statutory_branch_measurement.py").read_text())
                materialized = self.root / (kind + "-bundle")
                materialized.mkdir()
                for path, content in files.items():
                    target = materialized / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(content)
                checked = subprocess.run([sys.executable, str(materialized / "runner.py"), "--check"],
                                         env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                                         capture_output=True, text=True)
                self.assertEqual(checked.returncode, 0, checked.stderr)


if __name__ == "__main__":
    unittest.main()
