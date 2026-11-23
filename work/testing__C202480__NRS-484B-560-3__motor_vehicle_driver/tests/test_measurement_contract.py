"""Bind all four statutory observations to saved original sources."""

import json
import os
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from saved_measurement import analyze, finalize_attempt
import test_saved_measurement as saved_fixture


class MeasurementContractTests(unittest.TestCase):
    def test_selected_requirements_and_source_hashes(self):
        output = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
        self.assertTrue(output)
        self.assertIn(ROOT / ".runtime-work", Path(output).resolve().parents)
        sys.path.insert(0, str(ROOT / "runtime"))
        from scenario_pipeline.worker_exchange.measurement_contract import validate, verify_report

        plan = json.loads((HERE / "case-plan.json").read_text())
        contract = json.loads((HERE / "measurement-contract.json").read_text())
        case_id = plan["cases"][0]["case_id"]
        validate(contract, plan["requirement_dispositions"],
                 (HERE / "saved_measurement.py").read_text(), case_id)
        fixture = saved_fixture.SavedMeasurementTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        report = finalize_attempt(fixture.attempt, fixture.attempt / "analysis-report.json")
        verified = verify_report(contract, report, fixture.attempt)
        self.assertEqual(len(verified), 4)
        self.assertEqual(verified["marked_lane_qualification_observation"]["value"]
                         ["total_marked_highway_lane_count"], 2)
        (fixture.attempt / "site/packet.json").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source: site/packet.json"):
            analyze(fixture.attempt)


if __name__ == "__main__":
    unittest.main()
