import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from three_lane_passing_finalizer import measure_passing_sources
from three_lane_source_capture import ThreeLaneSourceRecorder
from test_three_lane_route import corridor
from test_three_lane_source_capture import Ego


class PassingSavedSourcesTests(unittest.TestCase):
    def fixture(self, root):
        _, route = corridor()
        ego = Ego(3.5)
        recorder = ThreeLaneSourceRecorder(root, route[0], ego)
        passing = []
        for i in range(2):
            frame, time_s = 41 + i, i * .05
            recorder.append(frame, time_s)
            passing.append({'frame': frame, 'time_s': time_s,
                'ego_actor_id': '99', 'target_actor_id': '101',
                'ego_center_xy': [0, 3.5], 'target_center_xy': [2, 0],
                'target_corners_xy': [[1, -.6], [3, -.6], [3, .6], [1, .6]],
                'right_lane_center_xy': [0, 0], 'center_lane_center_xy': [0, 3.5],
                'other_vehicle_bodies': [{'actor_id': '101', 'center_xy': [2, 0],
                                          'half_length_m': 1, 'half_width_m': .6}],
                'clear_target_m': 60})
        (root / 'passing_frames.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in passing))
        (root / 'trace.jsonl').write_text('{}\n{}\n')
        (root / 'video_frames.jsonl').write_text('{}\n{}\n')
        return passing

    def test_source_bound_passing_actor_and_clear_center(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            result = measure_passing_sources(root)
            self.assertEqual(len(result['observations']), 2)
            self.assertTrue(result['observations'][0]['center_engineering_interval_clear'])
            self.assertGreater(result['observations'][0]['target_right_lane_fraction'], .95)
            self.assertIsNone(result['highway_clearly_visible'])

    def test_missing_source_and_wrong_target_lane_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            passing = self.fixture(root)
            (root / 'passing_frames.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source'):
                measure_passing_sources(root)
            passing[0]['target_corners_xy'] = [[1, 3], [3, 3], [3, 4], [1, 4]]
            (root / 'passing_frames.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in passing))
            with self.assertRaisesRegex(ValueError, 'left right lane'):
                measure_passing_sources(root)


if __name__ == '__main__':
    unittest.main()
