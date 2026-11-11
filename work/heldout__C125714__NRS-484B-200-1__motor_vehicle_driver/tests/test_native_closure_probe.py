from pathlib import Path
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_closure_probe import check_config


class ClosureProbeTests(unittest.TestCase):
    def test_exact_case_and_sourced_map_reference_guard(self):
        config = json.loads((ROOT / 'closure-probe-config.json').read_text())
        check_config(config)
        with self.assertRaisesRegex(ValueError, 'Unknown right-half closure'):
            check_config({**config, 'selected_case_id': 'another-case'})
        with self.assertRaisesRegex(ValueError, 'map source required'):
            check_config({**config, 'median_opening_reference': None})
        with self.assertRaisesRegex(ValueError, 'masquerade'):
            check_config({**config, 'construction_probe_only': False})


if __name__ == '__main__':
    unittest.main()
