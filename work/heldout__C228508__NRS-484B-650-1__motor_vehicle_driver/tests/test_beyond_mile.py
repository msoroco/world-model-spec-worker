import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('beyond_mile_construction', ROOT/'cases/beyond_mile/following_construction.py')
module = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class BeyondMileTests(unittest.TestCase):
    def test_physical_phase_separation(self):
        self.assertTrue(module.validate_schedule())
        first, second = [p for p in module.PHASES if 'closing_request' in p.label]
        self.assertGreater(second.start_m - first.end_m, 1609.344)
        self.assertEqual(module.phase_at(1900).label, 'separate_encounters')
        self.assertEqual(module.phase_at(2000).label, 'second_closing_request')
        altered = list(module.PHASES)
        altered[2] = module.Phase(300, 1850, 22, 18, 'separate_encounters')
        altered[3] = module.Phase(1850, 2070, 24, 11, 'second_closing_request')
        with self.assertRaisesRegex(ValueError, 'exceed one mile'):
            module.validate_schedule(tuple(altered))


if __name__ == '__main__':
    unittest.main()
