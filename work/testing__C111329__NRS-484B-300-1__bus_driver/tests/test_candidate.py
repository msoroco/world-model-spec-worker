"""Guard the exact Native fallback invariant and physical knob location."""
import json
from pathlib import Path
import unittest

from package_spec import CASES


HERE = Path(__file__).resolve().parents[1]


def config(path):
    construction = json.loads(path.read_text())
    return json.loads(next(item['content'] for item in construction['files']
                           if item['path'] == 'config.json'))


class CandidateTests(unittest.TestCase):
    def test_fallback_keeps_exact_case_and_changes_top_level_controller(self):
        for name, *_ in CASES:
            with self.subTest(case=name):
                base = HERE / 'cases' / name
                primary = config(base / 'construction.json')
                fallback = config(base / 'fallback1/construction.json')
                self.assertEqual(primary['case'], fallback['case'])
                self.assertEqual(primary['selected_case_id'], fallback['selected_case_id'])
                self.assertNotEqual(primary['control_profile'], fallback['control_profile'])


if __name__ == '__main__':
    unittest.main()
