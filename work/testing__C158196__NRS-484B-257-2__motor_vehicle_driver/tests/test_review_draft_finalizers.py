"""Exercise the proposed common camera index without changing selected bundles."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import review_draft_officer_reference_saved_finalizer as officer_draft
import review_draft_saved_finalizer as crossing_draft
import test_officer_reference_saved_finalizer as officer_tests
from test_saved_finalizer import saved_fixture


class DraftReviewFinalizerTests(unittest.TestCase):
    def test_crossing_context_from_original_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            attempt = Path(directory)
            saved_fixture(attempt)
            crossing_draft.finalize(attempt, attempt / 'analysis.json')
            native = json.loads((attempt / 'result.json').read_text())
            review = json.loads((attempt / 'channels/original_camera_review.json').read_text())['original_camera_review']
            self.assertEqual(review['visual_judgment'], 'unreviewed')
            self.assertIn('original_camera_review',
                          {item['name'] for item in native['recording_evidence']})

    def test_officer_context_from_original_sources(self):
        fixture = officer_tests.OfficerReferenceSavedFinalizerTests(
            'test_native_result_retains_unresolved_judgment')
        fixture.setUp()
        try:
            path = fixture.attempt / 'video_frames.jsonl'
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            for row in rows:
                row['camera_frames'] = {name: row['carla_frame']
                                        for name in officer_draft.CAMERAS}
            path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with patch.object(officer_draft, '_probe'):
                officer_draft.finalize(fixture.attempt,
                                       fixture.attempt / 'analysis-report.json',
                                       fixture.site)
            native = json.loads((fixture.attempt / 'result.json').read_text())
            review = json.loads((fixture.attempt / 'channels/original_camera_review.json').read_text())['original_camera_review']
            self.assertEqual(review['frame_count'], 600)
            self.assertEqual(review['legal_judgment'], 'unresolved')
            self.assertIn('original_camera_review',
                          {item['name'] for item in native['recording_evidence']})
        finally:
            fixture.doCleanups()


if __name__ == '__main__':
    unittest.main()
