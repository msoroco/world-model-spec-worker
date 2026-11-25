"""Saved analyzer requires each exact case source; fixture proves software only."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis import analyze, saved_result
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
                              'telemetry.json', 'frame-map.json',
                              'trace.jsonl', 'video_frames.jsonl'})
            self.assertIsNone(item['value']['statutory_priority_verdict'])

    def test_missing_source_is_rejected_before_measurement(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parents[1] / '.runtime-work') as temp:
            attempt = Path(temp)
            fixture(attempt)
            (attempt / 'config.json').write_text((ROOT / 'config.json').read_text())
            (attempt / 'map.json').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source: map.json'):
                analyze(attempt)

    def test_diagnostic_source_requires_explicit_marker_and_preserves_label(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parents[1] / '.runtime-work') as temp:
            attempt = Path(temp)
            receipt = fixture(attempt)
            receipt['source_kind'] = 'synthetic_fixture'
            receipt['diagnostic'] = True
            (attempt / 'acquisition.json').write_text(json.dumps(receipt) + '\n')
            (attempt / 'config.json').write_text((ROOT / 'config.json').read_text())
            with self.assertRaisesRegex(ValueError, 'original Native acquisition required'):
                analyze(attempt)
            (attempt / 'diagnostic-fixture.json').write_text(
                json.dumps({'format': 'worker-diagnostic-fixture',
                            'diagnostic_fixture': True}) + '\n')
            report = analyze(attempt)
            self.assertTrue(report['diagnostic_fixture'])
            self.assertEqual(report['provenance_kind'], 'synthetic_fixture')
            self.assertFalse(report['physical_acceptance_claimed'])

    def test_saved_result_projects_exact_channels_without_legal_verdict(self):
        from worker_exchange.native_output import validate_result
        with tempfile.TemporaryDirectory(dir=ROOT.parents[1] / '.runtime-work') as temp:
            attempt = Path(temp)
            fixture(attempt)
            (attempt / 'config.json').write_text((ROOT / 'config.json').read_text())
            (attempt / 'construction.json').write_text((ROOT / 'construction.json').read_text())
            native = saved_result(attempt, analyze(attempt))
            self.assertEqual(native['case_id'], ROOT.name + '__pedestrian_yield')
            self.assertEqual(len(native['recording_evidence']), 3)
            self.assertNotIn('legal_verdict', native)
            validate_result(native)


if __name__ == '__main__':
    unittest.main()
