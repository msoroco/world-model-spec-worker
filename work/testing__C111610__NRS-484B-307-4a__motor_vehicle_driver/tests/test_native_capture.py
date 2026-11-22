import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as N

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_capture import bind_map, bind_facing_arrow, observed_arrow, spawn_entities
from runner import load_scene


def point(x, y, z=0):
    return N(x=x, y=y, z=z)


class Waypoint:
    def __init__(self, x, y, road=1, lane=1):
        self.transform = N(location=point(x, y))
        self.road_id = road
        self.lane_id = lane
        self.following = []

    def next(self, distance):
        return self.following


class NativeBindingTests(unittest.TestCase):
    def setUp(self):
        self.scene = load_scene()
        points = [Waypoint(-20, -1.75), Waypoint(-4, -1.75),
                  Waypoint(0, 0), Waypoint(0, 20)]
        for first, second in zip(points, points[1:]):
            first.following = [second]
        self.points = points
        self.crosswalk = [point(-2, 4), point(2, 4), point(2, 8), point(-2, 8)]

    def world(self):
        points = self.points
        crosswalk = self.crosswalk
        mapping = N(name='fake Native map',
                    get_waypoint=lambda loc: min(points,
                        key=lambda wp: abs(wp.transform.location.x-loc.x) +
                                       abs(wp.transform.location.y-loc.y)),
                    get_crosswalks=lambda: crosswalk)
        return N(get_map=lambda: mapping)

    def test_connected_left_turn_and_marked_crosswalk_required(self):
        carla = N(Location=lambda x, y, z: point(x, y, z))
        bound = bind_map(self.world(), carla, self.scene)
        self.assertEqual(len(bound['route_waypoints']), 4)
        self.assertEqual(len(bound['crosswalk_vertices_m']), 4)
        self.points[2].following = []
        with self.assertRaisesRegex(ValueError, 'connected left turn'):
            bind_map(self.world(), carla, self.scene)
        self.points[2].following = [self.points[3]]
        self.crosswalk.clear()
        with self.assertRaisesRegex(ValueError, 'no marked adjacent crosswalk'):
            bind_map(self.world(), carla, self.scene)

    def test_facing_original_asset_and_green_frame_required(self):
        light = N(id=7, attributes={'signal_shape': 'arrow', 'arrow_direction': 'left',
                                    'sole_illuminated': 'true'}, get_state=lambda: 'Green')
        ego = N(get_traffic_light=lambda: light)
        self.assertIs(bind_facing_arrow(ego, self.scene), light)
        self.assertEqual(observed_arrow(light, self.scene, 120)['observed_frame'], 120)
        light.attributes['sole_illuminated'] = 'false'
        with self.assertRaisesRegex(ValueError, 'sole left arrow'):
            bind_facing_arrow(ego, self.scene)
        light.attributes['sole_illuminated'] = 'true'
        light.get_state = lambda: 'Red'
        with self.assertRaisesRegex(ValueError, 'not green'):
            observed_arrow(light, self.scene, 120)

    def test_distinct_spawn_and_cleanup_on_failure(self):
        class Actor:
            def __init__(self, id): self.id, self.destroyed = id, False
            def destroy(self): self.destroyed = True
        actors = [Actor(1), Actor(2)]
        issued = []
        def spawn(_blueprint, _transform):
            actor = actors[len(issued)]
            issued.append(actor)
            return actor
        world = N(spawn_actor=spawn)
        occupied = load_scene(ROOT / 'cases/crosswalk_occupied_yield/scene.json')
        self.assertEqual(spawn_entities(world, occupied, 'car', 'walker',
                         lambda x, y, yaw: (x, y, yaw)), actors)
        issued.clear()
        actors[1].id = 1
        with self.assertRaisesRegex(ValueError, 'not distinct'):
            spawn_entities(world, occupied, 'car', 'walker', lambda x, y, yaw: (x, y, yaw))
        self.assertTrue(all(a.destroyed for a in actors))
