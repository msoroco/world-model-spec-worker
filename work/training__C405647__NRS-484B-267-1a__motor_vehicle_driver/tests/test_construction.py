import json
from pathlib import Path
import unittest
from runner import check


class ConstructionTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_exact_preflight(self):
        result = check(self.config['case_suffix'], self.config['candidate_id'])
        self.assertTrue(result['passed'])
        self.assertEqual(result['native_track_rows'], 480)
        self.assertEqual(result['camera_count'], 4)
        self.assertFalse(result['carla_imported'])

    def test_unknown_candidate_rejected(self):
        with self.assertRaises(ValueError):
            check(self.config['case_suffix'], 'unsupported')


if __name__ == '__main__':
    unittest.main()
