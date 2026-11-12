import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_passing_probe import check_config


class PassingProbeConfigTests(unittest.TestCase):
    def test_exact_case_and_controller_bound(self):
        config = json.loads((ROOT / 'passing-probe-config.json').read_text())
        check_config(config)
        config['requested_lane_fraction'] = .4
        with self.assertRaisesRegex(ValueError, 'fraction differs'):
            check_config(config)
        config['requested_lane_fraction'] = .75
        config['selected_case_id'] += '-wrong'
        with self.assertRaisesRegex(ValueError, 'Unknown passing'):
            check_config(config)


if __name__ == '__main__':
    unittest.main()
