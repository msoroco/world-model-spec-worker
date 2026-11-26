"""Exact selected judgment stations request distinct source-bound controls."""

import json
from pathlib import Path
import unittest

from school_lane_controls import selected_schedule


ROOT = Path(__file__).resolve().parents[1]


class SelectedSweepTests(unittest.TestCase):
    def test_all_frozen_points(self):
        proposal = json.loads((ROOT / "proposals/cases.json").read_text())
        points = [case for case in proposal["cases"] if case.get("sweep_id")]
        self.assertEqual(len(points), 6)
        for case in points:
            schedule = selected_schedule(case["case_id"], 70.0)
            self.assertEqual(schedule["case_id"], case["case_id"])
            self.assertEqual(schedule["sweep_point"], case["sweep_point"])
            axis, value = next(iter(case["sweep_point"].items()))
            frame = "warning_on_from_frame" if axis == "warning_onset_s" else "release_frame"
            self.assertEqual(schedule[frame], int(value * 20))

    def test_unselected_case_rejected(self):
        with self.assertRaises(ValueError):
            selected_schedule("fake__child_warning_onset-0000", 70.0)


if __name__ == "__main__":
    unittest.main()
