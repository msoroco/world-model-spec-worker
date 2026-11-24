import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from continuous_signal import ASSIGNMENT, measure


class ContinuousSignalTests(unittest.TestCase):
    def packet(self):
        return {"assignment_id": ASSIGNMENT, "original_trace_id": "synthetic-test-only",
                "district_type": "business", "district_source_id": "district-a",
                "turn_direction": "right",
                "frames": [{"time_s": i * 0.05, "x_m": float(i * 10), "y_m": 0.0,
                            "right_signal": True, "left_signal": False,
                            "course_change_begun": i >= 4} for i in range(6)]}

    def run_measure(self, packet):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            p = Path(d) / "original.json"
            p.write_text(json.dumps(packet), encoding="utf-8")
            return measure(p)

    def test_business_right_sufficient(self):
        r = self.run_measure(self.packet())
        self.assertEqual(r["continuous_signal_distance_m"], 40)
        self.assertEqual(r["statutory_distance_m"], 30.48)
        self.assertTrue(r["continuous_signal_distance_sufficient"])

    def test_interruption_resets_continuity(self):
        p = self.packet()
        p["frames"][2]["right_signal"] = False
        r = self.run_measure(p)
        self.assertEqual(r["continuous_signal_onset_index"], 3)
        self.assertFalse(r["continuous_signal_distance_sufficient"])

    def test_other_area_three_hundred_feet(self):
        p = self.packet()
        p["district_type"] = "other"
        r = self.run_measure(p)
        self.assertEqual(r["statutory_distance_m"], 91.44)
        self.assertFalse(r["continuous_signal_distance_sufficient"])

    def test_wrong_signal_rejected_as_continuous(self):
        p = self.packet()
        p["frames"][4]["left_signal"] = True
        r = self.run_measure(p)
        self.assertIsNone(r["continuous_signal_onset_index"])

    def test_missing_district_source_rejected(self):
        p = self.packet()
        del p["district_source_id"]
        with self.assertRaisesRegex(ValueError, "district"):
            self.run_measure(p)


if __name__ == "__main__":
    unittest.main()
