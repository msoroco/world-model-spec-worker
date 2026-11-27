import unittest

from runner import AID, CAMERAS, CASES, check


class TestRunner(unittest.TestCase):
    def test_all_three_exact_case_requests(self):
        self.assertEqual(set(CASES.values()), {"right_horizontal", "left_upward", "none"})
        for case_id in CASES:
            status = check(case_id)
            self.assertEqual(status["case_id"], case_id)
            self.assertEqual(status["frames"], 600)
            self.assertFalse(status["native_imported"])
            self.assertFalse(status["physical_acceptance_claimed"])
        self.assertEqual([(row[0], row[1], row[2]) for row in CAMERAS],
                         [("overview", 1920, 1080), ("approach", 1280, 720),
                          ("reference_corner", 1280, 720),
                          ("driver_reference", 1280, 720)])

    def test_rejects_unknown_case(self):
        with self.assertRaisesRegex(ValueError, "Unknown exact"):
            check(AID + "__probe_d")


if __name__ == "__main__":
    unittest.main()
