"""A selected school-lane run must keep exact capture and source gates."""

import unittest

from package_contract import ACTOR, CAMERAS, CELL, LAW
from runner import check_config, selected_ids


class RunnerContractTests(unittest.TestCase):
    def test_every_selected_case(self):
        self.assertEqual(len(selected_ids()), 15)
        for case_id in selected_ids():
            config = {"law_id": LAW, "cell_id": CELL, "actor": ACTOR,
                      "selected_case_id": case_id, "diagnostic_only": True,
                      "rate_hz": 20, "duration_s": 45, "cameras": CAMERAS}
            self.assertTrue(check_config(config))

    def test_bad_capture_rejected(self):
        case_id = next(iter(selected_ids()))
        config = {"law_id": LAW, "cell_id": CELL, "actor": ACTOR,
                  "selected_case_id": case_id, "diagnostic_only": True,
                  "rate_hz": 10, "duration_s": 45, "cameras": CAMERAS}
        with self.assertRaisesRegex(ValueError, "capture contract"):
            check_config(config)


if __name__ == "__main__":
    unittest.main()
