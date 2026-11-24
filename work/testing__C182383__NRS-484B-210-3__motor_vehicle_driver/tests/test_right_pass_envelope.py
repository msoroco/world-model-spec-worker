import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from right_pass_envelope import ASSIGNMENT, measure


class RightPassTests(unittest.TestCase):
    def packet(self):
        return {"assignment_id": ASSIGNMENT, "original_trace_id": "synthetic-test-only",
                "ego_actor_id": "ego", "overtaken_actor_id": "car-b",
                "frames": [{"time_s": i * 0.05, "ego_left_m": 3.0, "ego_right_m": 5.0,
                            "overtaken_left_m": 0.0, "overtaken_right_m": 2.8,
                            "paved_left_m": -1.0, "paved_right_m": 4.5,
                            "longitudinal_overlap": i == 1,
                            "ego_ahead_of_overtaken": i == 2} for i in range(3)]}

    def run_measure(self, packet):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            p = Path(d) / "original.json"
            p.write_text(json.dumps(packet), encoding="utf-8")
            return measure(p)

    def test_off_pavement_and_no_body_fit(self):
        r = self.run_measure(self.packet())
        self.assertTrue(r["actual_off_pavement_observed"])
        self.assertTrue(r["zero_clearance_paved_fit_impossible_observed"])

    def test_off_pavement_not_same_as_required(self):
        p = self.packet()
        p["frames"][1]["paved_right_m"] = 7.0
        p["frames"][1]["ego_left_m"] = 5.0
        p["frames"][1]["ego_right_m"] = 7.5
        r = self.run_measure(p)
        self.assertTrue(r["actual_off_pavement_observed"])
        self.assertFalse(r["zero_clearance_paved_fit_impossible_observed"])

    def test_no_right_side_overlap_rejected(self):
        p = self.packet()
        p["frames"][1]["ego_left_m"] = 2.0
        with self.assertRaisesRegex(ValueError, "right-side overlap"):
            self.run_measure(p)

    def test_incomplete_pass_rejected(self):
        p = self.packet()
        p["frames"][-1]["ego_ahead_of_overtaken"] = False
        with self.assertRaisesRegex(ValueError, "complete right-side"):
            self.run_measure(p)

    def test_missing_paved_edge_rejected(self):
        p = self.packet()
        del p["frames"][1]["paved_right_m"]
        with self.assertRaisesRegex(ValueError, "paved_right_m"):
            self.run_measure(p)


if __name__ == "__main__":
    unittest.main()
