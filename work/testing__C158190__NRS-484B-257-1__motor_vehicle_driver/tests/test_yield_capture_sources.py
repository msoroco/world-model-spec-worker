import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from yield_capture_sources import ApproachSourceWriter, SightWriter, observe_sight


class Point:
    def __init__(self, x=0, y=0, z=0):
        self.x, self.y, self.z = x, y, z

    def distance(self, other):
        return ((self.x-other.x)**2 + (self.y-other.y)**2 + (self.z-other.z)**2)**.5


class Transform:
    location = Point(-20, 1.8, .25)

    def transform(self, point):
        return Point(self.location.x+point.x, self.location.y+point.y,
                     self.location.z+point.z)


class Actor:
    id = 1
    bounding_box = type('Box', (), {'contains': lambda self, point, transform: False})()

    def get_transform(self):
        return Transform()

    def get_velocity(self):
        return Point(3, 4, 0)


class World:
    frame = 100
    hits = []

    def get_snapshot(self):
        return type('Snapshot', (), {'frame': self.frame})()

    def get_map(self):
        return self

    def get_waypoint(self, point, project_to_road=False):
        assert project_to_road is False
        if point.x < 0:
            values = (158190, -1, 0)
        else:
            values = (158195, -1, 158191)
        return type('Waypoint', (), dict(zip(('road_id', 'lane_id', 'junction_id'), values)))()

    def cast_ray(self, eye, target):
        return self.hits


class CaptureTests(unittest.TestCase):
    def test_clear_road_without_through_actor_and_blocked_road(self):
        world = World()
        ray, sample = observe_sight(world, Actor(), None, 100, 5., location_factory=Point)
        self.assertTrue(ray['clear'])
        self.assertEqual(sample['visible_through_vehicle_ids'], [])
        self.assertEqual(ray['distance_to_intersection_m'], 12.)
        world.frame = 101
        world.hits = [type('Hit', (), {'location': Point(-10, 0, 1), 'label': 'Building'})()]
        blocked, blocked_sample = observe_sight(world, Actor(), None, 101, 5.05,
                                                 location_factory=Point)
        self.assertFalse(blocked_sample['through_highway_visible'])
        self.assertEqual(blocked['blockers'][0]['label'], 'Building')
        with tempfile.TemporaryDirectory() as directory:
            writer = SightWriter(directory)
            writer.add(ray, sample)
            writer.add(blocked, blocked_sample)
            writer.close()
            self.assertEqual(len(Path(directory, 'visibility_rays.jsonl').read_text().splitlines()), 2)
            self.assertEqual(json.loads(Path(directory, 'visibility_samples.json').read_text())[1]['frame'], 101)

    def test_rejects_stale_frame_target_and_relation(self):
        world = World()
        with self.assertRaisesRegex(ValueError, 'current Native frame'):
            observe_sight(world, Actor(), None, 99, 5., location_factory=Point)
        wrong_actor = type('Through', (), {'id': 2})()
        with self.assertRaisesRegex(ValueError, 'different actor IDs'):
            observe_sight(world, Actor(), wrong_actor, 100, 5., location_factory=Point,
                          visible_relation=lambda *args: {'a': 1, 'b': 3, 'visible': True})
        world.get_waypoint = lambda *args, **kwargs: type('Waypoint', (),
            {'road_id': 158194, 'lane_id': -1, 'junction_id': 0})()
        with self.assertRaisesRegex(ValueError, 'outside the sign-governed approach'):
            observe_sight(world, Actor(), None, 100, 5., location_factory=Point)

    def test_writer_rejects_duplicate_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = SightWriter(directory)
            writer.add({'frame': 1}, {'frame': 1})
            with self.assertRaisesRegex(ValueError, 'must increase'):
                writer.add({'frame': 1}, {'frame': 1})

    def test_original_speed_and_camera_frame_join(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = ApproachSourceWriter(directory)
            world = World()
            writer.add(world, Actor(), None, 100, 5., 0, location_factory=Point)
            world.frame = 101
            with self.assertRaisesRegex(ValueError, 'Camera frame index'):
                writer.add(world, Actor(), None, 101, 5.05, 2, location_factory=Point)
            writer.add(world, Actor(), None, 101, 5.05, 1, location_factory=Point)
            writer.add_nonapproach_frame(102, 5.10, 2)
            writer.close()
            rows = [json.loads(line) for line in
                    Path(directory, 'approach_history.jsonl').read_text().splitlines()]
            self.assertEqual([row['ego_speed_mps'] for row in rows], [5., 5.])
            frames = [json.loads(line) for line in
                      Path(directory, 'video_frames.jsonl').read_text().splitlines()]
            self.assertEqual([row['video_frame'] for row in frames], [0, 1, 2])
