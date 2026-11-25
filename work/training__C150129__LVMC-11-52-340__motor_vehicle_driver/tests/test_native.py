import unittest

from geometry import check as geometry_check
from runner import check as runner_check, spawn_posting_marker, survey


class FakeCarla:
    class LaneType:
        Parking = 'parking'

    class Location:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z

    class Rotation:
        def __init__(self, yaw):
            self.yaw = yaw

    class Transform:
        def __init__(self, location, rotation):
            self.location, self.rotation = location, rotation


class FakeWaypoint:
    def __init__(self, x, y, wrong=False):
        self.road_id, self.lane_id, self.lane_type = 1, -1 if wrong else -2, 'parking'
        self.transform = type('T', (), {'location': FakeCarla.Location(x, y, 8)})()


class FakeWorld:
    def __init__(self, wrong=False):
        self.wrong = wrong

    def get_map(self):
        return self

    def get_waypoint(self, location, project_to_road, lane_type):
        return FakeWaypoint(location.x, location.y, self.wrong)


class NativeDraft(unittest.TestCase):
    def test_geometry_and_camera_plan(self):
        self.assertEqual(geometry_check()['lane_types'], ['driving', 'parking'])
        self.assertEqual(runner_check()['frames'], 600)
        self.assertEqual(len(runner_check()['camera_names']), 4)
        self.assertFalse(runner_check()['physical_acceptance_claimed'])

    def test_parking_lane_survey_gate(self):
        self.assertEqual(len(survey(FakeWorld(), FakeCarla)), 4)
        with self.assertRaisesRegex(RuntimeError, 'readback failed'):
            survey(FakeWorld(wrong=True), FakeCarla)

    def test_physical_posting_marker_spawn_and_absence(self):
        class Blueprint:
            id = 'static.prop.streetsign'

        class Library:
            def __init__(self, present):
                self.present = present

            def filter(self, pattern):
                self.pattern = pattern
                return [Blueprint()] if self.present else []

        class World:
            def __init__(self, present):
                self.library = Library(present)
                self.spawned = []

            def get_blueprint_library(self):
                return self.library

            def try_spawn_actor(self, blueprint, transform):
                self.spawned.append((blueprint, transform))
                return type('Marker', (), {'id': 17, 'type_id': blueprint.id})()

        world = World(True)
        self.assertEqual(spawn_posting_marker(world, FakeCarla).id, 17)
        self.assertEqual(world.library.pattern, 'static.prop.*')
        self.assertEqual(world.spawned[0][1].location.y, -8.2)
        with self.assertRaisesRegex(RuntimeError, 'street-sign prop blueprint'):
            spawn_posting_marker(World(False), FakeCarla)
