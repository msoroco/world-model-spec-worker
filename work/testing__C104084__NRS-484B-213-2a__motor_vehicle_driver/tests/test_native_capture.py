import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native_capture', ROOT / 'native_capture.py')
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)
saved_spec = importlib.util.spec_from_file_location('saved_crest_capture_join', ROOT / 'saved_crest.py')
saved = importlib.util.module_from_spec(saved_spec)
saved_spec.loader.exec_module(saved)
ASSIGNMENT = ROOT.name
CASE = ASSIGNMENT + '__left_crest_obstructed'


class FakeAdapter:
    def __init__(self, *, broken_camera=False, broken_lane=False, authority_root=None,
                 broken_authority=False):
        self.frame = -1
        self.closed = False
        self.broken_camera = broken_camera
        self.broken_lane = broken_lane
        self.authority_root = authority_root
        self.broken_authority = broken_authority

    def begin(self, case):
        if case.endswith('left_one_way_obstructed'):
            authority = self.authority_root / capture.ONE_WAY_AUTHORITY
            authority.write_text('{"designation":"source fixture"}\n', encoding='utf-8')
            return {'case_id': case, 'law_id': 'NRS-484B-213-2a',
                    'highway_source_ref': 'Native public-road context',
                    'center_reference_source_ref': 'Native road center',
                    'lane_allocation': 'one_way',
                    'one_way_authority': {
                        'source_ref': 'source fixture',
                        'sha256': 'a' * 64 if self.broken_authority else
                        hashlib.sha256(authority.read_bytes()).hexdigest()}}
        return {'case_id': case, 'law_id': 'NRS-484B-213-2a',
                'highway_source_ref': 'Native public-road context',
                'center_reference_source_ref': 'Native road center',
                'opposing_lane_source_ref': None if self.broken_lane else 'Native opposing lane',
                'lane_allocation': 'two_way'}

    def tick(self):
        self.frame += 1
        return self.frame

    def sample(self, frame):
        return ({'frame': frame, 'timestamp_s': frame / 20,
                 'ego_body_corners_signed_m': [-1, -0.5, 0.1, 0.2],
                 'opposing_body_distance_m': 25,
                 'ego_source_ref': 'Native ego', 'opposing_source_ref': 'Native other'},
                {'frame': frame, 'body_corner_ray_hits': [True] * 4,
                 'ray_source_ref': 'Native raycast'})

    def camera_frames(self, frame):
        result = {name: frame for name in capture.CAMERAS}
        if self.broken_camera:
            result['left'] = frame - 1
        return result

    def write_camera_video(self, camera, path):
        path.write_bytes(f'fake {camera}'.encode())

    def close(self):
        self.closed = True


class NativeCaptureTests(unittest.TestCase):
    def test_writes_exact_original_join_and_closes(self):
        with tempfile.TemporaryDirectory() as temp:
            adapter = FakeAdapter()
            receipt = capture.capture(adapter, temp, assignment_id=ASSIGNMENT,
                                      case_id=CASE, frames=3)
            self.assertTrue(adapter.closed)
            self.assertEqual(receipt['frame_count'], 3)
            self.assertEqual(len(receipt['source_sha256']), 8)
            frame_map = json.loads((Path(temp) / 'frame-map.json').read_text())
            self.assertEqual(frame_map['camera_frames']['left'], [0, 1, 2])
            self.assertFalse(receipt['physical_visibility_reviewed'])
            observation = saved.measure(temp, receipt['source_sha256'],
                                        case_id=CASE, assignment_id=ASSIGNMENT,
                                        expected_frames=3)
            self.assertTrue(observation['construction_target_observed'])

    def test_missing_camera_or_lane_rejected_with_cleanup(self):
        for defect in ('broken_camera', 'broken_lane'):
            with tempfile.TemporaryDirectory() as temp:
                adapter = FakeAdapter(**{defect: True})
                with self.assertRaises(ValueError):
                    capture.capture(adapter, temp, assignment_id=ASSIGNMENT,
                                    case_id=CASE, frames=3)
                self.assertTrue(adapter.closed)

    def test_wrong_exact_case_rejected(self):
        adapter = FakeAdapter()
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, 'wrong exact crest case'):
                capture.capture(adapter, temp, assignment_id=ASSIGNMENT,
                                case_id=ASSIGNMENT + '__invented', frames=3)

    def test_rejects_existing_attempt_without_rewriting_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            prior = Path(temp) / 'frames.jsonl'
            prior.write_text('retained original\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'fresh empty output'):
                capture.capture(FakeAdapter(), temp, assignment_id=ASSIGNMENT,
                                case_id=CASE, frames=3)
            self.assertEqual(prior.read_text(encoding='utf-8'), 'retained original\n')

    def test_one_way_authority_bytes_bound_before_capture(self):
        case = ASSIGNMENT + '__left_one_way_obstructed'
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            adapter = FakeAdapter(authority_root=root)
            receipt = capture.capture(adapter, root, assignment_id=ASSIGNMENT,
                                      case_id=case, frames=3)
            self.assertTrue(adapter.closed)
            self.assertIn(capture.ONE_WAY_AUTHORITY, receipt['source_sha256'])
            self.assertEqual(saved.measure(root, receipt['source_sha256'],
                                           case_id=case, assignment_id=ASSIGNMENT,
                                           expected_frames=3)['lane_allocation'], 'one_way')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            adapter = FakeAdapter(authority_root=root, broken_authority=True)
            with self.assertRaisesRegex(ValueError, 'authority source file differs'):
                capture.capture(adapter, root, assignment_id=ASSIGNMENT,
                                case_id=case, frames=3)
            self.assertTrue(adapter.closed)


if __name__ == '__main__':
    unittest.main()
