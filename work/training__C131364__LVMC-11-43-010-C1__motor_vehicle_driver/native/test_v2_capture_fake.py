"""Bounded CPU state-machine test for the current Native capture entrypoint.

The fake world verifies runner plumbing only; it does not verify CARLA physics.
All temporary attempts are created under .runtime-work.
"""
import json
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
REPO = CASE.parents[1]
SCRATCH = REPO / '.runtime-work/c131364-v2/fake-native-test'
SCRATCH.mkdir(parents=True, exist_ok=True)
os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(SCRATCH.resolve())
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
import v2_native_capture as native
import v2_native_finalize as finalizer
import v2_source_audit as source_audit


class Position:
    def __init__(self, x=0, y=0, z=0):
        self.x, self.y, self.z = x, y, z


class Rotation:
    def __init__(self, yaw=0, pitch=0):
        self.yaw, self.pitch = yaw, pitch


class Transform:
    def __init__(self, location=None, rotation=None):
        self.location = location or Position()
        self.rotation = rotation or Rotation()


class Actor:
    type_id = 'vehicle.tesla.model3'
    id = 99

    def __init__(self, transform):
        self.transform = transform
        self.controls = []
        self.destroyed = False
        self.bounding_box = types.SimpleNamespace(
            get_world_vertices=lambda pose: [Position(), Position(1, 1, 1)])

    def get_transform(self):
        return self.transform

    def get_velocity(self):
        return Position()

    def apply_control(self, control):
        self.controls.append(control)

    def destroy(self):
        self.destroyed = True


class Sensor:
    type_id = 'sensor.camera.rgb'

    def __init__(self, number):
        self.number = number
        self.callback = None
        self.is_listening = False
        self.destroyed = False

    def listen(self, callback):
        self.callback = callback
        self.is_listening = True

    def stop(self):
        self.is_listening = False

    def destroy(self):
        self.destroyed = True


class Map:
    name = 'fake-roundabout'

    def __init__(self, lane):
        self.calls = 0
        self.lane = lane

    def get_waypoint(self, location, **kwargs):
        if self.calls < 3:
            road = (10, 11, 12)[self.calls]
        else:
            index = self.calls - 3
            road = 10 if index < 99 else 11 if index < 224 else 12
        self.calls += 1
        return types.SimpleNamespace(road_id=road, lane_id=self.lane)

    def to_opendrive(self):
        return '<OpenDRIVE>fake generated map</OpenDRIVE>'


class World:
    def __init__(self, lane, bad_camera):
        self.settings = types.SimpleNamespace(synchronous_mode=False)
        self.mapping = Map(lane)
        self.frame = 0
        self.sensors = []
        self.ego = None
        self.bad_camera = bad_camera

    def get_settings(self):
        return self.settings

    def apply_settings(self, settings):
        self.settings = settings

    def set_weather(self, weather):
        pass

    def get_map(self):
        return self.mapping

    def get_blueprint_library(self):
        return types.SimpleNamespace(find=lambda name: types.SimpleNamespace(
            set_attribute=lambda key, value: None))

    def try_spawn_actor(self, blueprint, transform):
        self.ego = Actor(transform)
        return self.ego

    def spawn_actor(self, blueprint, transform, attach_to=None):
        sensor = Sensor(len(self.sensors))
        self.sensors.append(sensor)
        return sensor

    def tick(self):
        self.frame += 1
        for sensor in self.sensors:
            frame = self.frame + int(self.bad_camera and sensor.number == 2 and self.frame == 21)
            sensor.callback(types.SimpleNamespace(frame=frame, raw_data=bytes(16)))
        return self.frame

    def get_snapshot(self):
        return types.SimpleNamespace(timestamp=types.SimpleNamespace(
            elapsed_seconds=self.frame / 20))


class Client:
    def __init__(self, lane, bad_camera):
        self.old = types.SimpleNamespace(get_actors=lambda: [])
        self.world = self.old
        self.generated = World(lane, bad_camera)
        self.restored = False

    def set_timeout(self, seconds):
        pass

    def get_world(self):
        return self.world

    def generate_opendrive_world(self, source, params):
        self.world = self.generated
        return self.world


class Sink:
    def __init__(self):
        self.writes = 0

    def write(self, data):
        self.writes += 1

    def close(self):
        pass


class Encoder:
    def __init__(self, command, stdin, stderr):
        self.stdin = Sink()
        self.returncode = 0
        Path(command[-1]).write_bytes(b'fake encoded source')
        self.name = Path(command[-1]).name

    def wait(self, timeout):
        return self.returncode


class Capture:
    def __init__(self, client, ego, output, case_id, **kwargs):
        self.path = Path(output) / 'trace.jsonl'
        self.stream = self.path.open('x')

    def capture(self, frame, time_s, extra):
        self.stream.write(json.dumps({'frame': frame, 'time_s': time_s}) + '\n')

    def close(self, confirmed):
        self.stream.close()


