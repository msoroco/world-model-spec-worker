from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_exposure_probe import check_config


class ExposureProbeConfigTests(unittest.TestCase):
    def test_exact_probe_identity(self):
        config = {'selected_case_id': 'heldout__C136539__NRS-484B-600-1b__motor_vehicle_driver__slow_person_exposure',
                  'law_id': 'NRS-484B-600-1b', 'cell_id': 'C136539',
                  'actor': 'motor_vehicle_driver', 'rate_hz': 20, 'frames': 80,
                  'requested_speed_mps': 2, 'construction_probe_only': True}
        check_config(config)
        with self.assertRaisesRegex(ValueError, 'masquerade'):
            check_config(dict(config, construction_probe_only=False))
        with self.assertRaisesRegex(ValueError, 'identity'):
            check_config(dict(config, cell_id='wrong'))
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            check_config(dict(config, selected_case_id='wrong'))


if __name__ == '__main__':
    unittest.main()
