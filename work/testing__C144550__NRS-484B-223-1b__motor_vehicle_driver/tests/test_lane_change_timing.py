import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lane_change_timing import ASSIGNMENT, measure


class TimingTests(unittest.TestCase):
    def trace(self, *, signal_at=1, check_at=2, gap=False):
        frames = []
        for i in range(6):
            frames.append({
                "t_s": i * (0.1 if gap else 0.05),
                "x_m": float(i), "y_m": 0.0,
                "source_lane_offset_m": 0.06 if i >= 4 else 0.0,
                "left_signal": signal_at is not None and i >= signal_at,
                "right_signal": False,
                "driver_check_observed": check_at == i,
            })
        return {"assignment_id": ASSIGNMENT, "original_trace_id": "synthetic-test-only",
                "source_lane_id": "lane-a", "frames": frames}

    def run_measure(self, trace):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            path = Path(d) / "trace.json"
            path.write_text(json.dumps(trace), encoding="utf-8")
            return measure(path)

    def test_two_observations_separate(self):
        result = self.run_measure(self.trace())
        self.assertEqual(result["signal_lead_distance_m"], 3.0)
        self.assertEqual(result["departure_bracket_indices"], [3, 4])
        self.assertTrue(result["driver_check_observed_before_departure"])

    def test_signal_only_does_not_imply_check(self):
        result = self.run_measure(self.trace(check_at=None))
        self.assertTrue(result["signal_precedes_center_departure"])
        self.assertFalse(result["driver_check_observed_before_departure"])

    def test_check_only_does_not_imply_signal(self):
        result = self.run_measure(self.trace(signal_at=None))
        self.assertTrue(result["driver_check_observed_before_departure"])
        self.assertIsNone(result["signal_lead_distance_m"])

    def test_missing_samples_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing samples"):
            self.run_measure(self.trace(gap=True))

    def test_wrong_assignment_rejected(self):
        trace = self.trace()
        trace["assignment_id"] = "wrong"
        with self.assertRaisesRegex(ValueError, "assignment identity"):
            self.run_measure(trace)


if __name__ == "__main__":
    unittest.main()
