import json
import unittest
from pathlib import Path
import road
import runner
from case_specs import CASES, target_x

class BundleTest(unittest.TestCase):
    def test_exact_zone_and_capture(self):
        cfg = json.loads(Path("config.json").read_text())
        self.assertTrue(road.check()["passed"])
        self.assertTrue(runner.check()["passed"])
        self.assertEqual(cfg["selected_case_id"], cfg["case_id"])
        self.assertEqual(len(cfg["cameras"]), 4)
        self.assertEqual(cfg["frames"], 600)
        self.assertEqual(cfg["rate_hz"], 20)
        self.assertIn(cfg["case_id"][len(cfg["assignment_id"]) + 2:], CASES)

    def test_boundary_and_candidate_invariants(self):
        self.assertLess(target_x("start_35"), target_x("start_30"))
        self.assertLess(target_x("end_30"), target_x("end_35"))
        cfg = json.loads(Path("config.json").read_text())
        self.assertIn(cfg["brake_lead_seconds"], (1.4, 2.0))
