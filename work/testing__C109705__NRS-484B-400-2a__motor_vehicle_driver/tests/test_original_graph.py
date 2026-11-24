import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from native_capture import _checked_graph
from original_graph import collect


def vector(x=0.0, y=0.0, z=0.0):
    return NS(x=x, y=y, z=z)


class Actor:
    def __init__(self, actor_id, x):
        self.id = actor_id
        self.type_id = 'vehicle.test'
        self.is_alive = True
        self.x = x
        self.bounding_box = NS(location=vector(), extent=vector(2, 1, 1),
                               get_world_vertices=lambda transform: [
                                   vector(transform.location.x + dx, dy, dz)
                                   for dx in (-2., 2.) for dy in (-1., 1.)
                                   for dz in (-1., 1.)])

    def get_transform(self):
        return NS(location=vector(self.x), rotation=NS(pitch=0, yaw=90, roll=0),
                  get_forward_vector=lambda: vector(0., 1., 0.))

    def get_velocity(self):
        return vector(3)


class World:
    def __init__(self, actors):
        self.actors = actors

    def get_actors(self):
        return self.actors


class OriginalGraphTests(unittest.TestCase):
    def setUp(self):
        self.ego = Actor(7, 12)
        self.other = Actor(9, 15)
        self.world = World([self.other, self.ego])
        self.snapshot = NS(frame=100, timestamp=NS(elapsed_seconds=5.0))

    def test_live_actor_state_and_original_identity(self):
        raw = collect(self.world, self.ego, self.snapshot,
                      expected_frame=100, expected_time_s=5.0)
        graph = _checked_graph(raw, 100, 5.0)
        self.assertEqual(graph['nodes'][0]['attributes']['actor_id'], 7)
        self.assertEqual(graph['nodes'][0]['attributes']['location_m'], [12, 0.0, 0.0])
        self.assertEqual(graph['nodes'][1]['attributes']['source_actor_id'], 9)
        self.assertEqual(graph['nodes'][0]['attributes']['sem_class'], 'vehicle.test')
        self.assertEqual(graph['nodes'][0]['attributes']['carla_id'], 7)
        self.assertEqual(len(graph['nodes'][0]['attributes']['threedbbox']), 8)
        self.assertNotIn('actor_id', graph['nodes'][1]['attributes'])
        self.assertEqual(graph['metadata']['source'], 'live_carla_world_snapshot')

    def test_stale_snapshot_rejected(self):
        self.snapshot.frame = 99
        with self.assertRaisesRegex(ValueError, 'snapshot frame/time differs'):
            collect(self.world, self.ego, self.snapshot,
                    expected_frame=100, expected_time_s=5.0)
        self.snapshot.frame = 100
        self.snapshot.timestamp.elapsed_seconds = 5.02
        with self.assertRaisesRegex(ValueError, 'snapshot frame/time differs'):
            collect(self.world, self.ego, self.snapshot,
                    expected_frame=100, expected_time_s=5.0)

    def test_missing_ego_and_duplicate_actor_rejected(self):
        self.ego.is_alive = False
        with self.assertRaisesRegex(ValueError, 'ego actor absent'):
            collect(self.world, self.ego, self.snapshot,
                    expected_frame=100, expected_time_s=5.0)
        self.ego.is_alive = True
        self.world.actors.append(Actor(9, 20))
        with self.assertRaisesRegex(ValueError, 'IDs duplicated'):
            collect(self.world, self.ego, self.snapshot,
                    expected_frame=100, expected_time_s=5.0)

    def test_nonfinite_source_rejected(self):
        self.other.x = float('nan')
        with self.assertRaisesRegex(ValueError, 'not finite'):
            collect(self.world, self.ego, self.snapshot,
                    expected_frame=100, expected_time_s=5.0)

    def test_camera_instruments_are_not_traffic_nodes(self):
        camera = NS(id=20, type_id='sensor.camera.rgb', is_alive=True)
        self.world.actors.append(camera)
        graph = json.loads(collect(self.world, self.ego, self.snapshot,
                                   expected_frame=100, expected_time_s=5.0))
        self.assertEqual([node['id'] for node in graph['nodes']], ['ego', 'actor:9'])

    def test_same_frame_signal_groups_join_original_inventory(self):
        light = NS(id=17, type_id='traffic.traffic_light', is_alive=True)
        self.world.actors.append(light)
        observed = {'frame': 100, 'time_s': 5.0,
                    'devices': [{'actor_id': 17,
                                 'blueprint': 'traffic.traffic_light',
                                 'state': 'Green',
                                 'light_box_method': 'TrafficLight.get_light_boxes',
                                 'light_boxes': [{'light_box_index': 0},
                                                 {'light_box_index': 1}]}],
                    'control_actor_inventory': {
                        'frame': 100, 'time_s': 5.0,
                        'method': 'World.get_actors', 'prefix': 'traffic.',
                        'actor_ids': [17], 'complete': True}}
        graph = json.loads(collect(self.world, self.ego, self.snapshot,
                                   expected_frame=100, expected_time_s=5.,
                                   observed_evidence=observed))
        self.assertEqual(graph['metadata']['observed_evidence'], observed)
        self.assertEqual([node['id'] for node in graph['nodes'][-2:]],
                         ['signal:17:0', 'signal:17:1'])
        self.assertEqual(graph['nodes'][-1]['attributes']['original_device_observation'],
                         observed['devices'][0])
