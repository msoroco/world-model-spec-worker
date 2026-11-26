import json
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]


class SelectedPriorityRequestTest(unittest.TestCase):
    def test_exact_requests_and_capture(self):
        names = ('overview', 'approach', 'reference_corner', 'driver_reference')
        for suffix in ('priority_yield', 'priority_intrusion'):
            with self.subTest(suffix=suffix):
                path = PACKAGE / 'native/selected' / suffix / 'primary/construction.json'
                construction = json.loads(path.read_text())
                files = {item['path']: item['content'] for item in construction['files']}
                config = json.loads(files['config.json'])
                self.assertEqual(config['case_id'], PACKAGE.name + '__' + suffix)
                self.assertEqual(config['law_id'], 'NRS-484B-250-1')
                self.assertEqual(config['physical_completion']['criterion'], 'intersection_clearance')
                self.assertEqual([camera['name'] for camera in config['cameras']], list(names))
                self.assertEqual(config['duration_s'], 30)
                self.assertIn('crossing_history.jsonl', files['finalize.py'])
                self.assertIn('right_of_way_legally_determined', files['finalize.py'])


if __name__ == '__main__':
    unittest.main()
