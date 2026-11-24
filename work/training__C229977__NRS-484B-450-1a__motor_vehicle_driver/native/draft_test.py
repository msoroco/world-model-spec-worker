import json
from pathlib import Path
import unittest
from runner import check, request

class Draft(unittest.TestCase):
    def test_exact_construction(self):
        cfg = json.loads(Path("config.json").read_text())
        self.assertEqual(check(cfg)["frames"], 600)
        target = -5.0 if cfg["case_id"].endswith("probe_2") else -1.75
        self.assertEqual(request(200, cfg["case_id"])["target_lateral_m"], target)
    def test_wrong_identity_rejected(self):
        cfg = json.loads(Path("config.json").read_text())
        cfg["cell_id"] = "C0"
        with self.assertRaisesRegex(ValueError, "frozen identity"):
            check(cfg)
        with self.assertRaisesRegex(ValueError, "600-frame"):
            request(600, cfg["case_id"])
if __name__ == "__main__":
    unittest.main()
