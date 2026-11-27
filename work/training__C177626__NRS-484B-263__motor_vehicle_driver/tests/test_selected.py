import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import check
class SelectedConstruction(unittest.TestCase):
    def test_exact_identity_and_geometry(self):
        config = json.loads((Path(__file__).resolve().parents[1] / 'config.json').read_text())
        report = check(config)
        self.assertEqual(report['case_id'], config['case_id'])
        self.assertEqual(report['camera_views'], [v['name'] for v in config['cameras']])
        self.assertFalse(report['physical_success_claimed'])
    def test_reject_wrong_case(self):
        config = json.loads((Path(__file__).resolve().parents[1] / 'config.json').read_text())
        config['case_id'] += '__wrong'
        with self.assertRaisesRegex(ValueError, 'exact selected entry case'):
            check(config)
