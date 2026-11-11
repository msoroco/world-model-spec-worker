import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_left_excursion_probe import check_config


class LeftExcursionProbeConfigTests(unittest.TestCase):
    def test_exact_case_and_controller_bound(self):
        config = json.loads((ROOT / 'left-probe-config.json').read_text())
        check_config(config)
        config['requested_lane_fraction'] = .4
        with self.assertRaisesRegex(ValueError, 'fraction differs'):
            check_config(config)
        config['requested_lane_fraction'] = .75
        config['selected_case_id'] += '-wrong'
        with self.assertRaisesRegex(ValueError, 'Unknown left-excursion'):
            check_config(config)


if __name__ == '__main__':
    unittest.main()
