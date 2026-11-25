import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import runner
from caravan_capture import validate_site


class Offline(unittest.TestCase):
    def test_all_exact_cases_and_unreviewed_site_guard(self):
        config = json.loads((ROOT / 'config.json').read_text())
        self.assertEqual(set(runner.MODULES), set(config['supported_case_ids']))
        self.assertEqual((config['duration_s'], config['rate_hz']), (45, 20))
        self.assertEqual(len(config['cameras']), 4)
        packet = json.loads((ROOT / 'site_packet.json').read_text())
        self.assertEqual(packet['site_review_status'], 'diagnostic_unreviewed')
        with self.assertRaisesRegex(ValueError, 'Reviewed Native caravan site required'):
            validate_site(packet, ROOT, packet['native_map_id'])


if __name__ == '__main__':
    unittest.main()
