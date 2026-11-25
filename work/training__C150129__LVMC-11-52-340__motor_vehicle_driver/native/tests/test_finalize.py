"""Saved-only parking analysis requires original samples and independent source bytes."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from finalize import finalize
from source_review import ASSIGNMENT


class FinalizeTests(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd() / '.runtime-work' / 'c150129'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temporary.cleanup)
        self.attempt = Path(self.temporary.name)
        case = ASSIGNMENT + '__controlled_2'
        (self.attempt / 'capture').mkdir()
        (self.attempt / 'source_context').mkdir()
        (self.attempt / 'config.json').write_text(json.dumps({
            'case_id': case, 'parking_case': 'inside_city_space'}) + '\n')
        (self.attempt / 'construction.json').write_text(json.dumps({
            'case_id': case, 'recording_description': {'channels': [
                {'name': 'vehicle-poses.jsonl', 'unit': 'structured'}]}}) + '\n')
        inventory = {'assignment_id': ASSIGNMENT,
                     'source_kind': 'synthetic_native_sample',
                     'space_id': 'city-space-01', 'space_polygon_xy_m':
                     [[-6, -7], [6, -7], [6, -3.5], [-6, -3.5]],
                     'native_marker_actor_id': 17,
                     'subject_city_vehicle': None}
        inventory_path = self.attempt / 'parking-inventory.json'
        inventory_path.write_text(json.dumps(inventory) + '\n')
        review = {'format': 'c150129-independent-source-review-v1',
                  'assignment_id': ASSIGNMENT, 'case_id': case,
                  'native_inventory_sha256': hashlib.sha256(inventory_path.read_bytes()).hexdigest()}
        assertions = {'city_street': {'is_city_street': True},
                      'council_designation': {'designated_for_city_vehicles': True,
                                              'space_id': 'city-space-01'},
                      'posting_or_marking': {'posted_or_marked': True,
                                             'space_id': 'city-space-01',
                                             'native_marker_actor_id': 17},
                      'subject_vehicle_status': {'subject_city_vehicle': False}}
        for field, values in assertions.items():
            path = self.attempt / 'source_context' / (field + '.txt')
            path.write_text('Synthetic CPU source: ' + field + '\n')
            review[field] = dict(values, path='source_context/' + path.name,
                                 sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                 source_id='synthetic-' + field,
                                 review_method='CPU synthetic source join')
        (self.attempt / 'review.json').write_text(json.dumps(review) + '\n')
        with (self.attempt / 'vehicle-poses.jsonl').open('w') as poses, \
             (self.attempt / 'video_frames.jsonl').open('w') as frames, \
             (self.attempt / 'trace.jsonl').open('w') as trace, \
             (self.attempt / 'capture/evidence.jsonl').open('w') as evidence:
            for i in range(600):
                row = {'video_frame': i, 'native_frame': i + 100,
                       'time_s': i / 20, 'vehicle_id': 'subject',
                       'vehicle_xy_m': [0, -5.2], 'yaw_rad': 0,
                       'bbox_half_length_m': 2, 'bbox_half_width_m': .8,
                       'speed_mps': 0 if 200 <= i < 500 else 2}
                poses.write(json.dumps(row) + '\n')
                frames.write(json.dumps({'video_frame': i, 'native_frame': i + 100,
                                         'time_s': i / 20}) + '\n')
                trace.write(json.dumps({'frame': i + 100, 'time_s': i / 20}) + '\n')
                evidence.write(json.dumps({'original_frame': i + 100}) + '\n')
        for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
            (self.attempt / (name + '.mkv')).write_text('synthetic placeholder for finalizer unit test\n')

    def test_source_join_and_measurement(self):
        report = finalize(self.attempt, self.attempt / 'analysis-report.json')
        metric = report['measurements']['municipal_street_parking']['value']
        self.assertEqual(metric['occupied_and_stationary_proxy_frames'], list(range(200, 500)))
        self.assertIsNone(metric['legal_result'])
        result = json.loads((self.attempt / 'result.json').read_text())
        self.assertEqual(result['provenance_kind'], 'synthetic_local_diagnostic')
        self.assertFalse(result['maneuver_completed'])

    def test_missing_posting_source_rejected(self):
        (self.attempt / 'source_context/posting_or_marking.txt').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing required source: source_context/posting_or_marking.txt'):
            finalize(self.attempt, self.attempt / 'analysis-report.json')


if __name__ == '__main__':
    unittest.main()
