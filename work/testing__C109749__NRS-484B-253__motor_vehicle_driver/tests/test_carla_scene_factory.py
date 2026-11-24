import hashlib
import pathlib
import sys
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from carla_scene_factory import make_scene_factory
from carla_live_adapter import WorldLease
from test_native_acquisition import waypoint
from saved_left_turn import ASSIGNMENT_ID


def obj(**values): return types.SimpleNamespace(**values)


class API:
    class VehicleLightState(int):
        LeftBlinker = 1
    @staticmethod
    def Location(*args, **kwargs):
        if args: return obj(x=args[0], y=args[1], z=args[2])
        return obj(**kwargs)
    @staticmethod
    def Rotation(*args): return args
    @staticmethod
    def Transform(location, rotation):
        return obj(location=location, rotation=rotation,
                   get_forward_vector=lambda: obj(x=0.0, y=1.0))
    @staticmethod
    def VehicleControl(**values): return obj(**values)


class Actor:
    def __init__(self, identifier, transform, sensor=False):
        self.id = identifier
        self.transform = transform
        self.sensor = sensor
        self.destroyed = False
        self.controls = []
        self.light = 0
        self.bounding_box = obj(get_world_vertices=lambda _: [obj(x=0, y=0, z=0)] * 8)
    def set_autopilot(self, value): self.autopilot = value
    def set_light_state(self, value): self.light = int(value)
    def apply_control(self, value): self.controls.append(value)
    def get_transform(self): return self.transform
    def get_velocity(self): return obj(length=lambda: 0.0)
    def destroy(self): self.destroyed = True


class Map:
    road = 'source-original-xodr'
    def to_opendrive(self): return self.road
    def get_waypoint(self, location, project_to_road=False):
        junction = abs(location.x) < 5 and abs(location.y) < 5
        return obj(road_id=1, lane_id=1,
                   is_junction=junction,
                   get_junction=lambda: obj(id=9),
                   transform=API.Transform(API.Location(x=location.x, y=location.y, z=0.0), (0, 0, 0)))


class World:
    def __init__(self):
        self.map = Map()
        self.actors = []
        self.settings = obj(synchronous_mode=False, fixed_delta_seconds=None)
        self.weather = obj(name='original')
    def get_map(self): return self.map
    def get_settings(self): return obj(**vars(self.settings))
    def apply_settings(self, value): self.settings = value
    def get_weather(self): return self.weather
    def set_weather(self, value): self.weather = value
    def get_blueprint_library(self):
        return obj(find=lambda key: obj(id=key, set_attribute=lambda *args: None))
    def try_spawn_actor(self, blueprint, transform, attach_to=None):
        actor = Actor(len(self.actors) + 1, transform, blueprint.id.startswith('sensor.'))
        self.actors.append(actor)
        return actor


def packet(world):
    return {'map_sha256': hashlib.sha256(world.map.road.encode()).hexdigest(),
            'source_ref': 'reviewed-source-fixture', 'junction_id': 9,
            'intersection_polygon': [[-5, -5], [5, -5], [5, 5], [-5, 5]],
            'ego_route': [waypoint(0, -10, None), waypoint(0, 0, 9), waypoint(-10, 0, None)],
            'opposing_route': [waypoint(0, 10, None), waypoint(0, 0, 9), waypoint(0, -10, None)],
            'ego_blueprint_id': 'vehicle.ego', 'opponent_blueprint_id': 'vehicle.other',
            'reviewed_original_map': True}


def request(world, reciprocal=False):
    p = packet(world)
    return {'case_id': ASSIGNMENT_ID + '__inside_yield',
            'ego_blueprint_id': p['ego_blueprint_id'],
            'opponent_blueprint_id': p['opponent_blueprint_id'],
            'ego_spawn_waypoint': p['ego_route'][0],
            'initial_opponent_spawn_waypoint': p['opposing_route'][1],
            'ego_route': p['ego_route'], 'initial_opponent_route': p['opposing_route'],
            'controller': {'wait_for_initial_opponent': True, 'signal_left': True,
                           'wait_for_later_opponent': True if reciprocal else None,
                           'target_speed_mps': 5.0},
            'capture': {'overview_resolution': [1920, 1080],
                        'detail_resolutions': [[1280, 720]] * 3}}


class SceneFactoryTests(unittest.TestCase):
    def test_spawns_six_owned_actors_and_applies_measured_control(self):
        world = World()
        original = world.get_settings()
        with WorldLease(world) as lease:
            scene = make_scene_factory(API)(world=world, request=request(world),
                                             packet=packet(world), lease=lease)
            self.assertEqual(len(lease.owned), 6)
            self.assertEqual(set(scene['cameras']),
                             {'overview', 'approach', 'reference_corner', 'driver_reference'})
            self.assertEqual(scene['ego'].light, 1)
            scene['control_step'](scene['ego'], scene['opponent'])
            self.assertEqual(len(scene['ego'].controls), 1)
            self.assertGreater(scene['ego'].controls[0].brake, 0)
            self.assertEqual(len(scene['opponent'].controls), 1)
        self.assertTrue(all(actor.destroyed for actor in world.actors))
        self.assertEqual(vars(world.get_settings()), vars(original))

    def test_reciprocal_requires_separate_actor_before_spawn(self):
        world = World()
        with WorldLease(world) as lease:
            with self.assertRaisesRegex(ValueError, 'separately spawned later opponent'):
                make_scene_factory(API)(world=world, request=request(world, True),
                                        packet=packet(world), lease=lease)
            self.assertEqual(world.actors, [])

    def test_changed_native_map_rejected_before_spawn(self):
        world = World()
        p = packet(world)
        p['map_sha256'] = '0' * 64
        with WorldLease(world) as lease:
            with self.assertRaisesRegex(ValueError, 'OpenDRIVE bytes differ'):
                make_scene_factory(API)(world=world, request=request(world),
                                        packet=p, lease=lease)
            self.assertEqual(world.actors, [])


if __name__ == '__main__': unittest.main()
