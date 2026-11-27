"""Controlled comparison checks for the statutory 30 minute threshold."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "native"))
from duration_policy import RATE_HZ, TARGETS, TOTAL_FRAMES, comparison_invariants, request, stop_frame


ASSIGNMENT = "training__C229398__LVMC-11-52-300__nonmotor_vehicle_operator"


class DurationPolicyTest(unittest.TestCase):
    def configs(self):
        common = {"law_id": "LVMC-11-52-300", "cell_id": "C229398",
                  "actor": "nonmotor_vehicle_operator", "rate_hz": RATE_HZ,
                  "capture_frames": TOTAL_FRAMES,
                  "duration_s": TOTAL_FRAMES / RATE_HZ,
                  "road_sha256": "same road", "prototype_blueprint": "nonmotor prototype",
                  "cameras": ["overview", "approach", "reference_corner", "driver_reference"],
                  "weather": "same", "parking_target_xy_m": [40.0, -1.75],
                  "source_context_policy": "original reviewed source required"}
        return {suffix: dict(common, case_id=ASSIGNMENT + "__" + suffix,
                             parking_stop_frame=stop_frame(ASSIGNMENT + "__" + suffix))
                for suffix in TARGETS}

    def test_exact_bracket_and_common_capture(self):
        configs = self.configs()
        self.assertTrue(comparison_invariants(configs)["passed"])
        self.assertEqual([stop_frame(configs[s]["case_id"]) for s in TARGETS],
                         [82, 62, 42])
        for suffix, expected in TARGETS.items():
            case_id = configs[suffix]["case_id"]
            self.assertEqual(request(case_id, TOTAL_FRAMES - 1)[
                             "requested_stationary_duration_s"], expected)
            self.assertEqual(request(case_id, stop_frame(case_id) - 1)["phase"],
                             "approach")
            self.assertEqual(request(case_id, stop_frame(case_id))["phase"],
                             "parking_request")

    def test_comparison_tamper_rejected(self):
        configs = self.configs()
        configs["at_30"]["cameras"] = ["overview"]
        with self.assertRaisesRegex(ValueError, "held condition"):
            comparison_invariants(configs)
        configs = self.configs()
        configs["above_30"]["parking_stop_frame"] += 1
        with self.assertRaisesRegex(ValueError, "stop frame"):
            comparison_invariants(configs)

    def test_missing_case_or_outside_frame_rejected(self):
        configs = self.configs()
        del configs["at_30"]
        with self.assertRaisesRegex(ValueError, "triple required"):
            comparison_invariants(configs)
        with self.assertRaisesRegex(ValueError, "outside synchronized"):
            request(ASSIGNMENT + "__above_30", TOTAL_FRAMES)


if __name__ == "__main__":
    unittest.main()
