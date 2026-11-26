"""Exercise the prospective Native capture without connecting to CARLA."""
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import runner

ROOT = Path(__file__).resolve().parents[3] / '.runtime-work'
CONFIG = Path(__file__).resolve().parents[1] / 'draft-native/probe_a/construction.json'


class Point:
    def __init__(self, x=0, y=0, z=0):
        self.x, self.y, self.z = x, y, z


class Rotation:
    def __init__(self, pitch=0, yaw=0, roll=0):
        self.pitch, self.yaw, self.roll = pitch, yaw, roll


class Transform:
    def __init__(self, location=None, rotation=None):
        self.location = location or Point()
        self.rotation = rotation or Rotation()


class Blueprint:
    def __init__(self, kind):
        self.id = kind
    def set_attribute(self, *_):
        pass


class Actor:
    next_id = 1
    def __init__(self, kind, transform):
        self.id = Actor.next_id
        Actor.next_id += 1
        self.type_id = kind
        self.transform = transform
        self.queue = None
        self.destroyed = False
    def listen(self, callback):
        self.callback = callback
    def apply_control(self, _):
        pass
    def get_transform(self):
        return self.transform
    def get_velocity(self):
        return Point()
    def stop(self):
        pass
    def destroy(self):
        self.destroyed = True


class Map:
    def to_opendrive(self):
        return '<OpenDRIVE/>'
    def get_waypoint(self, *_args, **_kwargs):
        return types.SimpleNamespace(transform=Transform(Point(y=10)))


class World:
    def __init__(self):
        self.settings = types.SimpleNamespace(synchronous_mode=False)
        self.actors = []
        self.frame = 0
    def get_settings(self):
        return self.settings
    def apply_settings(self, settings):
        self.settings = settings
    def get_map(self):
        return Map()
    def get_blueprint_library(self):
        return types.SimpleNamespace(filter=lambda pattern: [Blueprint(
            'walker.pedestrian.test' if pattern.startswith('walker')
            else 'vehicle.taxi.test')],
            find=lambda name: Blueprint(name))
    def spawn_actor(self, blueprint, transform, attach_to=None):
        actor = Actor(blueprint.id, transform)
        self.actors.append(actor)
        return actor
    def tick(self):
        self.frame += 1
        for actor in self.actors:
            if actor.type_id == 'sensor.camera.rgb':
                actor.callback(types.SimpleNamespace(frame=self.frame,
                                                     raw_data=b'frame'))
        return self.frame
    def get_snapshot(self):
        return types.SimpleNamespace(frame=self.frame,
            timestamp=types.SimpleNamespace(elapsed_seconds=self.frame * .05))
    def get_actors(self):
        return self.actors


class Client:
    def __init__(self, *_):
        self.original = World()
        self.current = self.original
    def set_timeout(self, _):
        pass
    def get_world(self):
        return self.current
    def generate_opendrive_world(self, *_):
        self.current = World()
        return self.current


class Encoder:
    def __init__(self, command, **_):
        self.path = Path(command[-1])
        self.stdin = io.BytesIO()
        self.stderr = io.BytesIO()
        self.returncode = None
    def wait(self, **_):
        self.path.write_bytes(b'synthetic-camera-shape')
        self.returncode = 0
        return 0
    def poll(self):
        return self.returncode
    def kill(self):
        self.returncode = -9


class FrameMap:
    def __init__(self, path):
        self.path = path
        self.rows = []
    def __enter__(self):
        return self
    def __exit__(self, *_):
        self.path.write_text(''.join(json.dumps(row) + '\n'
                                     for row in self.rows))
    def append(self, frame, time_s, **extra):
        self.rows.append({'video_frame': len(self.rows),
                          'native_frame': frame, 'time_s': time_s, **extra})


class PipelineCapture:
    def __init__(self, *_args, **_kwargs):
        self.frames = []
        self.closed = False
    def capture(self, frame, time_s):
        self.frames.append((frame, time_s))
    def close(self, confirmed=False):
        self.closed = confirmed


