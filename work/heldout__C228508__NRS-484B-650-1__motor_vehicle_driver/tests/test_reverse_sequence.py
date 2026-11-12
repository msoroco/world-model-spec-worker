import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('reverse_sequence_runner', ROOT/'cases/reverse_sequence/runner.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReverseSequenceTests(unittest.TestCase):
    def test_late_speed_request_and_identity(self):
        config = json.loads((ROOT/'cases/reverse_sequence/config.json').read_text())
        self.assertEqual(module.check_config(config), config['selected_case_id'])
        self.assertEqual(module.requested_ego_speed(24, 180), 18)
        self.assertEqual(module.requested_ego_speed(24, 659.9), 18)
        self.assertEqual(module.requested_ego_speed(24, 660), 24)
        config['engineering'].pop('speed_phase_start_station_m')
        with self.assertRaisesRegex(ValueError, 'late physical speed request'):
            module.check_config(config)


if __name__ == '__main__':
    unittest.main()
