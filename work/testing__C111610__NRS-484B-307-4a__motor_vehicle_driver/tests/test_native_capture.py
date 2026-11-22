import sys
import json
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import native_capture
from native_capture import (bind_map, bind_facing_arrow, observed_arrow,
                            bind_pedestrian_walk, pedestrian_station, spawn_entities,
                            bind_other_vehicle_green, other_vehicle_station)
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
    def test_other_vehicle_green_entry_and_connected_route(self):
        scene = load_scene(ROOT / 'cases/lawful_traffic_yield/scene.json')
        start, end = Waypoint(0, -12), Waypoint(0, 10)
        start.following = [self.points[2]]
        self.points[2].following.append(end)
        self.points.extend((start, end))
        carla = N(Location=lambda x, y, z: point(x, y, z))
        bound = bind_map(self.world(), carla, scene)
        self.assertEqual(len(bound['other_vehicle_route_waypoints']), 3)
        head = N(id=9, attributes={'official_traffic_signal': 'true'},
                 get_state=lambda: 'Green')
        world = N(get_actor=lambda identity: head if identity == 9 else None)
        self.assertIs(bind_other_vehicle_green(world, scene), head)
        self.assertEqual(other_vehicle_station(scene, 0, entry=True), (0, -11.95))
        self.assertAlmostEqual(other_vehicle_station(scene, 200, entry=True)[1], -1.95)
        head.get_state = lambda: 'Red'
        with self.assertRaisesRegex(ValueError, 'green entry'):
            bind_other_vehicle_green(world, scene)

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

    def test_original_walk_phase_and_bounded_entry(self):
        occupied = load_scene(ROOT / 'cases/crosswalk_occupied_yield/scene.json')
        head = N(id=8, attributes={'official_pedestrian_signal': 'true'},
                 get_state=lambda: 'Walk')
        world = N(get_actor=lambda identity: head if identity == 8 else None)
        self.assertIs(bind_pedestrian_walk(world, occupied), head)
        self.assertEqual(pedestrian_station(occupied, 0, entry=True), (-4.95, 6))
        self.assertEqual(pedestrian_station(occupied, 120, entry=True), (0, 6))
        self.assertEqual(pedestrian_station(occupied, 120), (5, 6))
        head.get_state = lambda: 'DontWalk'
        with self.assertRaisesRegex(ValueError, 'Walk indication'):
            bind_pedestrian_walk(world, occupied)

    def test_native_capture_lifecycle_with_fake_world(self):
        scene = load_scene(ROOT / 'cases/crosswalk_occupied_yield/scene.json')
        scene['duration_s'] = .15
        arrow = N(id=7, attributes={'signal_shape': 'arrow', 'arrow_direction': 'left',
                                     'sole_illuminated': 'true'}, get_state=lambda: 'Green')
        walk = N(id=8, attributes={'official_pedestrian_signal': 'true'},
                 get_state=lambda: 'Walk')
        other_green = N(id=9, attributes={'official_traffic_signal': 'true'},
                        get_state=lambda: 'Green')
        class Actor:
            def __init__(self, identity, transform):
                self.id, self.transform, self.destroyed = identity, transform, False
                self.bounding_box = N(get_world_vertices=lambda _transform: [
                    point(self.transform.location.x + dx, self.transform.location.y + dy)
                    for dx, dy in [(0, 0), (1, 0), (1, 1), (0, 1)]])
            def get_transform(self): return self.transform
            def set_transform(self, value): self.transform = value
            def get_velocity(self): return point(0, 0)
            def get_traffic_light(self): return arrow
            def apply_control(self, value): self.command = value
            def destroy(self): self.destroyed = True
        class World:
            def __init__(self, points):
                self.points, self.frame, self.actors = points, 0, []
                self.settings = N(synchronous_mode=False, fixed_delta_seconds=None)
            def get_map(self):
                return N(name='fake Native map',
                    get_waypoint=lambda loc: min(self.points,
                        key=lambda wp: abs(wp.transform.location.x-loc.x) +
                                       abs(wp.transform.location.y-loc.y)),
                    get_crosswalks=lambda: [point(-2, 4), point(2, 4),
                                            point(2, 8), point(-2, 8)])
            def get_settings(self): return N(**vars(self.settings))
            def apply_settings(self, value): self.settings = N(**vars(value))
            def get_blueprint_library(self):
                return N(filter=lambda _pattern: ['fake blueprint'],
                         find=lambda _name: N(set_attribute=lambda *_args: None))
            def spawn_actor(self, _bp, transform):
                actor = Actor(len(self.actors) + 1, transform)
                self.actors.append(actor)
                return actor
            def get_actor(self, identity):
                return walk if identity == 8 else other_green if identity == 9 else None
            def tick(self): self.frame += 1; return self.frame
            def get_snapshot(self):
                return N(frame=self.frame,
                         timestamp=N(elapsed_seconds=self.frame / 20))
        world = World(self.points)
        class FakeCameras:
            SPECS = native_capture.Cameras.SPECS
            def __init__(self, _world, _ego, output, _carla):
                self.output = output
                for name, *_ in self.SPECS:
                    (output / (name + '.mkv')).write_bytes(b'fake camera bytes')
            def append(self, frame): self.last_frame = frame
            def close(self): pass
        class FakePipelineCapture:
            def __init__(self, _client, _ego, output, _case):
                self.output = output
                for name in ('trace.jsonl', 'road.xodr', 'carla_recorder.log'):
                    (output / name).write_text('fake original source\n')
            def capture(self, frame, time_s): pass
            def close(self): pass
        class FakeFrameMap:
            def __init__(self, path): self.path, self.rows = path, []
            def append(self, frame, time_s):
                self.rows.append({'carla_frame': frame, 'time_s': time_s})
            def close(self):
                self.path.write_text(''.join(json.dumps(row) + '\n' for row in self.rows))
        carla = types.ModuleType('carla')
        carla.Location = lambda x=0, y=0, z=0: point(x, y, z)
        carla.Rotation = lambda yaw=0, pitch=0: N(yaw=yaw, pitch=pitch)
        carla.Transform = lambda location, rotation: N(location=location, rotation=rotation)
        carla.VehicleControl = lambda **values: N(**values)
        client = N(set_timeout=lambda _timeout: None, get_world=lambda: world)
        carla.Client = lambda _host, _port: client
        pipeline = types.ModuleType('pipeline_capture')
        pipeline.PipelineCapture = FakePipelineCapture
        native_output = types.ModuleType('worker_exchange.native_output')
        native_output.FrameMap = FakeFrameMap
        native_output.seal_capture = lambda output, **_values: (output / 'capture-seal.json').write_text('{}')
        restore = types.ModuleType('worker_exchange.world_restore')
        restore.fields = lambda value: vars(value)
        restore.equal = lambda first, second: first == second
        worker_exchange = types.ModuleType('worker_exchange')
        modules = {'carla': carla, 'pipeline_capture': pipeline,
                   'worker_exchange': worker_exchange,
                   'worker_exchange.native_output': native_output,
                   'worker_exchange.world_restore': restore}
        with tempfile.TemporaryDirectory() as directory, patch.dict(sys.modules, modules), \
             patch.object(native_capture, 'Cameras', FakeCameras):
            output = Path(directory)
            native_capture.run_native(scene, output, 'localhost', 2000)
            self.assertTrue((output / 'capture-seal.json').exists())
            self.assertTrue((output / 'pedestrian-entry.jsonl').exists())
            self.assertEqual(len((output / 'turn-history.jsonl').read_text().splitlines()), 3)
            self.assertTrue(all(actor.destroyed for actor in world.actors))
            self.assertFalse(world.settings.synchronous_mode)
            traffic_scene = load_scene(ROOT / 'cases/lawful_traffic_yield/scene.json')
            traffic_scene['duration_s'] = .15
            other_start, other_end = Waypoint(0, -12), Waypoint(0, 10)
            other_start.following = [self.points[2]]
            self.points[2].following.append(other_end)
            other_end.following = [self.points[3]]
            world = World([*self.points, other_start, other_end])
            with tempfile.TemporaryDirectory() as traffic_directory:
                traffic_output = Path(traffic_directory)
                native_capture.run_native(traffic_scene, traffic_output, 'localhost', 2000)
                self.assertTrue((traffic_output / 'capture-seal.json').exists())
                self.assertTrue((traffic_output / 'traffic-entry.jsonl').exists())
                self.assertEqual(len((traffic_output / 'turn-history.jsonl').read_text().splitlines()), 3)
                self.assertTrue(all(actor.destroyed for actor in world.actors))
                self.assertFalse(world.settings.synchronous_mode)
