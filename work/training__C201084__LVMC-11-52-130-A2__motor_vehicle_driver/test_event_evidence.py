"""Check source-bound event timing and the unresolved legal fields."""
import unittest
from pathlib import Path

from event_evidence import _episodes, build


ROOT = Path(__file__).resolve().parent


class EventEvidenceTest(unittest.TestCase):
    def test_source_bound_reference_and_contrast(self):
        reference = build(ROOT / 'fixtures/reference-sources',
                          'reference', diagnostic=True)
        contrast = build(ROOT / 'fixtures/contrast-sources',
                         'contrast', diagnostic=True)
        self.assertEqual(reference['frames'], 600)
        self.assertEqual(contrast['frames'], 600)
        self.assertEqual(sum(row['sample_count'] for row in
                             reference['near_zero_authored_zone_overlap_episodes']), 598)
        self.assertEqual(contrast['near_zero_authored_zone_overlap_episodes'], [])
        self.assertEqual(sum(row['sample_count'] for row in
                             contrast['near_zero_outside_authored_zone_episodes']), 598)
        self.assertEqual(reference['legal_act_classification'], None)
        self.assertFalse(reference['original_posting_or_designation_verified'])
        self.assertFalse(reference['driver_attendance_verified'])
        self.assertFalse(reference['physical_or_legal_completion_claimed'])
        self.assertIn('native-actors.jsonl', reference['source_sha256'])

    def test_diagnostic_is_not_original(self):
        with self.assertRaisesRegex(ValueError, 'Acquisition provenance'):
            build(ROOT / 'fixtures/reference-sources', 'reference')

    def test_contiguous_episode_duration(self):
        samples = [{'carla_frame': 100 + i, 'time_s': i / 20,
                    'speed_mps': speed}
                   for i, speed in enumerate((1, 0, 0, 1, 0))]
        self.assertEqual(_episodes(samples, lambda row: row['speed_mps'] == 0),
                         [{'first_frame': 101, 'last_frame': 102,
                           'first_time_s': 0.05, 'last_time_s': 0.1,
                           'sample_count': 2, 'sampled_duration_s': 0.1},
                          {'first_frame': 104, 'last_frame': 104,
                           'first_time_s': 0.2, 'last_time_s': 0.2,
                           'sample_count': 1, 'sampled_duration_s': 0.05}])


if __name__ == '__main__':
    unittest.main()
