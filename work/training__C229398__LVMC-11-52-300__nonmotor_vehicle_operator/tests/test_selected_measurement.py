"""Full-length synthetic 20 Hz source join and boundary checks."""

import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "native"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runtime" /
                       "scenario_pipeline"))
from duration_policy import TOTAL_FRAMES, stop_frame
from finalize import finalize
from selected_measurement import in_night_window, measure
from source_gate import FIELDS


ASSIGNMENT = "training__C229398__LVMC-11-52-300__nonmotor_vehicle_operator"


class SelectedMeasurementTest(unittest.TestCase):
    def test_civil_window_endpoints(self):
        self.assertFalse(in_night_window(datetime(2026, 11, 27, 0, 59, 59)))
        self.assertTrue(in_night_window(datetime(2026, 11, 27, 1, 0, 0)))
        self.assertTrue(in_night_window(datetime(2026, 11, 27, 5, 59, 59)))
        self.assertFalse(in_night_window(datetime(2026, 11, 27, 6, 0, 0)))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[3] /
                                                ".runtime-work")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def fixture(self, suffix):
        folder = self.root / suffix
        folder.mkdir()
        case = ASSIGNMENT + "__" + suffix
        config = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text())
        config["case_id"] = case
        config["selected_case_id"] = case
        config["case"]["case_id"] = case
        (folder / "config.json").write_text(json.dumps(config) + "\n")
        construction_path = (Path(__file__).resolve().parents[1] /
                             ("construction.json" if suffix == "below_30" else
                              "cases/" + suffix + "/construction.json"))
        (folder / "construction.json").write_bytes(construction_path.read_bytes())
        stop = stop_frame(case)
        with (folder / "native-actor-frames.jsonl").open("w") as actor_out, (
                folder / "video_frames.jsonl").open("w") as map_out:
            for frame in range(TOTAL_FRAMES):
                actor_out.write(json.dumps({"frame": frame, "native_frame": 100 + frame,
                                            "center_xyz_m": [40.0, -1.75, 0.5],
                                            "velocity_xyz_mps": [0.0 if frame >= stop else 1.5,
                                                                 0.0, 0.0]}) + "\n")
                map_out.write(json.dumps({"video_frame": frame, "native_frame": 100 + frame,
                                          "time_s": frame / 20}) + "\n")
        (folder / "street-geometry.json").write_text(json.dumps({
            "street_bounds_xy_m": [0.0, 100.0, -3.5, 3.5],
            "source_kind": "synthetic_cpu"}) + "\n")
        findings = {"transport_capability": True, "excluded_device": False,
                    "self_propulsion": False, "responsible_person": "synthetic operator",
                    "parking_purpose": "park", "active_loading_or_unloading": False,
                    "street_public_access": True, "city_limits": True,
                    "civil_clock": {"iana_timezone": "America/Los_Angeles",
                                    "utc_start_ms": 1795425000000}}
        sources = {}
        for name in FIELDS:
            path = folder / (name + ".json")
            path.write_text(json.dumps({"synthetic_finding": findings[name]}) + "\n")
            sources[name] = {"path": path.name,
                             "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                             "citation": "Synthetic CPU fixture for " + name,
                             "source_kind": "synthetic_cpu"}
        (folder / "review-source.json").write_text(json.dumps({
            "format": "c229398-source-review-v1", "case_id": case,
            "source_kind": "synthetic_cpu", "findings": findings,
            "sources": sources}) + "\n")
        return folder

    def test_exact_and_above_boundary(self):
        exact = measure(self.fixture("at_30"))
        above = measure(self.fixture("above_30"))
        self.assertEqual(exact["longest_continuous_qualifying_ms"], 1800000)
        self.assertFalse(exact["observed_over_thirty_minutes"])
        self.assertEqual(above["longest_continuous_qualifying_ms"], 1801000)
        self.assertTrue(above["observed_over_thirty_minutes"])
        self.assertFalse(above["physical_or_legal_acceptance"])

    def test_missing_or_bad_frame_source(self):
        folder = self.fixture("below_30")
        (folder / "street-geometry.json").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source: street-geometry"):
            measure(folder)
        (folder / "street-geometry.json").write_text(json.dumps({
            "street_bounds_xy_m": [0, 100, -4, 4]}) + "\n")
        actor = folder / "native-actor-frames.jsonl"
        rows = actor.read_text().splitlines()
        actor.write_text("\n".join(rows[:-1]) + "\n")
        with self.assertRaisesRegex(ValueError, "Actor/video frame counts differ"):
            measure(folder)

    def test_original_requires_original_review(self):
        folder = self.fixture("below_30")
        with self.assertRaisesRegex(ValueError, "Original review required"):
            measure(folder, require_original=True)

    def test_short_synthetic_compatibility_excerpt_is_explicit(self):
        folder = self.fixture("above_30")
        for name in ("native-actor-frames.jsonl", "video_frames.jsonl"):
            path = folder / name
            path.write_text("\n".join(path.read_text().splitlines()[:100]) + "\n")
        report = measure(folder)
        self.assertEqual(report["frame_count"], 100)
        self.assertTrue(report["diagnostic_excerpt"])
        self.assertFalse(report["observed_over_thirty_minutes"])
        self.assertFalse(report["physical_or_legal_acceptance"])

    def test_saved_result_projection_schema(self):
        folder = self.fixture("above_30")
        (folder / "trace.jsonl").write_text('{"synthetic":true}\n')
        (folder / "raw.mkv").write_bytes(b"synthetic fixture placeholder; not video")
        report = finalize(folder, folder / "analysis-report.json")
        result = json.loads((folder / "result.json").read_text())
        self.assertEqual(report["measurements"]["night_parking_duration"]["value"],
                         1801000)
        self.assertTrue(result["maneuver_completed"])
        self.assertEqual(result["provenance_kind"], "synthetic_fixture")
        self.assertFalse(result["target_checks"][0]["physical_cause_confirmed"])
        self.assertFalse(result["accepted"])


if __name__ == "__main__":
    unittest.main()
