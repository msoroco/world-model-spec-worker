import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as S

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_samples import sample


class Actor:
    def __init__(self, actor_id, x):
        self.id = actor_id
        self.is_alive = True
        self.location = S(x=x, y=0, z=0, lane_id=-1)
        self.bounding_box = S(get_world_vertices=lambda transform: [
            S(x=x-1, y=-1, z=0), S(x=x-1, y=1, z=0),
            S(x=x+1, y=-1, z=0), S(x=x+1, y=1, z=0)])

    def get_transform(self):
        return S(location=self.location)

    def get_velocity(self):
        return S(x=9, y=0, z=0)

    def get_physics_control(self):
        return S(wheels=[S(tire_friction=2.0)]*4)


class World:
    def __init__(self, traffic):
        self.traffic = traffic

    def get_weather(self):
        return S(fog_density=10, precipitation=20)

    def get_actors(self):
        return S(filter=lambda pattern: self.traffic)


class Map:
    def get_waypoint(self, location):
        return S(road_id=12, lane_id=location.lane_id)


class NativeSampleTest(unittest.TestCase):
    def test_binds_original_sources_and_lane_transition(self):
        ego, leader, neighbor = Actor(1, 10), Actor(2, 30), Actor(3, 40)
        world = World([ego, leader, neighbor])
        row = sample(world, Map(), ego, leader, frame=280, relative_time_s=14,
                     following_lane_id=-1)
        self.assertEqual(row['surrounding_vehicle_count'], 2)
        self.assertEqual(row['highway_condition']['observed_tire_friction'], 2)
        self.assertFalse(row['lane_change']['started'])
        ego.location.lane_id = -2
        row = sample(world, Map(), ego, leader, frame=440, relative_time_s=22,
                     following_lane_id=-1)
        self.assertTrue(row['lane_change']['started'])

    def test_rejects_early_change_and_missing_wheels(self):
        ego, leader = Actor(1, 10), Actor(2, 30)
        ego.location.lane_id = -2
        with self.assertRaisesRegex(ValueError, 'before steady window'):
            sample(World([ego, leader]), Map(), ego, leader, frame=300,
                   relative_time_s=15, following_lane_id=-1)
        ego.location.lane_id = -1
        ego.get_physics_control = lambda: S(wheels=[])
        with self.assertRaisesRegex(ValueError, 'wheel friction unavailable'):
            sample(World([ego, leader]), Map(), ego, leader, frame=300,
                   relative_time_s=15, following_lane_id=-1)


if __name__ == '__main__':
    unittest.main()
