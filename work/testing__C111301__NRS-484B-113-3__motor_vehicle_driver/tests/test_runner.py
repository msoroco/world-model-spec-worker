"""Exact runner selection remains source gated at Native capture."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runner import check


class RunnerTests(unittest.TestCase):
    def test_exact_two_case_four_view_check(self):
        result = check(ROOT)
        self.assertEqual(len(result['selected_cases']), 2)
        self.assertTrue(result['source_site_required_at_capture'])
        self.assertFalse(result['physical_acceptance_claimed'])

    def test_noncanonical_camera_is_rejected(self):
        config = json.loads((ROOT / 'config.json').read_text())
        config['cameras'][0]['name'] = 'front'
        scratch = ROOT.parents[1] / '.runtime-work'
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            (Path(temp) / 'config.json').write_text(json.dumps(config) + '\n')
            with self.assertRaisesRegex(ValueError, 'four-view'):
                check(temp)


if __name__ == '__main__':
    unittest.main()
