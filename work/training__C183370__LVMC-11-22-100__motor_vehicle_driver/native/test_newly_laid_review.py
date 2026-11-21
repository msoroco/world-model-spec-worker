"""Negative source-binding checks; all inputs here are synthetic unit mocks."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from newly_laid_review_annotations import evaluate, review_attempt


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fixture():
    camera_hashes = {name: sha(name.encode()) for name in
                     ('overview', 'approach', 'reference_corner', 'driver_reference')}
    analysis = {
        'format': 'c183370-newly-laid-original-source-analysis-v1',
        'source_kind': 'original_carla_capture',
        'case': 'newly_laid_crossing',
        'source_hashes': {},
        'camera_sources': [{'name': name, 'source_sha256': digest}
                           for name, digest in camera_hashes.items()],
        'observations': {'source_first_frame': 100, 'source_last_frame': 699,
                         'source_frames': 600,
                         'pavement_footprint_contact_frames': [200]},
    }
    review = {
        'source_analysis_sha256': 'a' * 64,
        'reviewer_id': 'independent-source-reviewer',
        'annotations': {
            'warning_act': {'observed': True,
                            'warning_content': 'against_riding_or_driving_over_identified_pavement',
                            'camera': 'approach',
                            'camera_sha256': camera_hashes['approach'],
                            'frame_interval': [250, 400],
                            'observation': 'Person visibly warns against driving across this surface.'},
            'newly_laid_pavement': {'observed': True, 'condition': 'newly_laid',
                                   'camera': 'overview',
                                   'camera_sha256': camera_hashes['overview'],
                                   'frame_interval': [200, 500],
                                   'observation': 'The reviewed surface occupies the surveyed road polygon.',
                                   'independent_surface_history': {
                                       'source_kind': 'dated_paving_record',
                                       'reference': 'surface-history.txt',
                                       'sha256': sha(b'dated source mock'),
                                       'observation': 'Dated paving record identifies this road surface as newly laid.',
                                       'map_name': 'SourceTown', 'road_id': 12}},
        },
    }
    return analysis, review


class NewlyLaidReviewTests(unittest.TestCase):
    def test_requires_independent_history_and_exact_condition(self):
        analysis, review = fixture()
        result = evaluate(analysis, review, analysis_sha256='a' * 64)
        self.assertEqual(result['contact_during_reviewed_context_frames'], [300])
        self.assertFalse(result['physical_acceptance_claimed'])
        missing = copy.deepcopy(review)
        del missing['annotations']['newly_laid_pavement']['independent_surface_history']
        with self.assertRaisesRegex(ValueError, 'independent dated surface history'):
            evaluate(analysis, missing, analysis_sha256='a' * 64)
        repaired = copy.deepcopy(review)
        repaired['annotations']['newly_laid_pavement']['condition'] = 'newly_repaired'
        with self.assertRaisesRegex(ValueError, 'Newly laid condition'):
            evaluate(analysis, repaired, analysis_sha256='a' * 64)

    def test_rejects_changed_camera_and_nonoverlap(self):
        analysis, review = fixture()
        changed = copy.deepcopy(review)
        changed['annotations']['warning_act']['camera_sha256'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'camera source hash'):
            evaluate(analysis, changed, analysis_sha256='a' * 64)
        changed = copy.deepcopy(review)
        changed['annotations']['warning_act']['frame_interval'] = [501, 550]
        with self.assertRaisesRegex(ValueError, 'do not overlap'):
            evaluate(analysis, changed, analysis_sha256='a' * 64)

    def test_review_attempt_binds_history_bytes_and_map(self):
        analysis, review = fixture()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'surface-history.txt').write_bytes(b'dated source mock')
            (path / 'live-readback.json').write_text(json.dumps({
                'plan': {'map_name': 'SourceTown'}, 'pavement_road_id': 12}))
            for camera in analysis['camera_sources']:
                (path / (camera['name'] + '.mkv')).write_bytes(camera['name'].encode())
            analysis_path = path / 'source-analysis.json'
            analysis_path.write_text(json.dumps(analysis))
            review['source_analysis_sha256'] = sha(analysis_path.read_bytes())
            annotation_path = path / 'review.json'
            annotation_path.write_text(json.dumps(review))
            result = review_attempt(path, annotation_path, path / 'receipt.json')
            self.assertEqual(result['surface_history_sha256'], sha(b'dated source mock'))
            (path / 'surface-history.txt').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'surface history hash differs'):
                review_attempt(path, annotation_path, path / 'second-receipt.json')


if __name__ == '__main__':
    unittest.main()
