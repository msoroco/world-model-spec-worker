import json
import sys
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from median_scene import check


class SelectedMedianRequestTest(unittest.TestCase):
    def test_exact_requests(self):
        for suffix in ('through_opening', 'across_divider'):
            with self.subTest(suffix=suffix):
                bundle = PACKAGE / 'native' / 'bundles' / suffix / 'construction.json'
                construction = json.loads(bundle.read_text())
                files = {entry['path']: entry['content'] for entry in construction['files']}
                request = json.loads(files['request.json'])
                config = json.loads(files['config.json'])
                self.assertEqual(check(request)['case'], suffix)
                self.assertEqual(config['case_id'], construction['case_id'])
                self.assertEqual(config['physical_completion']['criterion'], 'turn')
                self.assertEqual(config['physical_completion']['motion_source'], 'body_history.jsonl')


if __name__ == '__main__':
    unittest.main()
