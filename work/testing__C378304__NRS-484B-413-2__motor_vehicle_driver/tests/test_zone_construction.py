import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from zone_construction import build_xodr, validate_xodr


class ZoneConstructionTests(unittest.TestCase):
    def test_authored_right_turn_has_zone_objects_and_long_approach(self):
        report = validate_xodr(build_xodr())
        self.assertGreaterEqual(report["approach_length_m"], 91.44)
        self.assertLess(report["freight_zone_sign_s_m"], report["freight_zone_bay_s_m"])
        self.assertFalse(report["native_rendering_confirmed"])

    def test_missing_zone_sign_rejected(self):
        with self.assertRaisesRegex(ValueError, "sign and bay"):
            validate_xodr(build_xodr().replace("freight_loading_zone_sign", "unknown"))


if __name__ == "__main__":
    unittest.main()
