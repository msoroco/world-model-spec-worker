import json
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REPO / "runtime"))
sys.path.insert(0, str(REPO / "runtime" / "scenario_pipeline"))

from saved_case_analysis import analyze, finalize_attempt, saved_result
from build_construction_draft import build as build_construction
from test_turn_trace_finalizer import SavedNativeTraceTest, interpolate_path
from stand_route import make
from candidate_opendrive import build
from taxi_native_motion import route_points
from scenario_pipeline.worker_exchange.measurement_contract import validate, verify_report
from worker_exchange.native_output import validate_result
from batch_pipeline.validation import recording_evidence


class SavedCaseAnalysisTest(unittest.TestCase):
    def setUp(self):
        self.fixture = SavedNativeTraceTest(
            "test_original_frame_route_yields_right_turn_measurement")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.plan = json.loads((ROOT / "case-plan.json").read_text())
        self.contract = json.loads((ROOT / "cases" / "near_stand" /
                                    "selected-measurement-contract.json").read_text())

    def populate_saved_native_shape(self):
        construction = build_construction(self.fixture.case)
        (self.fixture.root / "construction.json").write_text(
            json.dumps(construction))
        config = next(item["content"] for item in construction["files"]
                      if item["path"] == "config.json")
        (self.fixture.root / "config.json").write_text(config)
        trace = []
        mapping = []
        controls = []
        for index, row in enumerate(self.fixture.rows):
            trace.append({"frame": row["frame"], "time_s": row["time_s"],
                          "position": {"x": row["x_m"], "y": row["y_m"], "z": 0},
                          "position_m": [row["x_m"], row["y_m"], 0],
                          "heading_deg": row["yaw_deg"], "speed_mps": 5.0,
                          "road_id": row["road_id"]})
            mapping.append({"carla_frame": row["frame"], "video_frame": index,
                            "time_s": row["time_s"]})
            controls.append({"frame": row["frame"], "time_s": row["time_s"],
                             "control": {"steer": 0.0, "throttle": 0.2}})
        for name, rows in (("trace.jsonl", trace), ("video_frames.jsonl", mapping),
                           ("taxi-controller-history.jsonl", controls)):
            (self.fixture.root / name).write_text(
                "".join(json.dumps(row) + "\n" for row in rows))
        for name in ("overview", "approach", "reference_corner", "driver_reference"):
            (self.fixture.root / (name + ".mkv")).write_bytes(
                b"synthetic unit-test placeholder, no media proof")

    def test_pinned_contract_and_saved_source_report(self):
        for case in self.plan["cases"]:
            suffix = case["case_id"].removeprefix(self.plan["assignment_id"] + "__")
            contract = json.loads((ROOT / "cases" / suffix /
                                   "selected-measurement-contract.json").read_text())
            validate(contract, self.plan["requirement_dispositions"],
                     (ROOT / "saved_case_analysis.py").read_text(),
                     case["case_id"])
        with tempfile.TemporaryDirectory() as temp:
            report = analyze(self.fixture.root, Path(temp) / "analysis-report.json")
            verified = verify_report(self.contract, report, self.fixture.root)
            self.assertTrue(
                verified["first_intersection_maneuver"]["value"]
                ["engineering_right_turn_observed"])
            self.assertEqual(json.loads((Path(temp) / "analysis-report.json").read_text()),
                             report)

    def test_missing_context_is_specific_negative(self):
        self.fixture.context_packet.unlink()
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,
                                        self.contract["negative"]["error_contains"]):
                analyze(self.fixture.root, Path(temp) / "analysis-report.json")

    def test_straight_case_reports_observed_non_right_turn(self):
        self.fixture.test_straight_attempt_yields_non_right_turn_measurement()
        contract = json.loads((ROOT / "cases" / "near_stand_straight" /
                               "selected-measurement-contract.json").read_text())
        with tempfile.TemporaryDirectory() as temp:
            report = analyze(self.fixture.root, Path(temp) / "analysis-report.json")
            verified = verify_report(contract, report, self.fixture.root)
            self.assertFalse(
                verified["first_intersection_maneuver"]["value"]
                ["engineering_right_turn_observed"])
            self.populate_saved_native_shape()
            result = saved_result(self.fixture.root, report)
            self.assertTrue(result["target_checks"][0]["matched"])
            self.assertEqual(result["physical_checks"]["maneuver"]["status"], "met")

    def test_far_case_reports_saved_turn(self):
        case = "far_stand"
        layout = make(case)
        self.fixture.case = case
        self.fixture.layout.write_text(json.dumps(layout))
        self.fixture.map.write_bytes(build(case))
        self.fixture.context["case_id"] = self.plan["assignment_id"] + "__" + case
        self.fixture.context["map_sha256"] = hashlib.sha256(
            self.fixture.map.read_bytes()).hexdigest()
        self.fixture.context["stand_center_m"] = layout["stand"]["center"]
        self.fixture.context["notice_point_m"] = layout["posted_notice"]["point"]
        self.fixture.context_packet.write_text(json.dumps(self.fixture.context))
        self.fixture.rows = interpolate_path(route_points(layout), case)
        self.fixture.write_sources()
        contract = json.loads((ROOT / "cases" / case /
                               "selected-measurement-contract.json").read_text())
        with tempfile.TemporaryDirectory() as temp:
            report = analyze(self.fixture.root, Path(temp) / "analysis-report.json")
            verified = verify_report(contract, report, self.fixture.root)
            self.assertTrue(
                verified["first_intersection_maneuver"]["value"]
                ["engineering_right_turn_observed"])
            self.populate_saved_native_shape()
            result = saved_result(self.fixture.root, report)
            self.assertTrue(result["target_checks"][0]["matched"])
            self.assertEqual(result["physical_checks"]["maneuver"]["status"], "met")

    def test_analysis_entrypoint_reads_saved_attempt(self):
        self.populate_saved_native_shape()
        with tempfile.TemporaryDirectory() as temp:
            command = [sys.executable, str(ROOT / "saved_case_analysis.py"),
                       "--attempt", str(self.fixture.root), "--output",
                       str(Path(temp) / "analysis-report.json")]
            result = subprocess.run(
                command, capture_output=True, text=True,
                env={**os.environ,
                     "PYTHONPATH": str(REPO / "runtime" / "scenario_pipeline")})
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((Path(temp) / "analysis-report.json").read_text())
            verify_report(self.contract, report, self.fixture.root)
            result_json = json.loads((self.fixture.root / "result.json").read_text())
            validate_result(result_json)
            recording_evidence(result_json,
                               build_construction(self.fixture.case)["recording_description"],
                               lambda reference: self.fixture.root / reference)
            self.assertTrue(result_json["target_checks"][0]["matched"])
            self.assertFalse(result_json["physical_acceptance_claimed"])


if __name__ == "__main__":
    unittest.main()
