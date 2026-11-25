import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis import analyze, measure_nearest_view
from build_semantic_proposals import recording_description
from camera_sources import write_camera_sources
from test_camera_sources import fixture


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.attempt = self.root / "attempt"
        frames = fixture(self.attempt)
        write_camera_sources(self.attempt, frames, diagnostic_fixture=True)

    def test_source_bound_report_reopens_pixels_and_ticks(self):
        report = analyze(self.attempt, self.root / "analysis-report.json")
        self.assertEqual(report["measurements"]["nearest_view_history"]["value"]["sample_count"], 3)
        self.assertTrue(report["diagnostic_fixture"])
        self.assertIsNone(report["legal_judgment"])
        self.assertEqual(report["measurements"]["governing_control_context"]["value"][
            "no_marked_stop_line"], True)

    def test_missing_case_source_fails_before_report(self):
        (self.attempt / "nearest-view-saved-packet.json").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source: nearest-view-saved-packet.json"):
            analyze(self.attempt, self.root / "analysis-report.json")
        self.assertFalse((self.root / "analysis-report.json").exists())

    def test_altered_original_pixels_fail(self):
        archive = self.attempt / "nearest-view-overview-original-png.zip"
        archive.write_bytes(archive.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "original archive hash differs"):
            measure_nearest_view(self.attempt)

    def test_selected_stage_builds_native_result_and_four_derived_videos(self):
        case = "testing__C158208__NRS-484B-257-1__motor_vehicle_driver__nearest_view_response"
        (self.attempt / "config.json").write_text(json.dumps({
            "selected_case_id": case, "rate_hz": 20, "duration_s": 45}) + "\n")
        (self.attempt / "construction.json").write_text(json.dumps({
            "case_id": case, "recording_description": recording_description()}) + "\n")
        report = analyze(self.attempt, self.root / "analysis-report.json")
        result = json.loads((self.attempt / "result.json").read_text())
        self.assertEqual(report["case_id"], result["case_id"])
        self.assertEqual(len(result["recording_evidence"]), 6)
        self.assertEqual(len((self.attempt / "trace.jsonl").read_text().splitlines()), 3)
        self.assertEqual(len(result["video_references"]), 4)
        self.assertTrue(all((self.attempt / name).is_file() for name in result["video_references"]))
        self.assertFalse(result["maneuver_completed"])


if __name__ == "__main__":
    unittest.main()
