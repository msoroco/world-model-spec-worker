import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace as NS


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from native_run import CAMERAS, run


class Carla:
    @staticmethod
    def Location(**values):
        return NS(**values)

    @staticmethod
    def Rotation(**values):
        return NS(**values)

    @staticmethod
    def Transform(location, rotation):
        return NS(location=location, rotation=rotation)

    @staticmethod
    def VehicleControl(**values):
        return NS(**values)


class Blueprint:
    def __init__(self, name):
        self.id = name
        self.attributes = {}

    def set_attribute(self, name, value):
        self.attributes[name] = value


class Library:
    def find(self, name):
        return Blueprint(name)


class Box:
    def get_world_vertices(self, transform):
        x, y = transform.location.x, transform.location.y
        return [NS(x=x + dx, y=y + dy, z=z) for dx in (-.4, .4)
                for dy in (-.4, .4) for z in (-.5, .5)]


class Vehicle:
    bounding_box = Box()

    def __init__(self, actor_id, transform):
        self.id = actor_id
        self.transform = transform
        self.destroyed = False
        self.controls = []

    def get_transform(self):
        return self.transform

    def get_location(self):
        return self.transform.location

    def get_velocity(self):
        return NS(x=0, y=0, z=0)

    def apply_control(self, control):
        self.controls.append(control)

    def destroy(self):
        self.destroyed = True


class Sensor:
    def __init__(self, blueprint):
        self.width = int(blueprint.attributes['image_size_x'])
        self.height = int(blueprint.attributes['image_size_y'])
        self.callback = None
        self.stopped = False
        self.destroyed = False

    def listen(self, callback):
        self.callback = callback

    def stop(self):
        self.stopped = True

    def destroy(self):
        self.destroyed = True


class Map:
    def to_opendrive(self):
        return '<OpenDRIVE/>\n'

    def get_waypoint(self, location, project_to_road=False):
        return NS(road_id=1, lane_id=1)


class World:
    def __init__(self):
        self.map = Map()
        self.settings = NS(synchronous_mode=False, fixed_delta_seconds=None)
        self.frame = 99
        self.vehicles = []
        self.sensors = []
        self.fail_camera = False
        self.bad_camera_time = False

    def get_map(self):
        return self.map

    def get_settings(self):
        return self.settings

    def apply_settings(self, settings):
        self.settings = NS(**vars(settings))

    def get_blueprint_library(self):
        return Library()

    def try_spawn_actor(self, blueprint, transform):
        actor = Vehicle(len(self.vehicles) + 1, transform)
        self.vehicles.append(actor)
        return actor

    def spawn_actor(self, blueprint, transform, attach_to=None):
        if self.fail_camera and len(self.sensors) == 2:
            return None
        sensor = Sensor(blueprint)
        self.sensors.append(sensor)
        return sensor

    def tick(self):
        self.frame += 1
        for sensor in self.sensors:
            if sensor.callback:
                sensor.callback(NS(frame=self.frame,
                                   timestamp=(self.frame - 99) * .05 +
                                   (.01 if self.bad_camera_time else 0),
                                   width=sensor.width, height=sensor.height,
                                   raw_data=bytes([0, 0, 255, 255]) *
                                   sensor.width * sensor.height))
        return self.frame

    def get_snapshot(self):
        return NS(frame=self.frame,
                  timestamp=NS(elapsed_seconds=(self.frame - 99) * .05))


class NativeRunTest(unittest.TestCase):
    def setUp(self):
        scratch = PACKAGE.parents[1] / '.runtime-work' / 'c125763-native-run-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.world = World()
        scene = {
            'map_sha256': hashlib.sha256(self.world.map.to_opendrive().encode()).hexdigest(),
            'reviewer': 'fixture', 'source_citation': 'fixture only',
            'cell_id': 'C125763', 'control': 'yield_sign',
            'ego_highway': 'A', 'other_highway': 'B',
            'approach_relation': 'crossing', 'ego_side': 'left',
            'intersection_bounds_xy_m': [-1, -1, 1, 1],
            'ego_route': [[-5, 0, 0], [2, 0, 0]],
            'other_route': [[0, -5, 0], [0, 2, 0]],
            'ego_lane': {'road_id': 1, 'lane_id': 1},
            'other_lane': {'road_id': 1, 'lane_id': 1},
            'ego_blueprint': 'vehicle.ego', 'other_blueprint': 'vehicle.other',
            'release_s': {'entry_below': 0, 'entry_inside': .1, 'entry_above': .2},
            'camera_dimensions': {name: [2, 2] for name in CAMERAS},
            'camera_poses': {name: dict(x=0, y=0, z=5, pitch=-30, yaw=0, roll=0)
                             for name in CAMERAS},
            'camera_mounts': {name: ('ego' if name == 'driver_reference' else 'world')
                              for name in CAMERAS},
        }
        for name in ('device', 'highway'):
            path = self.root / (name + '.txt')
            path.write_text('fixture ' + name + '\n')
            scene[name + '_source'] = {'path': path.name,
                                       'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                       'citation': 'fixture only'}
        self.packet = self.root / 'reviewed-site.json'
        self.packet.write_text(json.dumps(scene) + '\n')

    def test_same_tick_cameras_controls_and_release(self):
        output = self.root / 'capture'
        receipt = run(self.world, Carla, self.packet, output, 'entry_inside',
                      frame_count=3, diagnostic_fixture=True)
        self.assertEqual(receipt['camera_view_frames'], 12)
        self.assertEqual(len(self.world.vehicles[0].controls), 3)
        self.assertEqual([control.brake for control in self.world.vehicles[1].controls],
                         [1.0, 1.0, 0.0])
        self.assertTrue(all(actor.destroyed for actor in self.world.vehicles))
        self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor in self.world.sensors))
        self.assertFalse(self.world.settings.synchronous_mode)
        self.assertTrue((output / 'source-manifest.json').is_file())

    def test_partial_sensor_spawn_restores_owned_resources(self):
        self.world.fail_camera = True
        with self.assertRaisesRegex(RuntimeError, 'camera spawn failed'):
            run(self.world, Carla, self.packet, self.root / 'failed',
                'entry_inside', frame_count=3, diagnostic_fixture=True)
        self.assertTrue(all(actor.destroyed for actor in self.world.vehicles))
        self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor in self.world.sensors))
        self.assertFalse(self.world.settings.synchronous_mode)

    def test_fixture_cannot_be_published_as_original(self):
        with self.assertRaisesRegex(ValueError, 'reviewed original'):
            run(self.world, Carla, self.packet, self.root / 'unreviewed',
                'entry_inside', frame_count=3)
        self.assertEqual(self.world.vehicles, [])

    def test_camera_timestamp_failure_restores_world(self):
        self.world.bad_camera_time = True
        with self.assertRaisesRegex(ValueError, 'timestamp differs'):
            run(self.world, Carla, self.packet, self.root / 'bad-time',
                'entry_inside', frame_count=3, diagnostic_fixture=True)
        self.assertTrue(all(actor.destroyed for actor in self.world.vehicles))
        self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor in self.world.sensors))
        self.assertFalse(self.world.settings.synchronous_mode)

    def test_original_requires_full_four_view_profile(self):
        scene = json.loads(self.packet.read_text())
        scene['review_status'] = 'reviewed_original'
        self.packet.write_text(json.dumps(scene) + '\n')
        with self.assertRaisesRegex(ValueError, '900 frames and four profile cameras'):
            run(self.world, Carla, self.packet, self.root / 'too-small',
                'entry_inside', frame_count=900)
        self.assertEqual(self.world.vehicles, [])


if __name__ == '__main__':
    unittest.main()
