import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from right_half_measurement import EXCEPTIONS, measure


def square(x, y):
    return [[x - .5, y - .5], [x + .5, y - .5],
            [x + .5, y + .5], [x - .5, y + .5]]


class RightHalfTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.frames = [
            {'frame': 10 + i, 'time_s': i * .05,
             'ego_corners_xy': square(i, -2),
             'road_center_xy': [i, 0], 'road_travel_tangent_xy': [1, 0],
             'road_width_m': 8, 'road_id': 1, 'lane_id': -1}
            for i in range(2)]
        self.context = {key: {'value': None, 'source_ref': None} for key in EXCEPTIONS}

    def write(self):
        (self.root / 'ego_road_frames.jsonl').write_text(
            ''.join(json.dumps(row) + '\n' for row in self.frames))
        (self.root / 'road_exception_context.json').write_text(json.dumps(self.context))

    def result(self):
        return measure(self.root / 'ego_road_frames.jsonl',
                       self.root / 'road_exception_context.json')

    def test_right_half_both_travel_directions(self):
        self.write()
        result = self.result()
        self.assertTrue(all(row['whole_body_right_half'] for row in result['observations']))
        self.assertIsNone(result['right_half_legal_judgment'])
        for frame in self.frames:
            frame['road_travel_tangent_xy'] = [-1, 0]
            frame['ego_corners_xy'] = square(frame['road_center_xy'][0], 2)
        self.write()
        self.assertTrue(all(row['whole_body_right_half'] for row in self.result()['observations']))

    def test_centerline_crossing_and_separately_cited_exception(self):
        self.frames[0]['ego_corners_xy'] = square(0, 0)
        self.context['right_half_closed'] = {'value': True, 'source_ref': 'original lane closure review'}
        self.write()
        result = self.result()
        self.assertTrue(result['observations'][0]['body_crosses_centerline'])
        self.assertTrue(result['exception_context']['right_half_closed']['value'])
        self.context['right_half_closed']['source_ref'] = ''
        self.write()
        with self.assertRaisesRegex(ValueError, 'needs cited source'):
            self.result()

    def test_rejects_discontinuous_or_degenerate_original_geometry(self):
        self.frames[1]['frame'] = 13
        self.write()
        with self.assertRaisesRegex(ValueError, 'not continuous'):
            self.result()
        self.frames[1]['frame'] = 11
        self.frames[1]['road_travel_tangent_xy'] = [0, 0]
        self.write()
        with self.assertRaisesRegex(ValueError, 'degenerate'):
            self.result()

    def test_rejects_missing_exception_review(self):
        del self.context['posted_one_way']
        self.write()
        with self.assertRaisesRegex(ValueError, 'Missing separately reviewed exception'):
            self.result()


if __name__ == '__main__':
    unittest.main()
