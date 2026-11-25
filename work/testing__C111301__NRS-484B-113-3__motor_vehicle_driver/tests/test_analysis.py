"""Saved analyzer requires each exact case source; fixture proves software only."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis import analyze
from test_saved_backing import fixture


class AnalysisTests(unittest.TestCase):
    def test_positive_source_hashed_measurement(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parents[1] / '.runtime-work') as temp:
            attempt = Path(temp)
            fixture(attempt)
            (attempt / 'config.json').write_text((ROOT / 'config.json').read_text())
            report = analyze(attempt)
            item = report['measurements']['pedestrian_precedence']
            self.assertEqual(item['method'], 'measure_pedestrian_precedence')
            self.assertEqual(set(item['sources']),
                             {'acquisition.json', 'map.json', 'road.xodr',
                              'telemetry.json', 'frame-map.json'})
            self.assertIsNone(item['value']['statutory_priority_verdict'])

    def test_missing_source_is_rejected_before_measurement(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parents[1] / '.runtime-work') as temp:
            attempt = Path(temp)
            fixture(attempt)
            (attempt / 'config.json').write_text((ROOT / 'config.json').read_text())
            (attempt / 'map.json').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source: map.json'):
                analyze(attempt)


if __name__ == '__main__':
    unittest.main()
