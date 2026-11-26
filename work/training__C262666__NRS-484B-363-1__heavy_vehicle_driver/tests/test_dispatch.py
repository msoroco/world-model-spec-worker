import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
import runner


class ExactDispatchTests(unittest.TestCase):
    def test_all_selected_cases_have_exact_native_runner(self):
        manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
        for entry in manifest['cases']:
            with self.subTest(case=entry['case_id']):
                path = runner.exact_runner(entry['case_id'])
                self.assertTrue(path.is_file())
                self.assertEqual(path.parent.name,
                                 'selected_primary' if entry['case_id'].endswith('probe_03')
                                 else entry['case_id'].rsplit('__', 1)[-1])

    def test_unknown_case_rejected(self):
        with self.assertRaisesRegex(ValueError, 'one exact'):
            runner.exact_runner('unassigned')


if __name__ == '__main__':
    unittest.main()
