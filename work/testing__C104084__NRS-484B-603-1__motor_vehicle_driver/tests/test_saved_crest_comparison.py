import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from saved_crest_comparison import CONTEXT, compare_saved
from test_saved_crest_audit import ASSIGNMENT, fixture, write


def attempts(root):
    left = root/'left'
    right = root/'right'
    left.mkdir()
    right.mkdir()
    a = fixture(left)
    b = fixture(right)
    a['capture_id'] = 'original-attempt-a'
    b['capture_id'] = 'original-attempt-b'
    b['profile'] = 'late_decrease'
    b['case_id'] = ASSIGNMENT+'__late_decrease'
    frames = json.loads((right/'motion.json').read_text())
    for index, frame in enumerate(frames):
        frame['ego_speed_mps'] = 10 if index < 400 else 9
    b['motion_source'] = write(right, 'motion.json', json.dumps(frames))
    for attempt, manifest in ((left, a), (right, b)):
        manifest['fixed_sources'] = {key: write(attempt, key+'.txt', 'same-'+key)
                                     for key in CONTEXT}
        manifest['fixed_sources']['other_route_source_sha256'] = manifest['other_route_source']
        manifest['fixed_sources']['highway_context_source_sha256'] = manifest['context_source']
        manifest['fixed_sources']['prescribed_limit_source_sha256'] = manifest['prescribed_limit_source']
    return left, a, right, b


class SavedCrestComparisonTests(unittest.TestCase):
    def test_source_bound_profile_difference(self):
        with tempfile.TemporaryDirectory() as tmp:
            proof = compare_saved(*attempts(Path(tmp)),
                                  expected_profiles=('early_decrease', 'late_decrease'))
            self.assertEqual(proof['capture_ids'], ['original-attempt-a', 'original-attempt-b'])
            self.assertFalse(proof['actual_pixels_verified'])
            self.assertNotEqual(proof['physical_measurements'][0]['first_speed_decrease_frame_id'],
                                proof['physical_measurements'][1]['first_speed_decrease_frame_id'])

    def test_rejects_changed_fixed_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            left, a, right, b = attempts(Path(tmp))
            b['fixed_sources']['other_motion_source_sha256'] = write(
                right, 'other_motion_source_sha256.txt', 'different')
            with self.assertRaisesRegex(ValueError, 'fixed condition'):
                compare_saved(left, a, right, b,
                              expected_profiles=('early_decrease', 'late_decrease'))

    def test_rejects_reused_capture_and_missing_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            left, a, right, b = attempts(Path(tmp))
            b['capture_id'] = a['capture_id']
            with self.assertRaisesRegex(ValueError, 'distinct'):
                compare_saved(left, a, right, b,
                              expected_profiles=('early_decrease', 'late_decrease'))
            b['capture_id'] = 'original-attempt-b'
            del b['fixed_sources']['camera_contract_sha256']
            with self.assertRaisesRegex(ValueError, 'context'):
                compare_saved(left, a, right, b,
                              expected_profiles=('early_decrease', 'late_decrease'))

    def test_rejects_decoy_fixed_source_not_used_by_saved_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            left, a, right, b = attempts(Path(tmp))
            for attempt, manifest in ((left, a), (right, b)):
                manifest['fixed_sources']['prescribed_limit_source_sha256'] = write(
                    attempt, 'decoy-limit.txt', 'same-but-not-the-source-used-by-audit')
            with self.assertRaisesRegex(ValueError, 'audited original context'):
                compare_saved(left, a, right, b,
                              expected_profiles=('early_decrease', 'late_decrease'))


if __name__ == '__main__':
    unittest.main()
