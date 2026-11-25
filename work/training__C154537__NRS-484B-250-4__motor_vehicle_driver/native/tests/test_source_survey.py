"""CPU checks for authored geometry inventory and original ray sample shape."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

NATIVE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NATIVE))
from runner import authored_survey, view_sample


class Vec:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z

    def distance(self, other):
        return sum((a - b) ** 2 for a, b in zip(
            (self.x, self.y, self.z), (other.x, other.y, other.z))) ** .5


class Pose:
    location = Vec(-12, -1.75, 1.5)

    def transform(self, point):
        return Vec(self.location.x + point.x, self.location.y + point.y,
                   self.location.z + point.z)


class Box:
    def get_world_vertices(self, pose):
        return [Vec(1, -12, 1)] * 8

    def contains(self, location, pose):
        return False


class Actor:
    id = 7
    bounding_box = Box()

    def __init__(self, pose):
        self.pose = pose

    def get_transform(self):
        return self.pose


class OtherPose:
    location = Vec(1, -12, 1.5)


class Carla:
    Location = Vec


class World:
    def __init__(self, blocked):
        self.blocked = blocked

    def cast_ray(self, eye, endpoint):
        if self.blocked:
            return [type('Hit', (), {'location': Vec(-5, -6, 1.5),
                                      'label': 'building'})()]
        return []


class SurveyTest(unittest.TestCase):
    def test_authored_inventory_rejects_crossing_geometry(self):
        source = (NATIVE / 'crossroads.xodr').read_text()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'road.xodr'
            path.write_text(source)
            survey = authored_survey(path)
            self.assertEqual(survey['objects'], 0)
            self.assertEqual(survey['sidewalk_lanes'], 0)
            self.assertTrue(survey['authoring_absence_only'])
            path.write_text(source.replace('<objects />',
                '<objects><object id="crossing" type="crosswalk" /></objects>', 1))
            with self.assertRaisesRegex(ValueError, 'crossing geometry'):
                authored_survey(path)
            path.write_text(source.replace('type="driving"', 'type="sidewalk"', 1))
            with self.assertRaisesRegex(ValueError, 'crossing geometry'):
                authored_survey(path)
            path.write_text(source.replace('701', 'wrong-head', 1))
            with self.assertRaisesRegex(ValueError, 'signal inventory'):
                authored_survey(path)

    def test_ray_sample_preserves_clear_and_blocked(self):
        ego, other = Actor(Pose()), Actor(OtherPose())
        clear = view_sample(World(False), ego, other, Carla, 42)
        blocked = view_sample(World(True), ego, other, Carla, 43)
        self.assertEqual(clear['native_frame'], 42)
        self.assertEqual(len(clear['rays']), 9)
        self.assertTrue(clear['approaching_traffic_visible'])
        self.assertFalse(blocked['approaching_traffic_visible'])
        self.assertEqual(blocked['rays'][0]['blockers'][0]['label'], 'building')
        json.dumps(blocked)


if __name__ == '__main__':
    unittest.main()
