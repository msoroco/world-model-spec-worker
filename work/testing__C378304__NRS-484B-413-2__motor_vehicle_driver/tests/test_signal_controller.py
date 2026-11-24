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


if __name__ == "__main__":
    unittest.main()
