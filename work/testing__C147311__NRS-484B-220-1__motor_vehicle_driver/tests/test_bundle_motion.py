"""Exact selected route controls the diagnostic motion direction."""
import copy
import json
from pathlib import Path
import sys
import unittest


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from one_way_direction import CASES
from runner import check_config


class BundleMotionTests(unittest.TestCase):
    def test_selected_direction_and_reverse_motion_are_bound(self):
        for case in CASES:
            with self.subTest(case=case.name):
                path = (HERE / 'construction.json' if case.name == 'designated'
                        else HERE / 'cases' / case.name / 'construction.json')
                construction = json.loads(path.read_text(encoding='utf-8'))
                config_entry = next(row for row in construction['files']
                                    if row['path'] == 'config.json')
                config = json.loads(config_entry['content'])
                self.assertEqual(config['case']['direction'], case.direction)
                self.assertIs(config['reverse_motion'], case.direction == 'opposed')
                self.assertTrue(check_config(config))
                altered = copy.deepcopy(config)
                altered['reverse_motion'] = not config['reverse_motion']
                with self.assertRaisesRegex(ValueError, 'physical motion direction'):
                    check_config(altered)
                altered = copy.deepcopy(config)
                altered['case']['direction'] = ('opposed' if case.direction == 'designated'
                                               else 'designated')
                with self.assertRaisesRegex(ValueError, 'selected variant'):
                    check_config(altered)


if __name__ == '__main__':
    unittest.main()
