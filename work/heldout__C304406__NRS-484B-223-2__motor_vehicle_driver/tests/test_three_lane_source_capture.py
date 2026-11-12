import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from three_lane_measurement import measure
from three_lane_source_capture import ThreeLaneSourceRecorder
from test_three_lane_route import corridor


class Ego:
    id = 99

    def __init__(self, y):
        self.y = y
        self.bounding_box = NS(get_world_vertices=lambda transform: [
            NS(x=x, y=self.y + dy) for x, dy in
            ((-1, -0.7), (1, -0.7), (1, 0.7), (-1, 0.7))])

    def get_transform(self):
        return NS()


class ThreeLaneSourceTests(unittest.TestCase):
    def test_retained_original_body_and_lane_sources_feed_measurement(self):
        _, route = corridor()
        ego = Ego(0)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            recorder = ThreeLaneSourceRecorder(root, route[0], ego)
            recorder.append(101, 5.0)
            ego.y = 3.5
            recorder.append(102, 5.05)
            result = measure(root / 'three_lane_frames.jsonl',
                             root / 'three_lane_context.json')
            self.assertGreater(result['observations'][0]['body_lane_overlap_fraction']['right'], 0.95)
            self.assertGreater(result['observations'][1]['body_lane_overlap_fraction']['center'], 0.95)
            self.assertIsNone(result['condition_context']['three_clearly_marked_lanes']['value'])
            self.assertTrue(json.loads((root / 'three_lane_map_readback.json').read_text())['map_markings_verified'])
            with self.assertRaises(FileExistsError):
                ThreeLaneSourceRecorder(root, route[0], ego)

    def test_discontinuous_frames_rejected_before_writing(self):
        _, route = corridor()
        with tempfile.TemporaryDirectory() as temp:
            recorder = ThreeLaneSourceRecorder(temp, route[0], Ego(0))
            recorder.append(10, 0.0)
            with self.assertRaisesRegex(ValueError, '20 Hz'):
                recorder.append(12, 0.1)
            self.assertEqual(len((Path(temp) / 'three_lane_frames.jsonl').read_text().splitlines()), 1)


if __name__ == '__main__':
    unittest.main()
