import json
from pathlib import Path
import unittest

import runner


class TestSelectedRiderArmCase(unittest.TestCase):
    def test_exact_case_and_capture_profile(self):
        config = json.loads((Path(__file__).resolve().parents[1] / "config.json").read_text())
        checked = runner.check(config["selected_case_id"])
        self.assertEqual(checked["frames"], 600)
        self.assertEqual(checked["rate_hz"], 20)
        self.assertEqual(checked["camera_names"], ["overview", "approach",
            "reference_corner", "driver_reference"])
        self.assertEqual(config["law_id"], "NRS-484B-769")
        self.assertEqual(config["cell_id"], "C229831")


if __name__ == "__main__":
    unittest.main()
