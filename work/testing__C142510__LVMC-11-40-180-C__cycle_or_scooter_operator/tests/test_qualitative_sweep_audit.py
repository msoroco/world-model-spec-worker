"""Synthetic original-shaped receipts exercise the source gate only."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from qualitative_sweep_audit import audit
from sidewalk_overtake import ASSIGNMENT, SOURCES


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class SweepAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = ASSIGNMENT + '__bicycle_signal_before_yield'
        self.hashes = {name: hashlib.sha256(name.encode()).hexdigest() for name in SOURCES}
        fixed = {'sidewalk_id': 'SYNTHETIC ONLY',
                 'sidewalk_polygon_xy_m': [[0, 0], [4, 0], [4, 20], [0, 20]],
                 'map_sha256': self.hashes['road.xodr'],
                 'sidewalk_map_sha256': self.hashes['road.xodr']}
        self.receipt = {
            'format': 'c142510-independent-original-audit-v1',
            'case_id': self.case, 'source_kind': 'original_native_capture',
            'rider_kind': 'bicycle',
            'source_manifest_sha256': 'a' * 64, 'source_sha256': self.hashes,
            'fixed_site': fixed, 'physical_acceptance': False,
            'legal_status': 'unresolved',
            'measurement': {'case_id': self.case, 'frame_count': 900,
                            'pass_bracket_s': [10.0, 10.05],
                            'source_sha256': self.hashes,
                            'legal_verdict_claimed': False,
                            'brake_frames_before_pass': [190],
                            'original_emitter_event_times_s': [8.0],
                            'microphone': {'onset_time_s': 8.05}}}
        self.receipt_path = self.root / 'receipt.json'
        self.review_path = self.root / 'review.json'
        self.save_receipt()

    def save_receipt(self):
        self.receipt_path.write_text(json.dumps(self.receipt) + '\n')

    def save_review(self, kind, sweep):
        plan = json.loads((HERE / 'case-plan.json').read_text())
        spec = next(item for item in plan['judgment_range_inventory']
                    if item['sweep_id'] == sweep)
        point = next(item for item in spec['sampled_points']
                     if item['case_id'] == self.case)
        review = {'case_id': self.case, 'sweep_id': sweep, 'kind': kind,
                  'source_receipt_sha256': sha(self.receipt_path),
                  'source_sha256': dict(self.hashes),
                  'source_manifest_sha256': 'a' * 64,
                  'authored_point': point,
                  'reviewer': 'synthetic independent reviewer',
                  'method': 'synthetic interval review',
                  'independent_of_capture': True,
                  'original_intervals_s': [[9.0, 11.0]],
                  'qualitative_observation':
                      'observed_pause_or_brake' if kind == 'yielding' else
                      'heard_at_pedestrian',
                  'legal_verdict': None,
                  'pedestrian_precedence_source': 'synthetic history reference',
                  'pedestrian_response_source': 'synthetic history reference',
                  'pedestrian_listening_position_source': 'synthetic position reference',
                  'emitter_capability_source': 'synthetic capability reference',
                  'microphone_capability_source': 'synthetic capability reference'}
        self.review_path.write_text(json.dumps(review) + '\n')
        return review

    def test_both_source_gated_sweeps(self):
        for kind, sweep in [('yielding', 'c142510-0'),
                            ('audible_signal', 'c142510-1')]:
            self.save_review(kind, sweep)
            result = audit(self.case, self.receipt_path, self.review_path, sweep)
            self.assertIsNone(result['legal_verdict'])
            self.assertFalse(result['physical_acceptance'])

    def test_missing_review_and_original_source_rejected(self):
        self.save_review('yielding', 'c142510-0')
        self.review_path.unlink()
        with self.assertRaises(FileNotFoundError):
            audit(self.case, self.receipt_path, self.review_path, 'c142510-0')
        self.save_review('yielding', 'c142510-0')
        self.receipt['source_kind'] = 'synthetic_diagnostic_fixture'
        self.save_receipt()
        with self.assertRaisesRegex(ValueError, 'original independent receipt'):
            audit(self.case, self.receipt_path, self.review_path, 'c142510-0')

    def test_changed_source_and_legal_verdict_rejected(self):
        review = self.save_review('audible_signal', 'c142510-1')
        review['source_sha256']['pedestrian-microphone.wav'] = '0' * 64
        self.review_path.write_text(json.dumps(review) + '\n')
        with self.assertRaisesRegex(ValueError, 'source binding'):
            audit(self.case, self.receipt_path, self.review_path, 'c142510-1')
        review = self.save_review('audible_signal', 'c142510-1')
        review['legal_verdict'] = 'compliant'
        self.review_path.write_text(json.dumps(review) + '\n')
        with self.assertRaisesRegex(ValueError, 'without legal verdict'):
            audit(self.case, self.receipt_path, self.review_path, 'c142510-1')

    def test_missing_capability_and_interval_rejected(self):
        review = self.save_review('audible_signal', 'c142510-1')
        review.pop('microphone_capability_source')
        self.review_path.write_text(json.dumps(review) + '\n')
        with self.assertRaisesRegex(ValueError, 'microphone evidence'):
            audit(self.case, self.receipt_path, self.review_path, 'c142510-1')
        review = self.save_review('yielding', 'c142510-0')
        review['original_intervals_s'] = [[0, 1]]
        self.review_path.write_text(json.dumps(review) + '\n')
        with self.assertRaisesRegex(ValueError, 'passing interval'):
            audit(self.case, self.receipt_path, self.review_path, 'c142510-0')

    def test_sparse_points_match_exact_six_selected_constructions(self):
        plan = json.loads((HERE / 'case-plan.json').read_text())
        manifest = json.loads((HERE / 'execution-manifest.json').read_text())
        expected = {item['case_id'] for item in manifest['cases']}
        for spec in plan['judgment_range_inventory']:
            points = {item['case_id']: item for item in spec['sampled_points']}
            self.assertEqual(set(points), expected)
            for entry in manifest['cases']:
                construction = json.loads((HERE / entry['construction']).read_text())
                config = json.loads(next(item['content'] for item in construction['files']
                                         if item['path'] == 'config.json'))['case']
                point = points[entry['case_id']]
                self.assertEqual({key: config[key] for key in
                                  ('rider_kind', 'signal_frame', 'rider_response')},
                                 {key: point[key] for key in
                                  ('rider_kind', 'signal_frame', 'rider_response')})
        yielded = [p for p in points.values() if p['rider_response'] == 'yield_brake']
        self.assertEqual({p['rider_kind'] for p in yielded},
                         {'bicycle', 'electric_bicycle', 'electric_scooter'})
        self.assertEqual({p['signal_frame'] for p in points.values()
                          if p['rider_kind'] == 'bicycle' and
                          p['rider_response'] == 'yield_brake'}, {100, 400, None})

    def test_review_point_mismatch_rejected(self):
        review = self.save_review('yielding', 'c142510-0')
        review['authored_point']['signal_frame'] = 400
        self.review_path.write_text(json.dumps(review) + '\n')
        with self.assertRaisesRegex(ValueError, 'source binding'):
            audit(self.case, self.receipt_path, self.review_path, 'c142510-0')


if __name__ == '__main__':
    unittest.main()
