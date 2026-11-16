"""Exercise passenger creation and control calls with a lazy CARLA double."""
from types import SimpleNamespace
import unittest
from passenger_spawn import control, spawn


class Actor:
    def __init__(self):
        self.controls = []

    def apply_control(self, item):
        self.controls.append(item)


class World:
    def __init__(self, actor):
        self.actor = actor
        self.request = None

    def try_spawn_actor(self, blueprint, transform):
        self.request = (blueprint, transform)
        return self.actor


class Library:
    def filter(self, query):
        if query != 'walker.pedestrian.*':
            raise AssertionError('Wrong pedestrian blueprint filter')
        return ['walker.pedestrian.0001']


def carla_double():
    return SimpleNamespace(
        Location=lambda **kw: SimpleNamespace(**kw),
        Rotation=lambda **kw: SimpleNamespace(**kw),
        Transform=lambda location, rotation: SimpleNamespace(
            location=location, rotation=rotation),
        Vector3D=lambda x, y, z: (x, y, z),
        WalkerControl=lambda **kw: SimpleNamespace(**kw))


class PassengerSpawnProof(unittest.TestCase):
    def test_actor_creation_and_movement_window(self):
        actor = Actor()
        world = World(actor)
        carla = carla_double()
        self.assertIs(spawn(world, Library(), carla), actor)
        self.assertEqual(world.request[0], 'walker.pedestrian.0001')
        self.assertEqual((world.request[1].location.x,
                          world.request[1].location.y), (40, -10))
        self.assertFalse(control(actor, carla, 119, 120)['requested_walking'])
        self.assertTrue(control(actor, carla, 120, 120)['requested_walking'])
        self.assertTrue(control(actor, carla, 179, 120)['requested_walking'])
        self.assertFalse(control(actor, carla, 180, 120)['requested_walking'])
        self.assertEqual([item.speed for item in actor.controls], [0, 1, 1, 0])
        self.assertTrue(all(item.direction == (0, 1, 0) for item in actor.controls))
        with self.assertRaisesRegex(ValueError, 'passenger control'):
            control(actor, carla, -1, 120)

    def test_rejects_missing_actor(self):
        with self.assertRaisesRegex(RuntimeError, 'spawn failed'):
            spawn(World(None), Library(), carla_double())


if __name__ == '__main__':
    unittest.main()
