"""Original attempt comparator source binding and rejection tests."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT.parents[1] / '.runtime-work' / 'c229439-saved-v3'
sys.path.insert(0, str(ROOT))
from original_comparison_audit import audit
PAIRS = (
    ('device_effective_time', 'park_effective', 'park_not_effective'),
    ('traffic_conflict_exception', 'stop_effective', 'stop_for_conflict'),
    ('law_direction_exception', 'park_effective', 'park_law_direction'),
    ('police_direction_exception', 'park_effective', 'park_police_direction'),
    ('device_direction_exception', 'park_effective', 'park_device_direction'),
)


class OriginalComparisonTest(unittest.TestCase):
    def attempt(self, name):
        return FIXTURES / name / 'attempt'

    def copy_sources(self, name, dest):
        dest.mkdir(parents=True)
        for filename in ('attempt.json', 'site-source.json', 'device-source.json',
                         'actor_rows.json'):
            shutil.copyfile(self.attempt(name) / filename, dest / filename)
        return dest

    def test_all_exact_diagnostic_pairs(self):
        for comparison, left, right in PAIRS:
            with self.subTest(comparison=comparison):
                result = audit(comparison, self.attempt(left), self.attempt(right),
                               diagnostic=True)
                self.assertEqual(result['different_halt_frames'], 200)
                self.assertFalse(result['physical_acceptance'])
                self.assertIsNone(result['legal_judgment'])

    def test_production_rejects_synthetic_attempt(self):
        comparison, left, right = PAIRS[0]
        with self.assertRaisesRegex(ValueError, 'original Native source format required'):
            audit(comparison, self.attempt(left), self.attempt(right))

    def test_independent_attempts_required(self):
        with self.assertRaisesRegex(ValueError, 'independent attempts'):
            audit('device_effective_time', self.attempt('park_effective'),
                  self.attempt('park_effective'), diagnostic=True)

    def test_changed_source_hash_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            right = self.copy_sources('park_not_effective', Path(tmp) / 'right')
            rows = right / 'actor_rows.json'
            rows.write_bytes(rows.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'original source hash mismatch'):
                audit('device_effective_time', self.attempt('park_effective'), right,
                      diagnostic=True)

    def test_wrong_case_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            right = self.copy_sources('park_not_effective', Path(tmp) / 'right')
            path = right / 'attempt.json'
            attempt = json.loads(path.read_text())
            attempt['case_id'] = 'wrong-case'
            path.write_text(json.dumps(attempt) + '\n')
            with self.assertRaisesRegex(ValueError, 'wrong exact comparison case'):
                audit('device_effective_time', self.attempt('park_effective'), right,
                      diagnostic=True)

    def test_erased_difference_rejected(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            right = self.copy_sources('park_not_effective', Path(tmp) / 'right')
            left_rows = json.loads((self.attempt('park_effective') / 'actor_rows.json').read_text())
            rows_path = right / 'actor_rows.json'
            right_rows = json.loads(rows_path.read_text())
            for a, b in zip(left_rows, right_rows):
                b['device_effective'] = a['device_effective']
            rows_path.write_text(json.dumps(right_rows) + '\n')
            attempt_path = right / 'attempt.json'
            attempt = json.loads(attempt_path.read_text())
            attempt['source_context']['actor_rows.json']['sha256'] = hashlib.sha256(
                rows_path.read_bytes()).hexdigest()
            attempt_path.write_text(json.dumps(attempt) + '\n')
            with self.assertRaisesRegex(ValueError, 'deliberate source difference absent'):
                audit('device_effective_time', self.attempt('park_effective'), right,
                      diagnostic=True)


if __name__ == '__main__':
    unittest.main()
