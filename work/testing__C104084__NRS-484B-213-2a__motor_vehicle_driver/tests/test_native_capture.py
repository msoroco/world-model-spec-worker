import importlib.util
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
    def __init__(self, *, broken_camera=False, broken_lane=False):
        self.frame = -1
        self.closed = False
        self.broken_camera = broken_camera
        self.broken_lane = broken_lane

    def begin(self, case):
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


if __name__ == '__main__':
    unittest.main()
