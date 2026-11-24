import json
from pathlib import Path
import unittest
from runner import check, request


class Draft(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path("config.json").read_text())

    def test_exact_contract(self):
        result = check(self.config)
        self.assertEqual(result["frames"], 600)
        expected = 320 if self.config["case_id"].endswith("probe_01") else 140
        self.assertEqual(request(0, self.config["case_id"])["pedestrian_departure_frame"], expected)
        self.assertEqual(request(expected, self.config["case_id"])["pedestrian_target_speed_mps"], 1.2)

    def test_wrong_identity_and_frame_rejected(self):
        bad = dict(self.config, cell_id="C0")
        with self.assertRaisesRegex(ValueError, "frozen identity"):
            check(bad)
        with self.assertRaisesRegex(ValueError, "600-frame"):
            request(600, self.config["case_id"])


if __name__ == "__main__":
    unittest.main()
