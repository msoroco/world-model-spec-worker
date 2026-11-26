import json
import unittest
from pathlib import Path
from runner import check
from construction import check_comparisons
from control import command

ROOT = Path(__file__).resolve().parents[1]


class ExactCase(unittest.TestCase):
    def test_construction_and_controller(self):
        config = json.loads((ROOT / 'config.json').read_text())
        self.assertEqual(config['case_suffix'], 'probe_2')
        result = check(config)
        self.assertEqual(result['frames'], 600)
        self.assertEqual(len(result['camera_views']), 4)
        self.assertFalse(result['native_executed'])
        self.assertEqual(len(check_comparisons()['case_ids']), 3)
        self.assertEqual(command(config['case_suffix'], 599)['frame'], 599)
        with self.assertRaisesRegex(ValueError, 'outside 600-frame'):
            command(config['case_suffix'], 600)


if __name__ == '__main__':
    unittest.main()
