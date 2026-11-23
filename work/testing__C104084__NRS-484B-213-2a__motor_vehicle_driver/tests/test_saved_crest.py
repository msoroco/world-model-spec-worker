import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('saved_crest', ROOT / 'saved_crest.py')
saved = importlib.util.module_from_spec(spec)
spec.loader.exec_module(saved)
ASSIGNMENT = ROOT.name
CASE = ASSIGNMENT + '__left_crest_obstructed'


def fixture(directory):
    sources = {
        'frames.jsonl': '\n'.join(json.dumps({
            'frame': index, 'timestamp_s': index / 20,
            'ego_body_corners_signed_m': [-1, -0.5, 0.1, 0.2],
            'opposing_body_distance_m': 25 - index,
            'ego_source_ref': 'Native ego 1', 'opposing_source_ref': 'Native other 2'})
            for index in range(3)) + '\n',
        'crest-rays.jsonl': '\n'.join(json.dumps({
            'frame': index, 'body_corner_ray_hits': [True] * 4,
            'ray_source_ref': 'Native raycast'}) for index in range(3)) + '\n',
        'lane-context.json': json.dumps({
            'case_id': CASE, 'law_id': 'NRS-484B-213-2a',
            'lane_allocation': 'two_way', 'opposing_lane_source_ref': 'Native lane -1',
            'highway_source_ref': 'original road authority',
            'center_reference_source_ref': 'Native road center'}),
        'frame-map.json': json.dumps({'frames': [0, 1, 2]}),
        'camera-forward.mp4': 'forward-camera-source',
        'camera-left.mp4': 'left-camera-source',
        'camera-right.mp4': 'right-camera-source',
        'camera-rear.mp4': 'rear-camera-source',
    }
    for name, value in sources.items():
        (directory / name).write_text(value, encoding='utf-8')
    return {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
            for name in sources}


class SavedCrestTests(unittest.TestCase):
    def test_source_bound_body_and_ray_measurement(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt = Path(temp)
            hashes = fixture(attempt)
            result = saved.measure(attempt, hashes, case_id=CASE, assignment_id=ASSIGNMENT)
            self.assertEqual(result['ego_body_left_side_frames'], [0, 1, 2])
            self.assertEqual(result['all_corner_rays_blocked_frames'], [0, 1, 2])
            self.assertTrue(result['construction_target_observed'])
            self.assertEqual(result['hazard_distance_judgment'], 'unresolved')

    def test_rejects_changed_source_and_missing_camera(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt = Path(temp)
            hashes = fixture(attempt)
            (attempt / 'crest-rays.jsonl').write_text('{}\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'original source changed'):
                saved.measure(attempt, hashes, case_id=CASE, assignment_id=ASSIGNMENT)
            hashes = fixture(attempt)
            (attempt / 'camera-left.mp4').unlink()
            with self.assertRaisesRegex(ValueError, 'source path is missing'):
                saved.measure(attempt, hashes, case_id=CASE, assignment_id=ASSIGNMENT)

    def test_rejects_dropped_frame_and_missing_ray(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt = Path(temp)
            hashes = fixture(attempt)
            path = attempt / 'frame-map.json'
            path.write_text(json.dumps({'frames': [0, 2]}), encoding='utf-8')
            hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'does not join'):
                saved.measure(attempt, hashes, case_id=CASE, assignment_id=ASSIGNMENT)
            hashes = fixture(attempt)
            path = attempt / 'crest-rays.jsonl'
            rows = path.read_text().splitlines()
            path.write_text('\n'.join(rows[:2]) + '\n', encoding='utf-8')
            hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'does not join'):
                saved.measure(attempt, hashes, case_id=CASE, assignment_id=ASSIGNMENT)

    def test_one_way_needs_original_authority(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt = Path(temp)
            hashes = fixture(attempt)
            path = attempt / 'lane-context.json'
            context = json.loads(path.read_text())
            context['case_id'] = ASSIGNMENT + '__left_one_way_obstructed'
            context['lane_allocation'] = 'one_way'
            path.write_text(json.dumps(context), encoding='utf-8')
            hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'authority'):
                saved.measure(attempt, hashes, case_id=context['case_id'], assignment_id=ASSIGNMENT)
            context['one_way_authority'] = {'source_ref': 'original traffic order', 'sha256': 'a' * 64}
            path.write_text(json.dumps(context), encoding='utf-8')
            hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(saved.measure(attempt, hashes, case_id=context['case_id'],
                                           assignment_id=ASSIGNMENT)['lane_allocation'], 'one_way')

    def test_rejects_timestamp_drift_and_observes_target_miss(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt = Path(temp)
            hashes = fixture(attempt)
            path = attempt / 'frames.jsonl'
            frames = [json.loads(line) for line in path.read_text().splitlines()]
            frames[1]['timestamp_s'] = 0.07
            path.write_text('\n'.join(json.dumps(row) for row in frames) + '\n', encoding='utf-8')
            hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, '20 Hz'):
                saved.measure(attempt, hashes, case_id=CASE, assignment_id=ASSIGNMENT)
            frames[1]['timestamp_s'] = 0.05
            frames[0]['ego_body_corners_signed_m'] = [-1, -0.5, -0.1, -0.2]
            frames[1]['ego_body_corners_signed_m'] = [-1, -0.5, -0.1, -0.2]
            frames[2]['ego_body_corners_signed_m'] = [-1, -0.5, -0.1, -0.2]
            path.write_text('\n'.join(json.dumps(row) for row in frames) + '\n', encoding='utf-8')
            hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertFalse(saved.measure(attempt, hashes, case_id=CASE,
                                           assignment_id=ASSIGNMENT)['construction_target_observed'])


if __name__ == '__main__':
    unittest.main()
