import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_construction_probe import check_config


class ProbeConfigTests(unittest.TestCase):
    def test_exact_identity_and_probe_flag(self):
        config = {"selected_case_id": "heldout__C147331__LVMC-11-18-030-B__motor_vehicle_driver__within_marked_lane",
                  "law_id": "LVMC-11-18-030-B", "cell_id": "C147331",
                  "actor": "motor_vehicle_driver", "rate_hz": 20, "frames": 160,
                  "construction_probe_only": True}
        self.assertEqual(check_config(config), "within_marked_lane")
        with self.assertRaisesRegex(ValueError, "masquerade"):
            check_config(dict(config, construction_probe_only=False))
        with self.assertRaisesRegex(ValueError, "law/cell/actor"):
            check_config(dict(config, law_id="other"))
        with self.assertRaisesRegex(ValueError, "Unknown exact"):
            check_config(dict(config, selected_case_id="other"))


if __name__ == "__main__":
    unittest.main()
