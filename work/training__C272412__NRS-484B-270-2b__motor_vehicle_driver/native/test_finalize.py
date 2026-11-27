"""Saved-only conversion rejects absent original sources and wrong identity."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from finalize import CHANNELS, finalize
from test_measure import fixture


class FinalizeTests(unittest.TestCase):
    def test_source_bound_channels_and_negative(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as temp:
            attempt = fixture(Path(temp))
            case = "training__C272412__NRS-484B-270-2b__motor_vehicle_driver__witness_1"
            (attempt / "config.json").write_text(json.dumps({
                "case_id": case, "selected_case_id": case, "law_id": "NRS-484B-270-2b",
                "rate_hz": 20, "duration_s": 30,
                "physical_completion": {"criterion": "overtake_pass",
                    "motion_source": "participant-poses.jsonl", "body_key": "ego.body_xy_m",
                    "other_body_key": "scooter.body_xy_m", "minimum_progress_m": 1}}) + "\n")
            (attempt / "construction.json").write_text(json.dumps({
                "case_id": case, "recording_description": {"channels": [
                    {"name": name, "unit": "original source derived"} for name in CHANNELS]}}) + "\n")
            result = finalize(attempt, Path(temp) / "analysis.json")
            self.assertFalse(result["physical_or_legal_acceptance"])
            self.assertEqual(len(list((attempt / "channels").glob("*.jsonl"))), len(CHANNELS))
            context = json.loads((attempt / "channels/source_review.json").read_text())
            self.assertIn("source_review", context)
            self.assertFalse(context["source_review"]["continuous_between_frame_clearance_confirmed"])
            self.assertFalse(json.loads((attempt / "result.json").read_text())["accepted"])
            self.assertEqual(json.loads((attempt / "result.json").read_text())
                             ["physical_checks"]["maneuver"]["status"], "met")
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as temp:
            attempt = fixture(Path(temp))
            (attempt / "capture/evidence.jsonl").unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source"):
                finalize(attempt, Path(temp) / "analysis.json")


if __name__ == "__main__":
    unittest.main()
