import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'runtime'))
from analysis import analyze
from derived_audit import audit
from test_saved_crest import ASSIGNMENT, CASE, fixture


def prepared(attempt):
    import hashlib
    hashes = fixture(attempt)
    (attempt / 'source-hashes.json').write_text(json.dumps(hashes) + '\n', encoding='utf-8')
    analyze(attempt, assignment_id=ASSIGNMENT, case_id=CASE, expected_frames=3,
            recording_description={'channels': [], 'context_inputs': []})


class DerivedAuditTests(unittest.TestCase):
    def test_independently_rejoins_derived_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            attempt = Path(temporary)
            prepared(attempt)
            receipt = audit(attempt, assignment_id=ASSIGNMENT, case_id=CASE,
                            expected_frames=3)
            self.assertTrue(receipt['source_join_passed'])
            self.assertEqual(receipt['verified_frames'], 3)
            self.assertFalse(receipt['physical_acceptance_claimed'])

    def test_rejects_resealed_derived_trace_and_frame_map(self):
        for name, field, value, error in (
                ('trace.jsonl', 'opposing_body_distance_m', 999, 'derived trace'),
                ('video_frames.jsonl', 'carla_frame', 999, 'derived frame map')):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                attempt = Path(temporary)
                prepared(attempt)
                path = attempt / name
                rows = [json.loads(line) for line in path.read_text().splitlines()]
                rows[0][field] = value
                path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
                with self.assertRaisesRegex(ValueError, error):
                    audit(attempt, assignment_id=ASSIGNMENT, case_id=CASE,
                          expected_frames=3)

    def test_rejects_unsupported_completion_and_target_claims(self):
        for mutate, error in (
                (lambda result: result.update(setup_confirmed=True), 'physical completion'),
                (lambda result: result['target_checks'][0].update(measured=False), 'target check')):
            with self.subTest(error=error), tempfile.TemporaryDirectory() as temporary:
                attempt = Path(temporary)
                prepared(attempt)
                path = attempt / 'result.json'
                result = json.loads(path.read_text())
                mutate(result)
                path.write_text(json.dumps(result) + '\n')
                with self.assertRaisesRegex(ValueError, error):
                    audit(attempt, assignment_id=ASSIGNMENT, case_id=CASE,
                          expected_frames=3)


if __name__ == '__main__':
    unittest.main()
