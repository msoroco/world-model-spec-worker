import json
from pathlib import Path
import tempfile
import unittest

from finalize import report, sha
from prove_speed import trace


class RecordedOnlyMeasurement(unittest.TestCase):
    def test_source_join_and_missing_sign_survey(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'road.xodr').write_text('<OpenDRIVE/>\n')
            (root / 'config.json').write_text(json.dumps({'case_id': 'synthetic-speed-test'}))
            (root / 'law-text.json').write_text(json.dumps({'source': 'LVMC 11.16.060',
                'text': 'The prima facie speed limit is twenty-five miles per hour on all streets and highways unless a different speed limit is posted as set forth in this Title.'}))
            (root / 'actor-poses.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in trace(20)))
            (root / 'reference_corner.mkv').write_bytes(b'synthetic camera placeholder')
            (root / 'street-status.json').write_text(json.dumps({
                'source_kind': 'independent_street_status',
                'review_status': 'independently_reviewed',
                'reviewer': 'synthetic unit test',
                'street_status': 'city_street', 'road_sha256': sha(root / 'road.xodr')}))
            (root / 'sign-survey.json').write_text(json.dumps({
                'source_kind': 'native_complete_sign_survey',
                'review_status': 'independently_reviewed',
                'reviewer': 'synthetic unit test',
                'road_sha256': sha(root / 'road.xodr'),
                'surveyed_route_interval_m': [0, 500],
                'survey_complete_both_directions': True,
                'pixel_source': 'reference_corner.mkv',
                'applicable_posted_signs': [{'governs_from_m': 100, 'governs_to_m': 500,
                    'limit_mph': 25, 'pixel_sha256': sha(root / 'reference_corner.mkv')}]}))
            result = report(root)
            value = result['measurements']['source_bound_speed_and_governance']['value']
            self.assertEqual(value['default_governed_frames'], 600)
            self.assertEqual(value['default_frames_above_25_mph'], 0)
            (root / 'sign-survey.json').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source: sign-survey.json'):
                report(root)


if __name__ == '__main__':
    unittest.main()
