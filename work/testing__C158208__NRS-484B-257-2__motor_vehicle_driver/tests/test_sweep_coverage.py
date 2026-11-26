import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from sweep_coverage import ASSIGNMENT, classify


def sample(station, minimum_speed, mean_speed):
    return {"counterpart_center_station_first_m": station,
            "ego_speed_min_peak_to_stop_reference_mps": minimum_speed,
            "ego_speed_mean_full_body_overlap_to_clear_mps": mean_speed}


class SweepCoverageTests(unittest.TestCase):
    def test_all_feasible_bins_and_zero_width_interior(self):
        values = {
            ASSIGNMENT + "__occupied_response": sample(0.02, 0.004, 1.0),
            ASSIGNMENT + "__approaching_near_response": sample(10.0, 0.008087591730665596, 3.0),
            ASSIGNMENT + "__approaching_far_response": sample(23.0, 0.1, 5.0),
        }
        report = classify(values)
        self.assertEqual(len(report["ranges"]), 9)
        for index, row in enumerate(report["ranges"]):
            self.assertTrue(row["witnesses"]["below"])
            self.assertTrue(row["witnesses"]["above"])
            if index in (1, 4, 7):
                self.assertFalse(row["strict_interior_possible"])
                self.assertFalse(row["witnesses"]["inside"])
            else:
                self.assertTrue(row["witnesses"]["inside"])
            self.assertEqual(row["missing"], [])

    def test_missing_or_invalid_original_value_rejected(self):
        case = ASSIGNMENT + "__occupied_response"
        with self.assertRaisesRegex(ValueError, "missing finite original"):
            classify({case: sample(0.02, 0.004, float("nan"))})
        with self.assertRaisesRegex(ValueError, "case outside exact assignment"):
            classify({"wrong_case": sample(0.02, 0.004, 1.0)})


if __name__ == "__main__":
    unittest.main()
