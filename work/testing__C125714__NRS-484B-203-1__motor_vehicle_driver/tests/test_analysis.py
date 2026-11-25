"""Saved-only body and pixel audit from retained textual diagnostic sources."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT.parents[1] / ".runtime-work" / "c125714-2031-analysis-tests"
sys.path.insert(0, str(ROOT))

from analysis import build_report, constraint_context_measurement, write_selected_result
from native_history import capture
from test_native_history import CameraAdapter
from test_opposing_pass import site


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "config.json").write_bytes((ROOT / "config.json").read_bytes())
        packet = site()
        packet["native_road_frame"] = {"source_id": "diagnostic axis",
            "origin_xyz_m": [0, 0, 0], "forward_xy": [1, 0]}
        packet["paved_boundary_source"] = "diagnostic reviewed edge"
        map_path = self.root / "map.json"
        map_path.write_text(json.dumps(packet) + "\n")
        (self.root / "reviewed-map.json").write_bytes(map_path.read_bytes())
        digest = hashlib.sha256(map_path.read_bytes()).hexdigest()
        dimensions = {name: (2, 2) for name in
            ("overview", "approach", "reference_corner", "driver_reference")}
        self.dimensions = dimensions
        receipt = capture(CameraAdapter(digest), map_path, digest, "right_half",
                          self.root / "opposing-actor-trace.json", frames=3,
                          diagnostic_fixture=True,
                          media_output=self.root / "opposing-camera-frames",
                          camera_dimensions=dimensions)
        (self.root / "opposing-capture-receipt.json").write_text(json.dumps(receipt) + "\n")

    def test_saved_measurement_rejects_original_claim(self):
        report = build_report(self.root, diagnostic_fixture=True,
                              camera_dimensions=self.dimensions)
        self.assertEqual(report["camera_audit"]["decoded_view_frames"], 12)
        self.assertEqual(report["measurements"]["opposing_pass_measurement"]["value"]["passing_frames"], [1])
        for key in ("opposing_motion", "paved_allocation", "constraint_context"):
            item = report["measurements"][key]
            self.assertIsInstance(item["value"], dict)
            for name, digest in item["sources"].items():
                self.assertEqual(digest, hashlib.sha256((self.root / name).read_bytes()).hexdigest())
        self.assertFalse(report["physical_acceptance_claimed"])
        with self.assertRaisesRegex(ValueError, "provenance differ"):
            build_report(self.root, camera_dimensions=self.dimensions)

    def test_changed_original_bytes_fail_closed(self):
        image = self.root / "opposing-camera-frames" / "approach-000001.png"
        image.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "camera bytes changed"):
            build_report(self.root, diagnostic_fixture=True,
                         camera_dimensions=self.dimensions)

    def test_missing_reviewed_source_is_exact_negative(self):
        (self.root / "reviewed-map.json").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source: reviewed-map.json"):
            build_report(self.root, diagnostic_fixture=True,
                         camera_dimensions=self.dimensions)

    def test_constraint_context_is_required_only_for_constrained_case(self):
        self.assertEqual(constraint_context_measurement({}, "right_half"),
                         {"feature_present": False, "legal_reasonableness": "unresolved"})
        with self.assertRaisesRegex(ValueError, "source-recorded physical constraint"):
            constraint_context_measurement({}, "right_constrained")

    def test_saved_result_projects_frozen_recording_channels(self):
        sys.path.insert(0, str(ROOT.parents[1] / "runtime"))
        from scenario_pipeline.batch_pipeline.validation import recording_evidence
        from scenario_pipeline.worker_exchange.native_output import validate_result
        (self.root / "trace.jsonl").write_text('{"frame":0,"time_s":0}\n')
        (self.root / "video_frames.jsonl").write_text('{"video_frame":0,"carla_frame":0,"time_s":0}\n')
        for name in ("overview", "approach", "reference_corner", "driver_reference"):
            (self.root / (name + ".mkv")).write_bytes(b"diagnostic placeholder")
        report = build_report(self.root, diagnostic_fixture=True,
                              camera_dimensions=self.dimensions)
        result = write_selected_result(self.root, report)
        validate_result(result)
        recording_evidence(result, result["recording_description"],
                           lambda name: self.root / name)
        self.assertFalse(result["maneuver_completed"])
        self.assertFalse(result["target_checks"][0]["physical_cause_confirmed"])
        with self.assertRaises(FileExistsError):
            write_selected_result(self.root, report)


if __name__ == "__main__":
    unittest.main()
