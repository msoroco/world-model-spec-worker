import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

folder = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fire_camera_capture', folder / 'fire_camera_capture.py')
module = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = module
spec.loader.exec_module(module)

class Blueprint:
    def __init__(self): self.attrs = {}
    def set_attribute(self, key, value): self.attrs[key] = value

class Sensor:
    def __init__(self, blueprint, transform):
        self.blueprint, self.transform, self.callback = blueprint, transform, None
        self.stopped = self.destroyed = False
    def listen(self, callback): self.callback = callback
    def emit(self, frame):
        width, height = int(self.blueprint.attrs['image_size_x']), int(self.blueprint.attrs['image_size_y'])
        self.callback(SimpleNamespace(frame=frame, width=width, height=height))
    def stop(self): self.stopped = True
    def destroy(self): self.destroyed = True

class World:
    def __init__(self): self.sensors = []
    def get_blueprint_library(self): return SimpleNamespace(find=lambda _: Blueprint())
    def spawn_actor(self, bp, transform, attach_to):
        assert attach_to is self.subject
        sensor = Sensor(bp, transform)
        self.sensors.append(sensor)
        return sensor

class Sink:
    def __init__(self): self.frames = []
    def write(self, image): self.frames.append(image.frame)

class CameraTests(unittest.TestCase):
    def setUp(self):
        self.world = World(); self.world.subject = object()
        self.carla = SimpleNamespace(Location=lambda *p: p,
                                     Rotation=lambda *p: p,
                                     Transform=lambda *p: p)
        self.sinks = {name: Sink() for name in module.CAMERAS}

    def test_four_sources_are_created_and_joined(self):
        capture = module.FireCameraCapture(self.world, self.carla, self.world.subject, self.sinks)
        self.assertEqual(len(self.world.sensors), 4)
        for sensor in self.world.sensors:
            self.assertEqual(sensor.blueprint.attrs['sensor_tick'], '0.05')
            for frame in (100, 101): sensor.emit(frame)
        capture.wait_for_frame(100, timeout_s=.01)
        capture.wait_for_frame(101, timeout_s=.01)
        self.assertEqual(capture.verify_frames((100, 101)), {n: 2 for n in module.CAMERAS})
        capture.close()
        self.assertTrue(all(s.stopped and s.destroyed for s in self.world.sensors))

    def test_missing_frame_and_sink_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'four named'):
            module.FireCameraCapture(self.world, self.carla, self.world.subject, {})
        capture = module.FireCameraCapture(self.world, self.carla, self.world.subject, self.sinks)
        for sensor in self.world.sensors[:-1]: sensor.emit(100)
        with self.assertRaisesRegex(ValueError, 'Timed out waiting'):
            capture.wait_for_frame(100, timeout_s=.001)
        with self.assertRaisesRegex(ValueError, 'Missing or extra'):
            capture.verify_frames((100,))
        capture.close()

    def test_lossless_source_sink_requires_exact_raw_frame_and_closed_encoder(self):
        class Input:
            def __init__(self): self.bytes = 0
            def write(self, raw): self.bytes += len(raw)
            def close(self): pass
        class Process:
            def __init__(self): self.stdin = Input()
            def wait(self): return 0
        commands = []
        process = Process()
        def popen(args, **kwargs):
            commands.append(args)
            return process
        with tempfile.TemporaryDirectory() as temp:
            sink = module.FFmpegSourceSink(temp, 'approach', popen=popen)
            self.assertIn('ffv1', commands[0])
            self.assertIn('1280x720', commands[0])
            with self.assertRaisesRegex(ValueError, 'raw byte count'):
                sink.write(SimpleNamespace(raw_data=b'bad'))
            sink.write(SimpleNamespace(raw_data=b'\x00' * sink.size))
            self.assertEqual(process.stdin.bytes, sink.size)
            sink.close()
            with self.assertRaisesRegex(ValueError, 'already closed'):
                sink.write(SimpleNamespace(raw_data=b''))

if __name__ == '__main__': unittest.main()
