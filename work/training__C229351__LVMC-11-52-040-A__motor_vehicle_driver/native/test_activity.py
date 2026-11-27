import unittest
from types import SimpleNamespace

from activity import spawn, control


class FakeBlueprint:
    def __init__(self):
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


class FakeActor:
    def __init__(self):
        self.location = SimpleNamespace(x=7.8, y=-6.0)
        self.controls = []

    def get_location(self):
        return self.location

    def apply_control(self, value):
        self.controls.append(value)


class FakeWorld:
    def __init__(self):
        self.blueprint = FakeBlueprint()
        self.actor = FakeActor()
        self.spawn_calls = []

    def get_blueprint_library(self):
        return self

    def find(self, name):
        assert name == 'walker.pedestrian.0001'
        return self.blueprint

    def spawn_actor(self, bp, transform):
        self.spawn_calls.append((bp, transform))
        return self.actor


class FakeCarla:
    @staticmethod
    def Location(**kwargs):
        return kwargs

    @staticmethod
    def Transform(location):
        return location

    @staticmethod
    def Vector3D(x, y, z):
        return SimpleNamespace(x=x, y=y, z=z)

    @staticmethod
    def WalkerControl(**kwargs):
        return SimpleNamespace(**kwargs)


class ActivityTest(unittest.TestCase):
    def test_standing_creates_and_controls_passenger(self):
        world = FakeWorld()
        passenger = spawn({'activity_requested': 'standing'}, world, FakeCarla)
        self.assertEqual(len(world.spawn_calls), 1)
        self.assertEqual(world.blueprint.attributes['role_name'], 'c229351_passenger')
        self.assertEqual(control(passenger, 1, FakeCarla), 'approach_vehicle')
        self.assertGreater(passenger.controls[-1].speed, 0)
        self.assertEqual(control(passenger, 10, FakeCarla), 'at_vehicle_side')
        self.assertEqual(passenger.controls[-1].speed, 0)

    def test_parking_has_no_passenger(self):
        world = FakeWorld()
        passenger = spawn({'activity_requested': 'parking'}, world, FakeCarla)
        self.assertIsNone(passenger)
        self.assertEqual(world.spawn_calls, [])
        self.assertEqual(control(passenger, 1, FakeCarla), 'no_passenger_request')


if __name__ == '__main__':
    unittest.main()
