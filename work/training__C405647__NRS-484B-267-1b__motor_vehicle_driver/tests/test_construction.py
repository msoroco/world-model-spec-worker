import json
from pathlib import Path
import unittest
from runner import check
from measure_saved import assignment_hash


class ConstructionTests(unittest.TestCase):
    def test_exact_bundle_preflight(self):
        config = json.loads(Path('config.json').read_text())
        result = check(config['case_suffix'], config['candidate_id'])
        self.assertTrue(result['passed'])
        self.assertEqual(result['native_track_rows'], 600)
        self.assertEqual(result['camera_count'], 4)
        self.assertFalse(result['carla_imported'])

    def test_unknown_variant_rejected(self):
        config = json.loads(Path('config.json').read_text())
        with self.assertRaises(ValueError):
            check(config['case_suffix'], 'unsupported')

    def test_bundled_frozen_assignment_source(self):
        config = json.loads(Path('config.json').read_text())
        self.assertEqual(assignment_hash(), config['assignment_sha256'])


if __name__ == '__main__':
    unittest.main()
