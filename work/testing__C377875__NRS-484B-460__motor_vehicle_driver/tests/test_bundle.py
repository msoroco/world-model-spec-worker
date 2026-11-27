import json
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from angle_native import control
from angle_site import ASSIGNMENT


class ExactBundleTests(unittest.TestCase):
    def test_exact_identity_and_selected_case(self):
        cfg = json.loads((ROOT / "config.json").read_text())
        self.assertEqual(cfg["assignment_id"], ASSIGNMENT)
        self.assertEqual(cfg["law_id"], "NRS-484B-460")
        self.assertEqual(cfg["cell_id"], "C377875")
        self.assertIn(cfg["selected_case_id"], cfg["supported_case_ids"])
        self.assertEqual(cfg["rate_hz"], 20)
        self.assertEqual(cfg["duration_s"], 30)

    def test_controller_realizes_approach_and_halt_phases(self):
        cfg = json.loads((ROOT / "config.json").read_text())
        activity = cfg["case"]["activity_request"]
        command, state, reached = control([0, 0], 0, 2, [10, 0], 45, False, 0, activity, 600)
        self.assertEqual(state, "approach")
        self.assertFalse(reached)
        command, state, reached = control([10, 0], 45, 0, [10, 0], 45, True, 0, activity, 600)
        self.assertEqual(state, "hold")
        self.assertTrue(reached)
        self.assertEqual(command["brake"], 1)


if __name__ == "__main__":
    unittest.main()
