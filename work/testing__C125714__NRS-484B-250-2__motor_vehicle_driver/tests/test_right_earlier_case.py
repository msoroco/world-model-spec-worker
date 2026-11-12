import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / 'cases/source_verified_other_right_earlier'


class RightEarlierCaseTests(unittest.TestCase):
    def test_release_and_controller_occupancy(self):
        construction = json.loads((CASE / 'construction.json').read_text())
        files = {item['path']: item['content'] for item in construction['files']}
        config = json.loads(files['config.json'])
        self.assertEqual(config['other_release_frame'], 0)

        diagnostic = json.loads((CASE / 'diagnostic.json').read_text())
        controls = [json.loads(line) for line in
                    diagnostic['files']['controller_history.jsonl'].splitlines()]
        self.assertEqual(len(controls), 60)
        self.assertFalse(controls[0]['other_entered_once'])
        self.assertTrue(any(row['other_inside_before_tick'] for row in controls))
        self.assertTrue(controls[-1]['other_entered_once'])
        self.assertFalse(controls[-1]['other_inside_before_tick'])


if __name__ == '__main__':
    unittest.main()
