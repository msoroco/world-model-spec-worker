import json
from pathlib import Path
import unittest

from runner import check


class DiagnosticBundleTest(unittest.TestCase):
    def test_exact_case_and_source_marking(self):
        scene = check()
        config = json.loads((Path(__file__).resolve().parents[1] / 'config.json').read_text())
        self.assertEqual(scene['case_id'], config['selected_case_id'])
        self.assertEqual(scene['source_kind'], 'synthetic_diagnostic_fixture')
        self.assertEqual(config['rate_hz'] * config['duration_s'], 900)
