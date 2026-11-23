import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REPO / "runtime"))

from saved_case_analysis import analyze
from test_turn_trace_finalizer import SavedNativeTraceTest, interpolate_path
from stand_route import make
from candidate_opendrive import build
from taxi_native_motion import route_points
from scenario_pipeline.worker_exchange.measurement_contract import validate, verify_report


class SavedCaseAnalysisTest(unittest.TestCase):
    def setUp(self):
        self.fixture = SavedNativeTraceTest(
            "test_original_frame_route_yields_right_turn_measurement")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.plan = json.loads((ROOT / "case-plan.json").read_text())
        self.contract = json.loads((ROOT / "cases" / "near_stand" /
                                    "selected-measurement-contract.json").read_text())

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

    def test_analysis_entrypoint_reads_saved_attempt(self):
        with tempfile.TemporaryDirectory() as temp:
            command = [sys.executable, str(ROOT / "saved_case_analysis.py"),
                       "--attempt", str(self.fixture.root), "--output",
                       str(Path(temp) / "analysis-report.json")]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((Path(temp) / "analysis-report.json").read_text())
            verify_report(self.contract, report, self.fixture.root)


if __name__ == "__main__":
    unittest.main()
