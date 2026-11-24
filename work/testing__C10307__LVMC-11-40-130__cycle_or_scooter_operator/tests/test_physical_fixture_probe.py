import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lifecycle_probe import ORDER, verify
from physical_fixture_probe import evaluate


class PhysicalFixtureTests(unittest.TestCase):
    def test_three_synthetic_outcomes_and_missing_frame_rejection(self):
        case = "testing__C10307__LVMC-11-40-130__cycle_or_scooter_operator__reference"
        expected = {"complete_motion": "met", "incomplete_motion": "not_met",
                    "missing_evidence": "unverified"}
        for kind, status in expected.items():
            path = ROOT / f"physical-reference-{kind}-source.json"
            result = evaluate(path)
            self.assertEqual(result["case_id"], case)
            self.assertEqual(result["physical_checks"]["maneuver"]["status"], status)
            self.assertEqual(result["maneuver_completed"], status == "met")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "missing.json"
            source = json.loads((ROOT / "physical-reference-complete_motion-source.json").read_text())
            source["samples"][400]["frame"] += 1
            path.write_text(json.dumps(source))
            self.assertEqual(evaluate(path)["physical_checks"]["maneuver"]["status"], "unverified")

    def test_saved_waits_for_ordered_native_release(self):
        self.assertTrue(verify(ORDER)["native_ownership_closed_before_saved"])
        bad = list(ORDER)
        bad[-2:] = reversed(bad[-2:])
        with self.assertRaisesRegex(ValueError, "precedes Native ownership closure"):
            verify(bad)


if __name__ == "__main__":
    unittest.main()
