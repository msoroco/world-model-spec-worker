"""Selected requirement contracts join exact source hashes and reject removal."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

from finalize import finalize
from test_measure_uturn import fixture

REPO = Path(__file__).resolve().parents[3]
PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "runtime"))
from scenario_pipeline.worker_exchange.measurement_contract import validate, verify_report


class MeasurementContractTest(unittest.TestCase):
    def test_two_case_contracts_and_missing_context(self):
        dispositions = json.loads((PKG / "case-plan.json").read_text())["requirement_dispositions"]
        code = (PKG / "native/finalize.py").read_text()
        for suffix in ("authorized_opening", "barrier_crossing"):
            with self.subTest(suffix=suffix):
                contract = json.loads((PKG / "native" / (suffix + "-measurement-contract.json")).read_text())
                case = PKG.name + "__" + suffix
                self.assertEqual(len(validate(contract, dispositions, code, case)), 1)
                with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work") as scratch:
                    attempt = Path(scratch)
                    fixture(attempt, suffix)
                    (attempt / "config.json").write_text(json.dumps({"case_id": case, "selected_case_id": case}) + "\n")
                    (attempt / "construction.json").write_text(json.dumps({"case_id": case, "recording_description": "Diagnostic"}) + "\n")
                    (attempt / "trace.jsonl").write_text('{"time_s":0}\n')
                    (attempt / "body_history.jsonl").write_text('{"frame":0}\n')
                    (attempt / "capture").mkdir()
                    (attempt / "capture/evidence.jsonl").write_text('{"frame":0}\n')
                    for name in ("overview", "approach", "median_reference", "driver_reference"):
                        (attempt / (name + ".mkv")).write_bytes(b"synthetic-video-placeholder")
                    report = finalize(attempt, attempt / "analysis-report.json")
                    self.assertIn("right_hand_roadway", verify_report(contract, report, attempt))
                    (attempt / "divided-road-context.json").unlink()
                    with self.assertRaises(FileNotFoundError):
                        verify_report(contract, report, attempt)


if __name__ == "__main__":
    unittest.main()
