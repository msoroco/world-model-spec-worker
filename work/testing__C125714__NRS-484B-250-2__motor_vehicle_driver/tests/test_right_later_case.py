import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / 'cases/source_verified_other_right_later'


class RightLaterCaseTests(unittest.TestCase):
    def test_ego_first_control_and_source_order(self):
        construction = json.loads((CASE / 'construction.json').read_text())
        files = {item['path']: item['content'] for item in construction['files']}
        config = json.loads(files['config.json'])
        self.assertEqual((config['ego_release_frame'], config['other_release_frame']), (20, 40))
        contract = json.loads((CASE / 'measurement-contract.json').read_text())
        self.assertEqual({row['disposition_index'] for row in contract['requirements']}, {0, 1, 2})
        self.assertEqual(contract['negative']['remove'], ['crossing_history.jsonl'])
        namespace = {'__name__': 'right_later_control'}
        exec(compile(files['yield_controller.py'], 'yield_controller.py', 'exec'), namespace)
        hold = namespace['later_entry_hold']
        self.assertEqual(hold(19, 20, False, False), (True, False))
        self.assertEqual(hold(20, 20, False, False), (False, False))
        self.assertEqual(hold(45, 20, True, False), (False, True))
        with self.assertRaisesRegex(ValueError, 'Boolean'):
            hold(20, 20, 1, False)

        diagnostic = json.loads((CASE / 'diagnostic.json').read_text())
        history = [json.loads(line) for line in diagnostic['files']['crossing_history.jsonl'].splitlines()]
        controls = [json.loads(line) for line in diagnostic['files']['controller_history.jsonl'].splitlines()]
        self.assertEqual(len(history), 60)
        self.assertTrue(all(row['other']['position_xy_m'] == [0, -8] for row in history[:40]))
        self.assertTrue(all(row['ego_control']['hold'] for row in controls[:20]))
        self.assertTrue(all(not row['ego_control']['hold'] for row in controls[20:]))
        self.assertFalse(controls[40]['other_entered_once'])
        self.assertTrue(controls[45]['other_entered_once'])


if __name__ == '__main__':
    unittest.main()
