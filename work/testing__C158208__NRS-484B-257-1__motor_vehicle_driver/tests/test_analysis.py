import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis import analyze, measure_nearest_view
from build_semantic_proposals import recording_description
from build_semantic_proposals import KINDS
from camera_sources import write_camera_sources
from test_camera_sources import fixture
from test_camera_sources import GEOMETRY, raw, png
from test_branch_site_preflight import BranchSitePreflightTests
from source_tick_capture import TickCapture, write_capture_identity
from camera_sources import CAMERAS
from selected_delivery_audit import audit as audit_delivery


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

    def test_source_shaped_marked_stop_line_history_uses_branch_measurement(self):
        kind = "marked_stop_line_response"
        case = ROOT.name + "__" + kind
        diagnostic = self.root / "branch-attempt"
        site = BranchSitePreflightTests().site_for(kind)
        site.update({"review_status": "reviewed", "capture_geometry": GEOMETRY,
                     "stopping_reference_station_m": 6.0})
        capture = TickCapture(diagnostic, GEOMETRY, site["reviewed_context"])
        frames = []
        for index in range(3):
            observed = raw(index)
            capture.append(observed)
            frames.append({"frame": observed["frame"], "time_s": observed["time_s"],
                           "cameras": {name: png((index * 30, camera * 40, 60))
                                       for camera, name in enumerate(CAMERAS)}})
        capture.close()
        construction = self.root / "branch-construction.json"
        construction.write_text(json.dumps({"case_id": case, "law_id": "NRS-484B-257-1",
            "cell_id": "C158208", "actor": "motor_vehicle_driver", "diagnostic_only": True}) + "\n")
        opendrive = b"<OpenDRIVE>synthetic test only</OpenDRIVE>"
        site["map_opendrive_sha256"] = hashlib.sha256(opendrive).hexdigest()
        site_path = diagnostic / "diagnostic-site.json"
        site_path.write_text(json.dumps(site, sort_keys=True) + "\n")
        write_capture_identity(diagnostic, case, construction, site_path, opendrive,
                               diagnostic_fixture=True)
        (diagnostic / "scene.json").write_text(json.dumps({
            "source_kind": "synthetic_reviewed_fixture", "site_source": site_path.name,
            "site_sha256": hashlib.sha256(site_path.read_bytes()).hexdigest()}) + "\n")
        write_camera_sources(diagnostic, frames, diagnostic_fixture=True)
        report = analyze(diagnostic, self.root / "branch-analysis-report.json")
        measured = report["measurements"]["statutory_branch_history"]
        self.assertEqual(measured["method"], "measure_statutory_branch")
        self.assertEqual(measured["value"]["reference_branch"], "marked_stop_line")
        self.assertEqual(measured["value"]["legal_status"], "unresolved")

    def test_all_nine_additional_branch_histories_from_sealed_diagnostic_sources(self):
        for kind in KINDS[2:]:
            with self.subTest(kind=kind):
                case = ROOT.name + "__" + kind
                diagnostic = self.root / (kind + "-attempt")
                site = BranchSitePreflightTests().site_for(kind)
                site.update({"review_status": "reviewed", "capture_geometry": GEOMETRY,
                             "stopping_reference_station_m": 6.0})
                capture = TickCapture(diagnostic, GEOMETRY, site["reviewed_context"])
                frames = []
                for index in range(3):
                    observed = raw(index)
                    capture.append(observed)
                    frames.append({"frame": observed["frame"], "time_s": observed["time_s"],
                                   "cameras": {name: png((index * 30, camera * 40, 60))
                                               for camera, name in enumerate(CAMERAS)}})
                capture.close()
                construction = self.root / (kind + "-construction.json")
                construction.write_text(json.dumps({"case_id": case, "law_id": "NRS-484B-257-1",
                    "cell_id": "C158208", "actor": "motor_vehicle_driver",
                    "diagnostic_only": True}) + "\n")
                opendrive = b"<OpenDRIVE>synthetic test only</OpenDRIVE>"
                site["map_opendrive_sha256"] = hashlib.sha256(opendrive).hexdigest()
                site_path = diagnostic / "diagnostic-site.json"
                site_path.write_text(json.dumps(site, sort_keys=True) + "\n")
                write_capture_identity(diagnostic, case, construction, site_path, opendrive,
                                       diagnostic_fixture=True)
                (diagnostic / "scene.json").write_text(json.dumps({
                    "source_kind": "synthetic_reviewed_fixture", "site_source": site_path.name,
                    "site_sha256": hashlib.sha256(site_path.read_bytes()).hexdigest()}) + "\n")
                (diagnostic / "diagnostic-compatibility.json").write_text(json.dumps({
                    "format": "c158208-generated-compatibility-v1", "case_id": case,
                    "frame_count": 3, "source_kind": "synthetic_fixture"}) + "\n")
                for name in CAMERAS:
                    size = "1920x1080" if name == "overview" else "1280x720"
                    subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                                    "-n", "-f", "lavfi", "-i", f"color=c=blue:s={size}:r=20",
                                    "-frames:v", "3", "-an", "-c:v", "ffv1", "-threads", "1",
                                    str(diagnostic / (name + ".mkv"))], check=True)
                (diagnostic / "config.json").write_text(json.dumps({
                    "selected_case_id": case, "rate_hz": 20, "duration_s": 45}) + "\n")
                (diagnostic / "construction.json").write_text(json.dumps({
                    "case_id": case, "recording_description": recording_description()}) + "\n")
                report = analyze(diagnostic, self.root / (kind + "-analysis.json"))
                measured = report["measurements"]["statutory_branch_history"]
                self.assertEqual(measured["method"], "measure_statutory_branch")
                self.assertEqual(measured["value"]["case_id"], case)
                self.assertEqual(measured["value"]["sample_count"], 3)
                self.assertEqual(measured["value"]["legal_status"], "unresolved")
                (diagnostic / "analysis-report.json").write_text(json.dumps(report) + "\n")
                audited = audit_delivery(diagnostic, case_id=case, diagnostic_fixture=True)
                self.assertEqual(audited["source_frames"], 3)
                self.assertEqual(len(audited["camera_sources"]), 4)


if __name__ == "__main__":
    unittest.main()
