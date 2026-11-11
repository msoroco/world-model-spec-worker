import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from three_lane_measurement import CONDITIONS, measure


def rectangle(x0, x1, y0, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


class ThreeLaneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rows = [{'frame': 10 + i, 'time_s': i * .05,
                      'road_id': 1, 'road_travel_tangent_xy': [1, 0],
                      'ego_corners_xy': rectangle(i, i + 2, -.5, .5),
                      'lane_polygons_xy': {
                          'right': rectangle(-10, 20, -5, -2),
                          'center': rectangle(-10, 20, -2, 2),
                          'extreme_left': rectangle(-10, 20, 2, 5)}}
                     for i in range(2)]
        self.context = {name: {'value': None, 'source_ref': None} for name in CONDITIONS}

    def write(self):
        (self.root / 'three_lane_frames.jsonl').write_text(
            ''.join(json.dumps(row) + '\n' for row in self.rows))
        (self.root / 'three_lane_context.json').write_text(json.dumps(self.context))

    def result(self):
        return measure(self.root / 'three_lane_frames.jsonl',
                       self.root / 'three_lane_context.json')

    def test_center_occupancy_and_westbound_lane_order(self):
        self.write()
        result = self.result()
        self.assertEqual(result['observations'][0]['body_lane_overlap_fraction']['center'], 1)
        self.assertIsNone(result['center_lane_exception_legal_judgment'])
        for row in self.rows:
            row['road_travel_tangent_xy'] = [-1, 0]
            row['lane_polygons_xy']['right'], row['lane_polygons_xy']['extreme_left'] = (
                row['lane_polygons_xy']['extreme_left'], row['lane_polygons_xy']['right'])
        self.write()
        self.assertEqual(self.result()['observations'][0]['body_lane_overlap_fraction']['center'], 1)

    def test_extreme_left_overlap_and_bad_lane_order(self):
        self.rows[0]['ego_corners_xy'] = rectangle(0, 2, 3, 4)
        self.write()
        self.assertTrue(self.result()['observations'][0]['extreme_left_body_overlap'])
        self.rows[0]['lane_polygons_xy']['right'], self.rows[0]['lane_polygons_xy']['extreme_left'] = (
            self.rows[0]['lane_polygons_xy']['extreme_left'],
            self.rows[0]['lane_polygons_xy']['right'])
        self.write()
        with self.assertRaisesRegex(ValueError, 'lane order differs'):
            self.result()

    def test_uncited_allocation_or_missing_sign_context_rejected(self):
        self.context['center_allocated_same_direction']['value'] = True
        self.write()
        with self.assertRaisesRegex(ValueError, 'needs source'):
            self.result()
        self.context['center_allocated_same_direction']['source_ref'] = 'original sign and map review'
        del self.context['allocation_sign_posted']
        self.write()
        with self.assertRaisesRegex(ValueError, 'condition missing'):
            self.result()

    def test_missing_original_and_frame_gap_rejected(self):
        self.write()
        (self.root / 'three_lane_frames.jsonl').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing original source'):
            self.result()
        self.rows[1]['frame'] = 13
        self.write()
        with self.assertRaisesRegex(ValueError, 'not joined'):
            self.result()


if __name__ == '__main__':
    unittest.main()
