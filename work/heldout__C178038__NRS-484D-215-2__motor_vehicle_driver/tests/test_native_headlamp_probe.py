from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_headlamp_probe import CASE_ID, check_config


class NativeProbeTests(unittest.TestCase):
    def test_exact_probe_config(self):
        config = {'selected_case_id': CASE_ID, 'law_id': 'NRS-484D-215-2',
                  'cell_id': 'C178038', 'actor': 'motor_vehicle_driver',
                  'rate_hz': 20, 'frames': 80, 'requested_gap_ft': 299,
                  'construction_probe_only': True}
        check_config(config)
        for change in ({'requested_gap_ft': 300}, {'construction_probe_only': False},
                       {'selected_case_id': CASE_ID.replace('299', '301')}):
            wrong = {**config, **change}
            with self.assertRaises(ValueError):
                check_config(wrong)


if __name__ == '__main__':
    unittest.main()
