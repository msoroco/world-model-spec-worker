"""Three-lane map direction, road center and full-body measurement controls."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from right_half_measurement import measure
from right_half_three_lane import (
    ThreeLaneRoadRecorder, sample_three_lane, select_three_lane_route,
    three_lane_neighbors, three_lane_targets,
)


class Point:
    def __init__(self, x, y, z=0):
        self.x, self.y, self.z = x, y, z


class Transform:
    def __init__(self, x, y, direction):
        self.location = Point(x, y)
        self.direction = direction

    def get_forward_vector(self):
        return Point(*self.direction)


class Actor:
    def __init__(self, y):
        self.y = y
        self.bounding_box = self

    def get_transform(self):
        return object()

    def get_world_vertices(self, transform):
        return [Point(x, self.y + dy, z) for z in (0, 1.5)
                for x, dy in ((-1, -.6), (1, -.6), (1, .6), (-1, .6))]


class Lane:
    lane_type = 'Driving'
    lane_width = 3.5
    road_id = 9
    is_junction = False

    def __init__(self, x, y, direction, lane_id):
        self.transform = Transform(x, y, direction)
        self.lane_id = lane_id
        self.left = self.right = self.following = None

    def get_left_lane(self):
        return self.left

    def get_right_lane(self):
        return self.right

    def next(self, spacing):
        return [self.following] if self.following is not None else []


def triplet(x=0):
    right = Lane(x, -3.5, (1, 0), -1)
    center = Lane(x, 0, (1, 0), -2)
    far = Lane(x, 3.5, (-1, 0), 1)
    right.left, center.right = center, right
    center.left, far.right = far, center
    return right, center, far


class ThreeLaneTest(unittest.TestCase):
    def test_three_lane_body_and_map_source(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            recorder = ThreeLaneRoadRecorder(root)
            for frame in (10, 11):
                recorder.append(Actor(3.5), triplet()[0], frame, (frame - 10) / 20)
            with self.assertRaisesRegex(ValueError, 'continuous'):
                recorder.append(Actor(3.5), triplet()[0], 13, .15)
            recorder.close()
            context = {key: {'value': None, 'source_ref': None} for key in (
                'passing_same_direction', 'right_half_closed', 'three_lane_highway',
                'posted_one_way', 'insufficient_width')}
            (root / 'road_exception_context.json').write_text(json.dumps(context) + '\n')
            value = measure(root / 'ego_road_frames.jsonl', root / 'road_exception_context.json')
            self.assertTrue(all(row['whole_body_left_half'] for row in value['observations']))
            first = json.loads((root / 'ego_road_frames.jsonl').read_text().splitlines()[0])
            self.assertEqual(first['road_center_xy'], [0., 0.])
            self.assertEqual(first['road_width_m'], 10.5)
            self.assertEqual(len(first['lane_inventory']), 3)

    def test_direction_and_extra_lane_rejected(self):
        right, center, far = triplet()
        self.assertEqual(three_lane_neighbors(right), (center, far))
        far.transform.direction = (1, 0)
        with self.assertRaisesRegex(ValueError, 'direction pattern'):
            three_lane_neighbors(right)
        right, center, far = triplet()
        far.left = Lane(0, 7, (-1, 0), 2)
        with self.assertRaisesRegex(ValueError, 'Additional driving lane'):
            three_lane_neighbors(right)

    def test_connected_route_and_left_targets(self):
        route = []
        for i in range(17):
            lane = triplet(i * 2.5)[0]
            if route:
                route[-1].following = lane
            route.append(lane)

        class Map:
            def get_spawn_points(self):
                return [route[0].transform]

            def get_waypoint(self, location):
                return route[0]

        chosen = select_three_lane_route(Map())
        targets = three_lane_targets(chosen)
        self.assertEqual(len(targets['targets_xy_m']), 17)
        self.assertTrue(all(point[1] == 3.5 for point in targets['targets_xy_m']))
        self.assertFalse(targets['applicable_lane_rule_verified'])
