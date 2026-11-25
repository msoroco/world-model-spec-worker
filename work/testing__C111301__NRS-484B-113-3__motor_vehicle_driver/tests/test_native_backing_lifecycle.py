"""Fake-world ownership and publication checks; no physical evidence."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT.parents[1] / '.runtime-work'
sys.path.insert(0, str(ROOT))
from native_backing_lifecycle import CarlaCameraFactory, FFV1Encoder, run
from media_decode import _probe
from saved_backing import ASSIGNMENT, CAMERAS
from test_saved_backing import fixture


class Actor:
    def __init__(self, actor_id, kind):
        self.id, self.kind = actor_id, kind
        self.type_id = 'vehicle.audi.a2' if kind == 'vehicle' else 'walker.pedestrian.0001'
        self.destroyed = False
        self.command = SimpleNamespace(brake=0.0, reverse=True)
    def get_transform(self):
        x = 5.0 if self.kind == 'vehicle' else 2.0
        return SimpleNamespace(location=SimpleNamespace(x=x, y=0.0),
                               get_forward_vector=lambda: SimpleNamespace(x=1.0, y=0.0))
    def get_velocity(self):
        return SimpleNamespace(x=-.2 if self.kind == 'vehicle' else 0.0,
                               y=0.0 if self.kind == 'vehicle' else .2)
    def get_control(self):
        return self.command
    def apply_control(self, command):
        self.command = command
    def destroy(self):
        self.destroyed = True


class Sensor:
    def __init__(self, name):
        self.name, self.callback, self.stopped, self.destroyed = name, None, False, False
    def listen(self, callback):
        self.callback = callback
    def stop(self):
        self.stopped = True
    def destroy(self):
        self.destroyed = True


class Encoder:
    def __init__(self, path, width, height):
        self.path = Path(path)
        self.frames = 0
        self.aborted = False
    def append(self, image):
        self.frames += 1
    def close(self):
        self.path.write_bytes(f'fixture:{self.frames}'.encode())
    def abort(self):
        self.aborted = True


class World:
    def __init__(self, map_bytes, fail_at=None):
        self.map_bytes, self.fail_at = map_bytes, fail_at
        self.settings = SimpleNamespace(synchronous_mode=False, fixed_delta_seconds=None)
        self.frame = 1000
        self.actors = []
        self.sensors = []
    def get_map(self):
        return SimpleNamespace(name='OriginalTown', to_opendrive=lambda: self.map_bytes.decode())
    def get_settings(self):
        return self.settings
    def apply_settings(self, settings):
        self.settings = settings
    def get_blueprint_library(self):
        return SimpleNamespace(find=lambda name: SimpleNamespace(
            id=name, set_attribute=lambda key, value: None))
    def spawn_actor(self, blueprint, transform, attach_to=None):
        sensor = Sensor(blueprint.id)
        self.sensors.append(sensor)
        return sensor
    def try_spawn_actor(self, blueprint, transform):
        actor = Actor(7 if blueprint.id.startswith('vehicle.') else 8,
                      'vehicle' if blueprint.id.startswith('vehicle.') else 'pedestrian')
        self.actors.append(actor)
        return actor
    def tick(self):
        self.frame += 1
        if self.frame == self.fail_at:
            raise RuntimeError('injected Native tick failure')
        for sensor in self.sensors:
            sensor.callback(SimpleNamespace(frame=self.frame,
                timestamp=100 + (self.frame - 1001) * .05,
                width=2, height=2, raw_data=bytes([0, 0, 0, 255] * 4)))
        return self.frame
    def get_snapshot(self):
        return SimpleNamespace(frame=self.frame,
            timestamp=SimpleNamespace(elapsed_seconds=100 + (self.frame - 1001) * .05))


class NativeBackingLifecycleTests(unittest.TestCase):
    def test_reviewed_camera_factory_spawns_source_positioned_sensor(self):
        pose = {'location': {'x': 1.0, 'y': 2.0, 'z': 3.0},
                'rotation': {'pitch': 0.0, 'yaw': 90.0, 'roll': 0.0},
                'fov_deg': 90}
        carla = SimpleNamespace(Transform=lambda location, rotation: (location, rotation),
                                Location=lambda **values: values,
                                Rotation=lambda **values: values)
        factory = CarlaCameraFactory(carla, {'camera_extrinsics': {name: pose for name in CAMERAS}})
        attributes = {}
        blueprint = SimpleNamespace(set_attribute=lambda key, value: attributes.__setitem__(key, value))
        calls = []
        world = SimpleNamespace(get_blueprint_library=lambda: SimpleNamespace(find=lambda name: blueprint),
                                spawn_actor=lambda *args, **kwargs: calls.append((args, kwargs)) or Sensor('overview'))
        vehicle = object()
        sensor = factory(world, vehicle, 'overview', (1920, 1080))
        self.assertIsInstance(sensor, Sensor)
        self.assertEqual(attributes, {'image_size_x': '1920', 'image_size_y': '1080',
                                      'sensor_tick': '.05', 'fov': '90'})
        self.assertIs(calls[0][1]['attach_to'], vehicle)
        self.assertEqual(calls[0][0][1][0]['z'], 3.0)

    def test_reviewed_camera_factory_rejects_missing_extrinsic(self):
        with self.assertRaisesRegex(ValueError, 'four reviewed original camera'):
            CarlaCameraFactory(SimpleNamespace(), {'camera_extrinsics': {'overview': {}}})

    def test_reviewed_camera_factory_rejects_wrong_fov(self):
        pose = {'location': {'x': 1.0, 'y': 2.0, 'z': 3.0},
                'rotation': {'pitch': 0.0, 'yaw': 0.0, 'roll': 0.0},
                'fov_deg': 80}
        carla = SimpleNamespace(Transform=lambda location, rotation: (location, rotation),
                                Location=lambda **values: values,
                                Rotation=lambda **values: values)
        with self.assertRaisesRegex(ValueError, 'field of view differs'):
            CarlaCameraFactory(carla, {'camera_extrinsics': {name: pose for name in CAMERAS}})

    def test_ffv1_encoder_writes_20_hz_lossless_video(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
            path = Path(temp) / 'camera.mkv'
            encoder = FFV1Encoder(path, 16, 16)
            image = SimpleNamespace(width=16, height=16,
                                    raw_data=bytes([1, 2, 3, 255] * (16 * 16)))
            for _ in range(3):
                encoder.append(image)
            encoder.close()
            stream = _probe(path)
            self.assertEqual((stream['width'], stream['height']), (16, 16))
            self.assertEqual(stream['r_frame_rate'], '20/1')

    def run_case(self, root, fail_at=None):
        fixture(root)
        (root / 'acquisition.json').unlink()
        (root / 'telemetry.json').unlink()
        (root / 'frame-map.json').unlink()
        world = World((root / 'road.xodr').read_bytes(), fail_at)
        def camera_factory(world, vehicle, name, dimensions):
            sensor = Sensor(name)
            world.sensors.append(sensor)
            return sensor
        kwargs = dict(attempt=root, packet_path=root / 'map.json',
                      transforms={'vehicle': object(), 'pedestrian': object()},
                      case_id=ASSIGNMENT + '__pedestrian_yield',
                      camera_factory=camera_factory,
                      control_factory=lambda **values: SimpleNamespace(**values),
                      encoder_factory=Encoder, diagnostic_fixture=True)
        return world, kwargs

    def test_complete_owned_capture_publishes_after_cleanup(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
            root = Path(temp)
            world, kwargs = self.run_case(root)
            receipt = run(world, **kwargs)
            self.assertEqual(set(receipt['media']), set(CAMERAS))
            self.assertEqual(receipt['source_kind'], 'synthetic_fixture')
            self.assertTrue(all(actor.destroyed for actor in world.actors))
            self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor in world.sensors))
            self.assertFalse(world.get_settings().synchronous_mode)
            self.assertTrue((root / 'acquisition.json').is_file())
            self.assertEqual(len(json.loads((root / 'telemetry.json').read_text())), 900)

    def test_failed_tick_restores_and_never_publishes(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
            root = Path(temp)
            world, kwargs = self.run_case(root, fail_at=1004)
            with self.assertRaisesRegex(RuntimeError, 'injected Native tick failure'):
                run(world, **kwargs)
            self.assertTrue(all(actor.destroyed for actor in world.actors))
            self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor in world.sensors))
            self.assertFalse(world.get_settings().synchronous_mode)
            self.assertFalse((root / 'acquisition.json').exists())

    def test_unreviewed_packet_cannot_claim_original(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
            root = Path(temp)
            world, kwargs = self.run_case(root)
            kwargs['diagnostic_fixture'] = False
            with self.assertRaisesRegex(ValueError, 'reviewed original Native site'):
                run(world, **kwargs)
            self.assertFalse(world.actors)

    def test_linked_original_packet_is_rejected_before_world_mutation(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
            root = Path(temp)
            world, kwargs = self.run_case(root)
            linked = root / 'linked-map.json'
            linked.symlink_to(root / 'map.json')
            kwargs['packet_path'] = linked
            with self.assertRaisesRegex(ValueError, 'adjacent original map packet'):
                run(world, **kwargs)
            self.assertFalse(world.actors)

    def test_reviewed_packet_runs_production_owned_lifecycle(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temp:
            root = Path(temp)
            world, kwargs = self.run_case(root)
            packet = json.loads((root / 'map.json').read_text())
            pose = {'location': {'x': 1.0, 'y': 0.0, 'z': 1.0},
                    'rotation': {'pitch': 0.0, 'yaw': 0.0, 'roll': 0.0},
                    'fov_deg': 90}
            packet.update(review_status='reviewed_original',
                          actor_transforms={'vehicle': pose, 'pedestrian': pose},
                          camera_extrinsics={name: pose for name in CAMERAS})
            (root / 'map.json').write_text(json.dumps(packet) + '\n')
            carla = SimpleNamespace(Transform=lambda location, rotation: (location, rotation),
                                    Location=lambda **values: values,
                                    Rotation=lambda **values: values)
            kwargs.pop('transforms')
            kwargs.pop('camera_factory')
            kwargs.update(carla=carla, diagnostic_fixture=False)
            receipt = run(world, **kwargs)
            self.assertEqual(receipt['source_kind'], 'native_original')
            self.assertEqual(len(world.sensors), 4)
            self.assertTrue(all(actor.destroyed for actor in world.actors))
            self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor in world.sensors))
            self.assertFalse(world.get_settings().synchronous_mode)


if __name__ == '__main__':
    unittest.main()
