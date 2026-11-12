import json
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('no_hazard_runner', ROOT / 'cases/no_hazard/runner.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
check_config, guarded_lead_speed = module.check_config, module.guarded_lead_speed


class GuardTests(unittest.TestCase):
    def test_physical_response_and_case_binding(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / 'cases/no_hazard/config.json').read_text())
        self.assertEqual(check_config(config), config['selected_case_id'])
        self.assertEqual(guarded_lead_speed(0, 10, 20, 8), 20 - 5.5/3)
        self.assertEqual(guarded_lead_speed(0, 45, 20, 8), 8)
        self.assertGreater(guarded_lead_speed(0, 10, 20, 8),
                           guarded_lead_speed(0, 20, 20, 8))
        config['engineering'].pop('hazard_guard_ttc_s')
        with self.assertRaisesRegex(ValueError, 'physical lead response guard'):
            check_config(config)


if __name__ == '__main__':
    unittest.main()
