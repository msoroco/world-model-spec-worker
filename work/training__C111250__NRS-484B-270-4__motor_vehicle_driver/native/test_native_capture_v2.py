import unittest

from native_capture_v2 import check


class NativeCaptureContractTest(unittest.TestCase):
    def test_both_exact_case_routes_use_four_view_profile(self):
        for suffix in ("outside_cycle_lane", "within_cycle_lane"):
            proof = check({"case_id": "C111250__" + suffix,
                           "case_suffix": suffix, "candidate_id": "primary",
                           "rate_hz": 20, "duration_s": 30})
            self.assertEqual(proof["frames"], 600)
            self.assertEqual(proof["camera_sizes"], [[1920, 1080],
                [1280, 720], [1280, 720], [1280, 720]])
            self.assertFalse(proof["physical_or_legal_success_claimed"])

    def test_unprepared_camera_placement_and_duration_fail(self):
        config = {"case_id": "C111250__outside_cycle_lane",
                  "case_suffix": "outside_cycle_lane", "candidate_id": "primary",
                  "camera_lateral_shift_m": 9,
                  "rate_hz": 20, "duration_s": 30}
        with self.assertRaisesRegex(ValueError, "camera placement"):
            check(config)
        config["camera_lateral_shift_m"] = 0
        config["duration_s"] = 29
        with self.assertRaisesRegex(ValueError, "duration"):
            check(config)


if __name__ == "__main__":
    unittest.main()
