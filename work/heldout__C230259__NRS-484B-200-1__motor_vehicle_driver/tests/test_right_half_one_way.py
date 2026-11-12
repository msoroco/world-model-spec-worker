"""One-way lane direction, sign source and undecided authority controls."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from right_half_one_way import OneWayRoadRecorder, same_direction_left
from right_half_measurement import measure


class Point:
    def __init__(self, x, y, z=0):
        self.x, self.y, self.z = x, y, z


class Transform:
    def __init__(self, x, y, direction):
        self.location = Point(x, y)
        self.direction = direction

    def get_forward_vector(self):
        return Point(*self.direction)


class Lane:
    lane_type = 'Driving'
    lane_width = 3.5
    road_id = 7

    def __init__(self, y, direction, lane_id):
        self.transform = Transform(0, y, direction)
        self.lane_id = lane_id
        self.left = self.right = None

    def get_left_lane(self):
        return self.left

    def get_right_lane(self):
        return self.right


def pair():
    right = Lane(-1.75, (1, 0), -1)
    left = Lane(1.75, (1, 0), -2)
    right.left, left.right = left, right
    return right, left


class Actor:
    def __init__(self, y):
        self.y = y
        self.bounding_box = self

    def get_transform(self):
        return object()

    def get_world_vertices(self, transform):
        return [Point(x, self.y + dy, z) for z in (0, 1.5)
                for x, dy in ((-1, -.6), (1, -.6), (1, .6), (-1, .6))]


class Sign:
    id = 34
    type_id = 'static.prop.oneway_sign'

    def get_transform(self):
        return Transform(5, -4, (1, 0))


class OneWayTest(unittest.TestCase):
    def test_direction_and_extra_lane_controls(self):
        right, left = pair()
        self.assertIs(same_direction_left(right), left)
        left.transform.direction = (-1, 0)
        with self.assertRaisesRegex(ValueError, 'another direction'):
            same_direction_left(right)
        right, left = pair()
        left.left = Lane(5.25, (1, 0), -3)
        with self.assertRaisesRegex(ValueError, 'additional driving lane'):
            same_direction_left(right)

    def test_original_sign_and_body_sources(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            recorder = OneWayRoadRecorder(root, Sign())
            for frame in (10, 11):
                recorder.append(Actor(1.75), pair()[0], frame, (frame - 10) / 20)
            with self.assertRaisesRegex(ValueError, 'continuous'):
                recorder.append(Actor(1.75), pair()[0], 13, .15)
            recorder.close()
            context = {key: {'value': None, 'source_ref': None} for key in (
                'passing_same_direction', 'right_half_closed', 'three_lane_highway',
                'posted_one_way', 'insufficient_width')}
            (root / 'road_exception_context.json').write_text(json.dumps(context) + '\n')
            value = measure(root / 'ego_road_frames.jsonl', root / 'road_exception_context.json')
            self.assertTrue(all(row['whole_body_left_half'] for row in value['observations']))
            sign = json.loads((root / 'one_way_sign.jsonl').read_text().splitlines()[0])
            self.assertFalse(sign['designation_verified'])
            self.assertFalse(sign['posting_authority_verified'])
