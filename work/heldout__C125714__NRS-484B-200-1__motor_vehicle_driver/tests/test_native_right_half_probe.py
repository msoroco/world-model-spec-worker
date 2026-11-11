from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_right_half_probe import check_config


class ProbeConfigTests(unittest.TestCase):
    def test_exact_identity_and_probe_flag(self):
        config = {'selected_case_id': 'heldout__C125714__NRS-484B-200-1__motor_vehicle_driver__baseline_right_east',
                  'law_id': 'NRS-484B-200-1', 'cell_id': 'C125714',
                  'actor': 'motor_vehicle_driver', 'rate_hz': 20, 'frames': 80,
                  'travel_direction': 'east',
                  'construction_probe_only': True}
        check_config(config)
        with self.assertRaisesRegex(ValueError, 'masquerade'):
            check_config(dict(config, construction_probe_only=False))
        with self.assertRaisesRegex(ValueError, 'identity'):
            check_config(dict(config, law_id='wrong'))
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            check_config(dict(config, selected_case_id='wrong'))
        with self.assertRaisesRegex(ValueError, 'eastward'):
            check_config(dict(config, travel_direction='west'))


if __name__ == '__main__':
    unittest.main()
