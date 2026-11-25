"""Provenance boundaries for CPU diagnostic finalization."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from finalize import measurement_rows, verified_arrow_frames


class FinalizerContractTest(unittest.TestCase):
    def test_synthetic_aspect_is_explicitly_diagnostic(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'capture').mkdir()
            (root / 'capture/manifest.json').write_text(json.dumps({'synthetic_diagnostic': True}))
            (root / 'aspect-review.json').write_text(json.dumps({
                'review_kind': 'synthetic_fixture_aspect', 'original_pixel_reviewed': False,
                'diagnostic_only': True, 'first_video_frame': 100, 'last_video_frame': 200}))
            frames, evidence = verified_arrow_frames(root, 840)
            self.assertEqual((min(frames), max(frames)), (100, 200))
            self.assertFalse(evidence['original_pixel_reviewed'])
            self.assertTrue(evidence['diagnostic_only'])
            (root / 'capture/manifest.json').unlink()
            with self.assertRaisesRegex(ValueError, 'Original pixel aspect/governing review incomplete'):
                verified_arrow_frames(root, 840)

    def test_measurements_hash_exact_sources_and_reject_missing_native(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('aspect-review.json', 'overview.mkv', 'reference_corner.mkv',
                         'native_samples.jsonl', 'body_history.jsonl', 'road_geometry.json'):
                (root / name).write_text(name)
            summary = {'sole_arrow_pixel_verified_frames': 600,
                       'straight_heading_no_turn_observed': True,
                       'other_vehicle_present_under_verified_arrow': True,
                       'prior_green_entry_within_verified_arrow': True,
                       'first_front_stop_line_crossing_frame': 400,
                       'last_other_vehicle_occupancy_under_verified_arrow_frame': 350,
                       'yielded_before_entry': True}
            rows = measurement_rows(root, summary)
            self.assertEqual(set(rows), {'arrow_aspect', 'straight_motion',
                                         'yield_timing', 'other_vehicle_conflict'})
            self.assertTrue(rows['yield_timing']['value']['yielded_before_entry'])
            (root / 'native_samples.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source: native_samples.jsonl'):
                measurement_rows(root, summary)