def materialize(root, witness):
    construction = json.loads((CASE / 'v2-native-draft' /
        f'{witness}-construction.json').read_text())
    for item in construction['files']:
        target = root / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item['content'])
    (root / 'construction.json').write_text(json.dumps(construction) + '\n')
    config = json.loads((root / 'config.json').read_text())
    for camera in config['cameras']:
        camera['width'] = camera['height'] = 2
    (root / 'config.json').write_text(json.dumps(config) + '\n')


class CaptureStateMachine(unittest.TestCase):
    def run_case(self, witness, bad_camera):
        lane = -1 if witness == 'witness_1' else -2
        client = Client(lane, bad_camera)
        carla = types.ModuleType('carla')
        carla.Client = lambda host, port: client
        carla.OpendriveGenerationParameters = lambda **kwargs: kwargs
        carla.WeatherParameters = types.SimpleNamespace(ClearNoon='clear')
        carla.Location, carla.Rotation, carla.Transform = Position, Rotation, Transform
        carla.LaneType = types.SimpleNamespace(Driving='driving')
        carla.VehicleControl = lambda **kwargs: kwargs
        capture = types.ModuleType('pipeline_capture')
        capture.PipelineCapture = Capture
        restore = types.ModuleType('worker_exchange.world_restore')
        restore.snapshot = lambda client: {'settings': types.SimpleNamespace(synchronous_mode=False)}
        def restore_world(client, saved):
            client.restored = True
            return {'restored': True}
        restore.restore = restore_world
        output = types.ModuleType('worker_exchange.native_output')
        def seal_fake(root, **kwargs):
            root = Path(root)
            sources = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                       for name in source_audit.REQUIRED}
            (root / 'capture-seal.json').write_text(json.dumps({
                'provenance_kind': 'native', 'diagnostic_fixture': False,
                'frames': kwargs['frames'], 'restoration': kwargs['restoration'],
                'events': ['capture_finished', 'encoders_closed', 'restoration_verified'],
                'sources': sources}) + '\n')
        output.seal_capture = seal_fake
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
            root = Path(temporary)
            materialize(root, witness)
            with patch.dict(sys.modules, {'carla': carla, 'pipeline_capture': capture,
                'worker_exchange.world_restore': restore,
                'worker_exchange.native_output': output}), \
                 patch.object(native, 'repository', return_value=REPO), \
                 patch.object(native.subprocess, 'Popen', Encoder):
                if bad_camera:
                    with self.assertRaisesRegex(RuntimeError, 'Native attempt failed'):
                        native.execute(root, root, 'fake', 2000)
                else:
                    result = native.execute(root, root, 'fake', 2000)
                    self.assertEqual(result['checked_frames'], 600)
            self.assertTrue(client.restored)
            self.assertEqual(len(client.generated.ego.controls), 600 if not bad_camera else 1)
            self.assertTrue(client.generated.ego.destroyed)
            self.assertTrue(all(sensor.destroyed for sensor in client.generated.sensors))
            status = json.loads((root / 'native-run-status.json').read_text())
            if bad_camera:
                self.assertEqual(status['frames'], 0)
                self.assertTrue(status['errors'])
                self.assertFalse((root / 'capture-seal.json').exists())
            else:
                self.assertEqual(status['frames'], 600)
                self.assertEqual(status['errors'], [])
                self.assertTrue((root / 'capture-seal.json').is_file())
                self.assertEqual(len((root / 'roundabout-track.jsonl').read_text().splitlines()), 600)
                self.assertEqual(len((root / 'video_frames.jsonl').read_text().splitlines()), 600)
                with patch.object(finalizer, 'validate_video'):
                    measured = finalizer.measure_native(root)
                    self.assertTrue(measured['ordered_entry_circulation_exit_observed'])
                    self.assertEqual(measured['circulating_lane_ids'], [lane])
                    report = finalizer.finalize_native(root, root / 'analysis-report.json')
                    self.assertFalse(report['physical_acceptance_claimed'])
                    self.assertTrue((root / 'result.json').is_file())
                    with patch.object(source_audit, 'decode_cameras'):
                        audit = source_audit.audit(root)
                        self.assertTrue(audit['source_verified'])
                        self.assertFalse(audit['physical_acceptance_claimed'])
                    path = root / 'roundabout-track.jsonl'
                    lines = path.read_text().splitlines()
                    changed = json.loads(lines[201])
                    changed['native_frame'] += 1
                    lines[201] = json.dumps(changed)
                    path.write_text('\n'.join(lines) + '\n')
                    with self.assertRaisesRegex(ValueError, 'source/frame join differs'):
                        finalizer.measure_native(root)
                    with self.assertRaisesRegex(ValueError, 'Sealed original source differs'):
                        source_audit.audit(root)

    def test_full_four_camera_capture_and_restore(self):
        self.run_case('witness_1', False)

    def test_camera_join_failure_restores_without_seal(self):
        self.run_case('witness_2', True)


if __name__ == '__main__':
    unittest.main()
