import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scene_inventory import capture


class Actor:
    def __init__(self, ident, kind, x, state=None):
        self.id, self.type_id, self.x, self.state = ident, kind, x, state

    def get_transform(self):
        return types.SimpleNamespace(location=types.SimpleNamespace(
            x=self.x, y=0.0, z=0.0))

    def get_state(self):
        return self.state


class World:
    def __init__(self, actors):
        self.actors = actors

    def get_actors(self):
        return self.actors


class SceneInventoryTest(unittest.TestCase):
    def test_retains_in_radius_vehicle_and_light_with_original_state(self):
        ego = Actor(1, 'vehicle.ego', 0.0)
        world = World([Actor(8, 'vehicle.hazard', 9.0),
                       Actor(5, 'traffic.traffic_light', 15.0, 'Red'),
                       Actor(9, 'vehicle.distant', 101.0),
                       Actor(3, 'walker.pedestrian', 2.0), ego])
        result = capture(world, ego)
        self.assertEqual([row['actor_id'] for row in result['actors']], [1, 5, 8])
        self.assertEqual(result['actors'][1]['state'], 'Red')
        self.assertIn('no legal or physical absence claim', result['interpretation'])

    def test_rejects_unavailable_or_duplicate_inventory(self):
        ego = Actor(1, 'vehicle.ego', 0.0)
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            capture(World(None), ego)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            capture(World([ego, Actor(1, 'vehicle.other', 2.0)]), ego)


if __name__ == '__main__':
    unittest.main()
