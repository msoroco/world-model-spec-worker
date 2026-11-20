"""CPU contract tests for independent original-source review citations."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from review_variant_annotations import CONTROLS, evaluate, review_attempt

HASH = 'a' * 64


def fixture(kind='warning_sign', route='crossing'):
    control_name, content = (CONTROLS[kind] if kind in CONTROLS else
                             ('governing_warning_control',
                              'barrier_across_or_around_identified_pavement'))
    analysis = {
        'format': 'c183370-variant-original-analysis-v1',
        'source_kind': 'original_carla_capture',
        'control_kind': kind,
        'case': route,
        'camera_sources': [
            {'name': name, 'source_sha256': HASH}
            for name in ('overview', 'approach', 'reference_corner',
                         'driver_reference')],
        'observations': {
            'source_first_frame': 100,
            'source_last_frame': 699,
            'source_frames': 600,
            'source_elapsed_s': 30,
            'control_actor_near_pavement_frames': 600,
            'pavement_footprint_contact_frames':
                list(range(200, 500)) if route == 'crossing' else [],
        },
    }
    review = {'reviewer_id': 'independent-source-reviewer',
              'source_analysis_sha256': HASH,
              'annotations': {
                  control_name: {
                      'observed': True,
                      'content': content,
                      'camera': 'overview',
                      'camera_sha256': HASH,
                      'frame_interval': [100, 699],
                      'observation': 'Original control content seen at the surveyed pavement.',
                  },
                  'newly_repaired_pavement': {
                      'observed': True,
                      'condition': 'newly_repaired',
                      'camera': 'approach',
                      'camera_sha256': HASH,
                      'frame_interval': [100, 699],
                      'observation': 'Original repaired pavement surface seen at this location.',
                  },
              }}
    if kind == 'employee_exception':
        review['annotations']['operator_activity'] = {
            'status': ('actually_engaged' if route == 'employee_crossing'
                       else 'not_actually_engaged'),
            'independent_evidence': {
                'reference': 'operator-activity-source.txt',
                'sha256': HASH,
                'observation': 'Independent source describes the operator activity at this repair.',
            }}
    return analysis, review


class VariantReviewTests(unittest.TestCase):
    def test_each_control_route_keeps_diagnostic_claims_false(self):
        for kind in CONTROLS:
            for route in ('crossing', 'avoidance'):
                with self.subTest(kind=kind, route=route):
                    analysis, review = fixture(kind, route)
                    result = evaluate(analysis, review, analysis_sha256=HASH)
                    self.assertEqual(result['requested_contact_context_observed'],
                                     True)
                    self.assertFalse(result['physical_acceptance_claimed'])
                    self.assertFalse(result['legal_verdict_claimed'])

    def test_source_and_content_changes_rejected(self):
        analysis, review = fixture()
        changed = copy.deepcopy(review)
        changed['annotations']['warning_sign_content']['camera_sha256'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'camera source hash'):
            evaluate(analysis, changed, analysis_sha256=HASH)
        changed = copy.deepcopy(review)
        changed['annotations']['warning_sign_content']['content'] = 'generic_warning'
        with self.assertRaisesRegex(ValueError, 'Specific control content'):
            evaluate(analysis, changed, analysis_sha256=HASH)
        changed = copy.deepcopy(analysis)
        changed['source_kind'] = 'synthetic_diagnostic_capture'
        with self.assertRaisesRegex(ValueError, 'Original variant source'):
            evaluate(changed, review, analysis_sha256=HASH)

    def test_nonoverlapping_citations_rejected(self):
        analysis, review = fixture()
        review['annotations']['warning_sign_content']['frame_interval'] = [100, 200]
        review['annotations']['newly_repaired_pavement']['frame_interval'] = [201, 699]
        with self.assertRaisesRegex(ValueError, 'do not overlap'):
            evaluate(analysis, review, analysis_sha256=HASH)

    def test_employee_activity_needs_distinct_independent_evidence(self):
        for route in ('employee_crossing', 'nonemployee_crossing'):
            with self.subTest(route=route):
                analysis, review = fixture('employee_exception', route)
                result = evaluate(analysis, review, analysis_sha256=HASH)
                self.assertEqual(result['paving_employee_exception_status'],
                                 review['annotations']['operator_activity']['status'])
                self.assertFalse(result['legal_verdict_claimed'])
                changed = copy.deepcopy(review)
                changed['annotations']['operator_activity']['status'] = 'unreviewed'
                with self.assertRaisesRegex(ValueError, 'activity status differs'):
                    evaluate(analysis, changed, analysis_sha256=HASH)

    def test_review_attempt_rejects_changed_camera_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            attempt = root / 'attempt'
            attempt.mkdir()
            analysis, review = fixture()
            for camera in analysis['camera_sources']:
                path = attempt / (camera['name'] + '.mkv')
                path.write_bytes(b'CPU source-shaped camera bytes')
                camera['source_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            for row in review['annotations'].values():
                row['camera_sha256'] = next(
                    camera['source_sha256'] for camera in analysis['camera_sources']
                    if camera['name'] == row['camera'])
            source = attempt / 'native-actors.jsonl'
            source.write_text('source-shaped rows\n')
            analysis['source_hashes'] = {
                source.name: hashlib.sha256(source.read_bytes()).hexdigest()}
            analysis_path = attempt / 'source-analysis.json'
            analysis_path.write_text(json.dumps(analysis))
            review['source_analysis_sha256'] = hashlib.sha256(
                analysis_path.read_bytes()).hexdigest()
            annotations_path = root / 'annotations.json'
            annotations_path.write_text(json.dumps(review))
            receipt = review_attempt(attempt, annotations_path, root / 'review.json')
            self.assertFalse(receipt['physical_acceptance_claimed'])
            (attempt / 'overview.mkv').write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'camera changed after analysis'):
                review_attempt(attempt, annotations_path, root / 'review-again.json')

    def test_employee_activity_source_hash_is_checked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            attempt = root / 'attempt'
            attempt.mkdir()
            analysis, review = fixture('employee_exception', 'employee_crossing')
            for camera in analysis['camera_sources']:
                path = attempt / (camera['name'] + '.mkv')
                path.write_bytes(b'source-shaped camera bytes')
                camera['source_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            for row in review['annotations'].values():
                if 'camera' in row:
                    row['camera_sha256'] = next(
                        camera['source_sha256'] for camera in analysis['camera_sources']
                        if camera['name'] == row['camera'])
            evidence = attempt / 'operator-activity-source.txt'
            evidence.write_text('Original source-shaped activity evidence.\n')
            review['annotations']['operator_activity']['independent_evidence'][
                'sha256'] = hashlib.sha256(evidence.read_bytes()).hexdigest()
            analysis_path = attempt / 'source-analysis.json'
            analysis_path.write_text(json.dumps(analysis))
            review['source_analysis_sha256'] = hashlib.sha256(
                analysis_path.read_bytes()).hexdigest()
            annotations_path = root / 'annotations.json'
            annotations_path.write_text(json.dumps(review))
            receipt = review_attempt(attempt, annotations_path, root / 'review.json')
            self.assertEqual(receipt['paving_employee_exception_status'],
                             'actually_engaged')
            evidence.write_text('changed\n')
            with self.assertRaisesRegex(ValueError, 'activity source hash differs'):
                review_attempt(attempt, annotations_path, root / 'review-again.json')


if __name__ == '__main__':
    unittest.main()
