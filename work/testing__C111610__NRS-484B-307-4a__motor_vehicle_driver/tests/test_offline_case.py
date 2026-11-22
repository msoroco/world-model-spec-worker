"""Portable construction checks included in each exact materialized bundle."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as N

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_capture import bind_map
from runner import control, load_scene


class Waypoint:
    def __init__(self, x, y):
        self.transform = N(location=N(x=x, y=y, z=0))
        self.road_id = self.lane_id = 1
        self.following = []
    def next(self, _distance): return self.following


class OfflineCase(unittest.TestCase):
    def test_connected_left_turn_crosses_original_marked_crosswalk(self):
        scene = load_scene()
        points = [Waypoint(-20, -1.75), Waypoint(-4, -1.75),
                  Waypoint(0, 0), Waypoint(0, 20)]
        for first, following in zip(points, points[1:]):
            first.following = [following]
        if scene.get('other_traffic_setup') == 'lawful_entered':
            other_start, other_end = Waypoint(0, -12), Waypoint(0, 10)
            other_start.following = [points[2]]
            points[2].following.append(other_end)
            other_end.following = [points[3]]
            points.extend((other_start, other_end))
        crosswalk = [N(x=x, y=y, z=0) for x, y in
                     [(-2, 4), (2, 4), (2, 8), (-2, 8)]]
        mapping = N(name='CPU fixture map', get_crosswalks=lambda: crosswalk,
                    get_waypoint=lambda location: min(points, key=lambda p:
                        abs(p.transform.location.x - location.x) +
                        abs(p.transform.location.y - location.y)))
        world = N(get_map=lambda: mapping)
        carla = N(Location=lambda x, y, z: N(x=x, y=y, z=z))
        self.assertEqual(len(bind_map(world, carla, scene)['route_waypoints']), 4)
        points[2].following = []
        with self.assertRaisesRegex(ValueError, 'connected left turn'):
            bind_map(world, carla, scene)

    def test_facing_arrow_and_hold_or_turn(self):
        scene = load_scene()
        signal = {'source_verified': True, 'source_ref': 'Native head asset',
                  'head_id': scene['facing_head_id'], 'observed_frame': 100,
                  'illuminated_indications': [{'color': 'green', 'shape': 'arrow',
                                               'direction': 'left'}]}
        ego = [[-10, -1.75, 0], [-9, -1.75, 0],
               [-9, -.75, 0], [-10, -.75, 0]]
        person = {'id': 1, 'role': 'pedestrian', 'source_ref': 'Native walker',
                  'lawfully_present': True,
                  'lawful_presence_source': 'pedestrian-entry.jsonl and original Walk head',
                  'body_vertices_m': [[0, 5, 0], [1, 5, 0], [1, 6, 0], [0, 6, 0]]}
        if scene.get('other_traffic_setup') == 'lawful_entered':
            traffic = [{'id': 3, 'source_ref': 'Native CARLA vehicle 3',
                'lawful_presence_source': 'traffic-entry.jsonl and original green head',
                'lawfully_using_intersection': True}]
            self.assertEqual(control(scene, signal, 100, ego, [], traffic, 0)['brake'], 1)
        elif scene['crosswalk_setup'] == 'occupied':
            self.assertEqual(control(scene, signal, 100, ego, [person], [], 0)['brake'], 1)
        else:
            self.assertEqual(control(scene, signal, 100, ego, [], [], 0)['throttle'], .2)
        signal['head_id'] += 1
        with self.assertRaisesRegex(ValueError, 'ego-facing'):
            control(scene, signal, 100, ego, [], [], 0)
