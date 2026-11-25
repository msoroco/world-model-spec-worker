import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location('c158196_officer_camera_media',
                                              ROOT / 'officer_camera_media.py')
MEDIA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MEDIA)


class Sensor:
    def __init__(self):
        self.stopped = self.destroyed = False

    def listen(self, callback):
        self.callback = callback

    def stop(self):
        self.stopped = True

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self):
        self.frame = 101
        self.sensors = []

    def spawn_actor(self, blueprint, transform, **options):
        sensor = Sensor()
        self.sensors.append(sensor)
        return sensor

    def get_snapshot(self):
        return NS(frame=self.frame, timestamp=NS(elapsed_seconds=5.05))


class Encoder:
    def __init__(self, root):
        self.root, self.count, self.processes = Path(root), 0, {'open': True}

    def __enter__(self):
        return self

    def validate_packets(self, packets):
        if set(packets) != set(MEDIA.CAMERAS):
            raise ValueError('camera packet set differs')

    def add_packets(self, packets):
        self.count += 1

    def _finish(self, abort=False):
        self.processes = {}
        self.exit_codes = {name: 0 for name in MEDIA.CAMERAS}


class CameraMediaTests(unittest.TestCase):
    def test_four_same_frame_sources_and_stale_packet_rejection(self):
        world = World()
        blueprints = {name: name for name in MEDIA.CAMERAS}
        mounts = {name: {'transform': NS(), 'attach_to': None}
                  for name in MEDIA.CAMERAS}
        with tempfile.TemporaryDirectory() as root:
            with MEDIA.CameraMedia(world, root, blueprints, mounts,
                                   {'ego': NS(id=1)}, encoder_factory=Encoder) as media:
                self.assertEqual(len(world.sensors), 4)
                for sensor in world.sensors:
                    sensor.callback(NS(frame=101, timestamp=5.05, width=16, height=16))
                frames = media.readback(101)
                self.assertEqual(set(frames), set(MEDIA.CAMERAS))
                self.assertEqual(frames['approach']['video_frame'], 0)
                self.assertEqual(frames['approach']['raw_source'],
                                 str(Path(root).resolve() / 'approach.mkv') + '#frame-0')
                for sensor in world.sensors:
                    sensor.callback(NS(frame=100, timestamp=5.05, width=16, height=16))
                with self.assertRaisesRegex(ValueError, 'frame or time differs'):
                    media.readback(101)
            self.assertTrue(all(s.stopped and s.destroyed for s in world.sensors))


if __name__ == '__main__':
    unittest.main()
