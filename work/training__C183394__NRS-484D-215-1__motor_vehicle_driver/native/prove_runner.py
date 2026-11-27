"""CPU fake of the complete Native acquisition control and source lifecycle."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import types
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
REPO = next(parent for parent in HERE.parents if (parent / 'batch.json').is_file())
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
sys.path.insert(1, str(REPO / 'runtime/python'))
from worker_exchange import media, native_output, world_restore
import beam_capture


class Point:
    def __init__(self, x=0, y=0, z=0):
        self.x, self.y, self.z = x, y, z


class Rotation:
    def __init__(self, yaw=0, pitch=0):
        self.yaw, self.pitch = yaw, pitch


class Transform:
    def __init__(self, location=None, rotation=None):
        self.location = location or Point()
        self.rotation = rotation or Rotation()


class Actor:
    def __init__(self, ident, yaw):
        self.id, self.type_id, self.yaw = ident, 'vehicle.fake', yaw
        self.world = None
        self.bits = 2

    def get_transform(self):
        frame = self.world.frame
        x = -100 + frame * .125 if self.id == 107 else 100 - frame * .125
        return Transform(Point(x, -5 if self.id == 107 else 1.75, .5), Rotation(self.yaw))

    def get_velocity(self):
        return Point(2.5 if self.id == 107 else -2.5)

    def get_light_state(self):
        return self.bits

    def destroy(self):
        pass


class Image:
    def __init__(self, frame):
        self.frame = frame
        self.raw_data = b'x'


class Sensor:
    type_id = 'sensor.camera.rgb'

    def __init__(self, world):
        self.world, self.is_listening, self.callback = world, False, None

    def listen(self, callback):
        self.callback = callback
        self.is_listening = True

    def stop(self):
        self.is_listening = False

    def destroy(self):
        pass


class Blueprint:
    def __init__(self):
        self.attributes = {}

    def set_attribute(self, name, value):
        self.attributes[name] = value


class World:
    def __init__(self):
        self.frame = 0
        self.sensors = []
        self.blueprints = []

    def get_actors(self):
        return []

    def get_blueprint_library(self):
        world = self
        class Library:
            def find(self, name):
                assert name == 'sensor.camera.rgb'
                blueprint = Blueprint()
                world.blueprints.append(blueprint)
                return blueprint
        return Library()

    def try_spawn_actor(self, blueprint, transform, attach_to=None):
        sensor = Sensor(self)
        self.sensors.append(sensor)
        return sensor

    def tick(self):
        self.frame += 1
        for sensor in self.sensors:
            if sensor.is_listening:
                sensor.callback(Image(self.frame))
        return self.frame

    def get_snapshot(self):
        return types.SimpleNamespace(timestamp=types.SimpleNamespace(
            elapsed_seconds=self.frame / 20))


class Array:
    def reshape(self, *args):
        return self

    def __getitem__(self, key):
        return self

    def tobytes(self):
        return b'fake-rgb-pixel'


class Encoder:
    def __init__(self, args, **kwargs):
        self.stdin = types.SimpleNamespace(write=lambda value: len(value), close=lambda: None)
        self.returncode = None
        Path(args[-1]).write_bytes(b'fake-lossless-video')

    def wait(self, timeout=None):
        self.returncode = 0
        return 0


class Capture:
    def __init__(self, client, ego, output, case, **kwargs):
        self.count = 0

    def capture(self, frame, time_s, extra=None):
        assert extra['c183394_beam']['native_frame'] == frame
        self.count += 1

    def close(self, confirmed):
        assert confirmed and self.count == 600


def prove(suffix):
    construction = json.loads((PACKAGE / 'constructions' / suffix / 'primary' / 'construction.json').read_text())
    output = Path(os.environ['TMPDIR']).resolve() / ('fake-runner-' + suffix)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    for item in construction['files']:
        if item['path'] in ('runner.py', 'config.json'):
            (output / item['path']).write_text(item['content'])
    (output / 'construction.json').write_text(json.dumps(construction) + '\n')
    world = World()
    ego, oncoming = Actor(107, 0), Actor(108, 180)
    ego.world = oncoming.world = world
    plan = {'cameras': [{'name': name, 'size': size, 'xyz_m': [0, 0, 2],
                        'yaw_deg': 0, 'pitch_deg': 0, 'mount': 'world'}
                       for name, size in zip(beam_capture.CAMERAS,
                                             ([1920, 1080], [1280, 720], [1280, 720], [1280, 720]))]}
    scene = {'world': world, 'ego': ego, 'oncoming': oncoming, 'owned': [ego, oncoming],
             'plan': plan, 'map': types.SimpleNamespace(to_opendrive=lambda: '<OpenDRIVE>C183394</OpenDRIVE>')}
    client = types.SimpleNamespace(set_timeout=lambda value: None,
                                   get_world=lambda: world)
    carla = types.ModuleType('carla')
    carla.Client = lambda host, port: client
    carla.Transform, carla.Location, carla.Rotation = Transform, Point, Rotation
    numpy = types.ModuleType('numpy')
    numpy.uint8 = 'uint8'
    numpy.frombuffer = lambda data, dtype: Array()
    pipeline = types.ModuleType('pipeline_capture')
    pipeline.PipelineCapture = Capture
    def command(scene, module):
        scene['ego'].bits = 2 if suffix == 'condition_a' else 4
        return {'requested_beam_state': 'low_beam' if suffix == 'condition_a' else 'high_beam'}
    def compose(views, mapping, destination):
        assert len(views) == 4 and len(Path(mapping).read_text().splitlines()) == 600
        Path(destination).write_bytes(b'fake-composed-video')
        return {'diagnostic_fake': True}
    def seal(path, **kwargs):
        road = Path(path) / 'road.xodr'
        assert road.read_text() == '<OpenDRIVE>C183394</OpenDRIVE>'
        assert kwargs['frames'] == 600 and len(kwargs['encoder_exit_codes']) == 4
        assert all(value == 0 for value in kwargs['encoder_exit_codes'].values())
        (Path(path) / 'capture-seal.json').write_text(json.dumps({'fake': True}) + '\n')
    with patch.dict(sys.modules, {'carla': carla, 'numpy': numpy,
                                  'pipeline_capture': pipeline}), \
         patch.object(beam_capture, 'install', return_value=scene), \
         patch.object(beam_capture, 'command_tick', side_effect=command), \
         patch.object(beam_capture.subprocess, 'Popen', side_effect=Encoder), \
         patch.object(media, 'compose_four_views', side_effect=compose), \
         patch.object(native_output, 'seal_capture', side_effect=seal), \
         patch.object(world_restore, 'snapshot', return_value={'settings': types.SimpleNamespace(synchronous_mode=False)}), \
         patch.object(world_restore, 'restore', return_value={'restored': True}):
        beam_capture.run(output, output, 'fake-host', 2000)
    assert len(world.blueprints) == 4
    assert len((output / 'beam-rows.jsonl').read_text().splitlines()) == 600
    assert len((output / 'video_frames.jsonl').read_text().splitlines()) == 600
    assert (output / 'road.xodr').is_file()
    report = json.loads((output / 'native-capture-report.json').read_text())
    assert report['error'] is None and report['observed_frames'] == 600
    return {'case': suffix, 'frames': 600, 'cameras': 4,
            'road_sha256': hashlib.sha256((output / 'road.xodr').read_bytes()).hexdigest(),
            'fake_only': True}


if __name__ == '__main__':
    print(json.dumps([prove('condition_a'), prove('condition_b')], indent=2))
