import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'runtime'))
from analysis import analyze
from test_saved_crest import ASSIGNMENT, CASE, fixture


class SavedAnalysisTests(unittest.TestCase):
    def test_finalizes_only_original_join_and_preserves_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt = Path(temp)
            hashes = fixture(attempt)
            manifest = attempt / 'source-hashes.json'
            manifest.write_text(json.dumps(hashes) + '\n', encoding='utf-8')
            original = {name: hashlib.sha256((attempt / name).read_bytes()).hexdigest()
                        for name in hashes}
            report = analyze(attempt, assignment_id=ASSIGNMENT, case_id=CASE,
                             expected_frames=3, recording_description={'channels': [],
                                                                         'context_inputs': []})
            self.assertEqual(report['case_id'], CASE)
            self.assertFalse(report['physical_acceptance_claimed'])
            result = json.loads((attempt / 'result.json').read_text())
            self.assertFalse(result['setup_confirmed'])
            self.assertFalse(result['target_checks'][0]['physical_cause_confirmed'])
            self.assertEqual(len((attempt / 'trace.jsonl').read_text().splitlines()), 3)
            rows = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
            self.assertEqual([row['carla_frame'] for row in rows], [0, 1, 2])
            self.assertEqual(original, {name: hashlib.sha256((attempt / name).read_bytes()).hexdigest()
                                        for name in hashes})
            with self.assertRaisesRegex(ValueError, 'retain prior derived'):
                analyze(attempt, assignment_id=ASSIGNMENT, case_id=CASE,
                        expected_frames=3, recording_description={'channels': []})

    def test_changed_original_rejected_before_any_derived_output(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt = Path(temp)
            hashes = fixture(attempt)
            (attempt / 'source-hashes.json').write_text(json.dumps(hashes) + '\n')
            (attempt / 'crest-rays.jsonl').write_text('{}\n')
            with self.assertRaisesRegex(ValueError, 'original source changed'):
                analyze(attempt, assignment_id=ASSIGNMENT, case_id=CASE,
                        expected_frames=3, recording_description={'channels': []})
            self.assertFalse((attempt / 'result.json').exists())
            self.assertFalse((attempt / 'video_frames.jsonl').exists())

    def test_unplanned_manifest_source_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt = Path(temp)
            hashes = fixture(attempt)
            hashes['unplanned.txt'] = 'a' * 64
            (attempt / 'source-hashes.json').write_text(json.dumps(hashes) + '\n')
            with self.assertRaisesRegex(ValueError, 'wrong exact sources'):
                analyze(attempt, assignment_id=ASSIGNMENT, case_id=CASE,
                        expected_frames=3, recording_description={'channels': []})
            self.assertFalse((attempt / 'result.json').exists())


if __name__ == '__main__':
    unittest.main()
