import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from officer_motion import measure
from officer_scene import CASES
from test_officer_scene import site


def history(case):
    rows = []
    for i in range(900):
        station = -10 + i * .1
        phase = case.other_phase if i <= 500 else "cleared"
        rows.append({"frame": 1000 + i, "time_s": 8 + i / 20,
                     "state": {"ego": {"id": "ego", "speed_mps": 2.0,
                                       "leading_station_m": station,
                                       "across_or_within": i >= 100},
                               "other": {"id": "other", "phase": phase,
                                         "center_station_m": case.other_station_m},
                               "officer": {"id": "officer", "controls_traffic": True,
                                           "visible": True, "directive": case.officer_directive},
                               "officer_directive": case.officer_directive}})
    return rows


class OfficerMotionTest(unittest.TestCase):
    def test_all_selected_cases_use_original_entry(self):
        for case in CASES:
            with self.subTest(case=case.suffix):
                result = measure(history(case), site(), case)
                self.assertEqual(result["observed_other_phase_at_entry"], case.other_phase)
                self.assertEqual(result["observed_officer_directive_at_entry"],
                                 case.officer_directive)
                self.assertIsNone(result["legal_judgment"])

    def test_missing_officer_visibility_rejected(self):
        rows = history(CASES[0])
        rows[101]["state"]["officer"]["visible"] = False
        with self.assertRaisesRegex(ValueError, "visibility"):
            measure(rows, site(), CASES[0])

    def test_requested_phase_not_substituted_for_observation(self):
        rows = history(CASES[0])
        rows[100]["state"]["other"]["phase"] = "approaching"
        with self.assertRaisesRegex(ValueError, "physically realized"):
            measure(rows, site(), CASES[0])

    def test_frame_gap_rejected(self):
        rows = history(CASES[0])
        rows[55]["frame"] += 1
        with self.assertRaisesRegex(ValueError, "gap"):
            measure(rows, site(), CASES[0])


if __name__ == "__main__":
    unittest.main()
