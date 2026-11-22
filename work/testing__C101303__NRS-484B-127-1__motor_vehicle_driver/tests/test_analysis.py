import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis import build_report
from test_following import CASE, fixture


class AnalysisTest(unittest.TestCase):
    def test_saved_report_retains_original_measurement_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root)
            (root/'config.json').write_text(json.dumps({'selected_case_id': CASE}))
            (root/'fixture-provenance.json').write_text(json.dumps({
                'diagnostic_fixture': True, 'physical_acceptance_claimed': False}))
            report = build_report(root)
            self.assertTrue(report['analysis_complete'])
            self.assertFalse(report['legal_verdict_claimed'])
            self.assertEqual(report['measurements']['following_spacing_measurement']
                             ['value']['mean_ego_speed_mps'], 9)
            (root/'fixture-provenance.json').write_text(json.dumps({
                'diagnostic_fixture': True, 'physical_acceptance_claimed': True}))
            with self.assertRaisesRegex(ValueError, 'untrusted diagnostic fixture'):
                build_report(root)


if __name__ == '__main__':
    unittest.main()
