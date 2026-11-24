import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("signal_controller", ROOT / "signal_controller.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SignalControllerTest(unittest.TestCase):
    def test_numeric_triple_targets(self):
        self.assertFalse(MODULE.request_right_signal("short80", 90 * .3048))
        self.assertTrue(MODULE.request_right_signal("short80", 80 * .3048))
        self.assertTrue(MODULE.request_right_signal("continuous100", 100 * .3048))
        self.assertTrue(MODULE.request_right_signal("above101", 101 * .3048))

    def test_interruption_and_weather(self):
        self.assertTrue(MODULE.request_right_signal("interrupted", 70 * .3048))
        self.assertFalse(MODULE.request_right_signal("interrupted", 60 * .3048))
        self.assertTrue(MODULE.request_right_signal("interrupted", 50 * .3048))
        self.assertEqual(MODULE.request_right_signal("rain", 75 * .3048),
                         MODULE.request_right_signal("continuous100", 75 * .3048))

    def test_reject_bad_values(self):
        with self.assertRaises(ValueError):
            MODULE.request_right_signal("none", 0)
        with self.assertRaises(ValueError):
            MODULE.request_right_signal("short80", float("nan"))
        with self.assertRaises(ValueError):
            MODULE.request_right_signal("continuous100", 10, speed_m_s=-1)

    def test_one_sample_lead_preserves_measured_boundary(self):
        # At 20 Hz and 8 m/s each saved sample is 0.4 m apart. An exact
        # 100-foot request would first be retained inside the 100-foot mark.
        remaining = [40 - .4 * index for index in range(101)]
        starts = {}
        for case in ("short80", "continuous100", "above101", "interrupted", "rain"):
            active = [MODULE.request_right_signal(case, distance, speed_m_s=8)
                      for distance in remaining]
            first = 100
            while first > 0 and active[first - 1]:
                first -= 1
            starts[case] = remaining[first] / MODULE.METRES_PER_FOOT
        self.assertLess(starts["short80"], 100)
        self.assertGreaterEqual(starts["continuous100"], 100)
        self.assertGreater(starts["above101"], 101)
        self.assertLess(starts["interrupted"], 100)
        self.assertEqual(starts["rain"], starts["continuous100"])


if __name__ == "__main__":
    unittest.main()
