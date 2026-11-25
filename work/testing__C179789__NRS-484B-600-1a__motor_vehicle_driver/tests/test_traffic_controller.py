import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("traffic_controller", ROOT / "traffic_controller.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TrafficControllerTests(unittest.TestCase):
    def test_lead_speed_and_ego_gap(self):
        lead = MODULE.LongitudinalController(7)
        ego = MODULE.LongitudinalController(10)
        self.assertGreater(lead.step(4)["throttle"], 0)
        self.assertEqual(lead.step(9)["throttle"], 0)
        self.assertGreater(ego.step(6, lead_body_gap_m=20)["throttle"], 0)
        self.assertEqual(ego.step(8, lead_body_gap_m=6)["gap_guard"], "approach")
        self.assertGreater(ego.step(8, lead_body_gap_m=6)["brake"], 0)
        self.assertEqual(ego.step(8, lead_body_gap_m=3)["brake"], 1)

    def test_invalid_observations_rejected(self):
        controller = MODULE.LongitudinalController(8)
        with self.assertRaisesRegex(ValueError, "observed speed"):
            controller.step(float("nan"))
        with self.assertRaisesRegex(ValueError, "observed body gap"):
            controller.step(4, lead_body_gap_m=-1)
        with self.assertRaisesRegex(ValueError, "Approach gap"):
            MODULE.LongitudinalController(8, minimum_body_gap_m=10, approach_body_gap_m=8)


if __name__ == "__main__":
    unittest.main()