class CaptureLifecycle(unittest.TestCase):
    def fake_dependencies(self):
        construction = json.loads(CONFIG.read_text())
        files = {item['path']: item['content'] for item in construction['files']}
        config = json.loads(files['config.json'])
        fake_carla = types.ModuleType('carla')
        fake_carla.Client = Client
        fake_carla.Location = Point
        fake_carla.Rotation = Rotation
        fake_carla.Transform = Transform
        fake_carla.Vector3D = Point
        fake_carla.LaneType = types.SimpleNamespace(Parking=1)
        fake_carla.OpendriveGenerationParameters = lambda **kwargs: kwargs
        fake_carla.VehicleControl = lambda **kwargs: kwargs
        fake_carla.WalkerControl = lambda **kwargs: kwargs
        parent = types.ModuleType('worker_exchange')
        parent.__path__ = []
        native = types.ModuleType('worker_exchange.native_output')
        native.FrameMap = FrameMap
        seals = []
        native.seal_capture = lambda *args, **kwargs: seals.append((args, kwargs))
        restore_module = types.ModuleType('worker_exchange.world_restore')
        restore_calls = []
        restore_module.snapshot = lambda client: {'settings': client.original.settings}
        restore_module.restore = lambda client, saved: (
            restore_calls.append((client, saved)) or {'restored': True})
        capture_module = types.ModuleType('pipeline_capture')
        capture_module.PipelineCapture = PipelineCapture
        modules = {'carla': fake_carla, 'worker_exchange': parent,
                   'worker_exchange.native_output': native,
                   'worker_exchange.world_restore': restore_module,
                   'pipeline_capture': capture_module}
        return config, modules, seals, restore_calls

    def test_full_synthetic_world_lifecycle(self):
        config, modules, seals, restore_calls = self.fake_dependencies()
        with tempfile.TemporaryDirectory(dir=ROOT) as directory, \
                patch.dict(sys.modules, modules), \
                patch.object(runner.subprocess, 'Popen', Encoder):
            result = runner.capture(config, directory)
            attempt = Path(directory)
            rows = [json.loads(line) for line in
                    (attempt / 'native-rows.jsonl').read_text().splitlines()]
            frames = [json.loads(line) for line in
                      (attempt / 'video_frames.jsonl').read_text().splitlines()]
            trace = [json.loads(line) for line in
                     (attempt / 'trace.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows), 600)
            self.assertEqual(len(frames), 600)
            self.assertEqual(len(trace), 600)
            self.assertEqual(rows[0]['time_s'], .05)
            self.assertEqual(rows[-1]['time_s'], 30)
            self.assertEqual(frames[0]['time_s'], .05)
            self.assertEqual(frames[-1]['time_s'], 30)
            self.assertEqual(trace[0]['time_s'], .05)
            self.assertEqual(trace[-1]['time_s'], 30)
            self.assertEqual([row['frame'] for row in trace],
                             [row['native_frame'] for row in rows])
            self.assertTrue(all(row['taxi_actor_id'] == rows[index]['taxi_actor_id']
                                for index, row in enumerate(trace)))
            self.assertEqual(result['frames'], 600)
            self.assertFalse(result['taxi_and_stand_authority_verified'])
            self.assertEqual(len(seals), 1)
            self.assertEqual(len(restore_calls), 1)
            self.assertEqual({row['video_frame'] for row in rows}, set(range(600)))
            self.assertTrue(all(row['observed_activity'] is None for row in rows))
            self.assertTrue(all((attempt / (view + '.mkv')).is_file()
                for view in ('overview', 'approach', 'curb_reference',
                             'driver_reference')))

    def test_tick_failure_restores_without_seal(self):
        config, modules, seals, restore_calls = self.fake_dependencies()
        original_tick = World.tick
        def fail_after_ten(world):
            if world.frame == 10:
                raise RuntimeError('injected Native tick failure')
            return original_tick(world)
        with tempfile.TemporaryDirectory(dir=ROOT) as directory, \
                patch.dict(sys.modules, modules), \
                patch.object(runner.subprocess, 'Popen', Encoder), \
                patch.object(World, 'tick', fail_after_ten):
            with self.assertRaisesRegex(RuntimeError, 'injected Native tick failure'):
                runner.capture(config, directory)
            self.assertEqual(len(restore_calls), 1)
            self.assertEqual(seals, [])
            rows = (Path(directory) / 'native-rows.jsonl').read_text().splitlines()
            self.assertEqual(len(rows), 10)


if __name__ == '__main__':
    unittest.main()
