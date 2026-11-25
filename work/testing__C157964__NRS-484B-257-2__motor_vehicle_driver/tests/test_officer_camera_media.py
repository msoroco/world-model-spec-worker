import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from officer_camera import CAMERAS, FourCameraEncoder
from officer_camera_media import CameraMedia


class FakeSensor:
    def __init__(self):
        self.callback = None
        self.stopped = False
        self.destroyed = False

    def listen(self, callback):
        self.callback = callback

    def stop(self):
        self.stopped = True

    def destroy(self):
        self.destroyed = True


class CameraMediaTests(unittest.TestCase):
    def fixtures(self):
        sensors = []

        def spawn(blueprint, transform, **kwargs):
            sensor = FakeSensor()
            sensors.append(sensor)
            return sensor

        world = NS(spawn_actor=spawn)
        blueprints = {name: name + '-blueprint' for name in CAMERAS}
        mounts = {name: {'transform': name + '-mount', 'attach_to': None}
                  for name in CAMERAS}
        actors = {'ego': NS(id=11), 'other': NS(id=33), 'officer': NS(id=12)}
        sizes = {name: (4, 4) for name in CAMERAS}
        return world, blueprints, mounts, actors, sizes, sensors

    def test_four_lossless_video_streams_and_exact_frame_refs(self):
        with tempfile.TemporaryDirectory() as dirname:
            world, blueprints, mounts, actors, sizes, sensors = self.fixtures()
            with CameraMedia(world, dirname, blueprints, mounts, actors,
                             sizes=sizes, timeout_s=1) as media:
                for index, frame in enumerate((101, 102)):
                    for sensor in sensors:
                        sensor.callback(NS(frame=frame, width=4, height=4,
                                           raw_data=bytes([index, 0, 0, 255] * 16)))
                    refs = media.readback(frame)
                    self.assertEqual(set(refs), set(CAMERAS))
                    self.assertEqual({item['video_frame'] for item in refs.values()}, {index})
                    self.assertTrue(all(item['raw_source'].endswith('#frame-' + str(index))
                                        for item in refs.values()))
            self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor in sensors))
            for name in CAMERAS:
                video = Path(dirname) / (name + '.mkv')
                self.assertTrue(video.is_file())
                command = ['ffprobe', '-v', 'error', '-count_frames',
                           '-select_streams', 'v:0', '-show_entries',
                           'stream=codec_name,nb_read_frames', '-of', 'json', str(video)]
                info = json.loads(subprocess.check_output(command, text=True))
                self.assertEqual(info['streams'][0]['codec_name'], 'ffv1')
                self.assertEqual(info['streams'][0]['nb_read_frames'], '2')

    def test_missing_and_mismatched_sensor_packets_rejected(self):
        with tempfile.TemporaryDirectory() as dirname:
            world, blueprints, mounts, actors, sizes, sensors = self.fixtures()
            with self.assertRaisesRegex(ValueError, 'Original camera packet missing'):
                with CameraMedia(world, dirname, blueprints, mounts, actors,
                                 sizes=sizes, timeout_s=0.01) as media:
                    media.readback(101)
        with tempfile.TemporaryDirectory() as dirname:
            world, blueprints, mounts, actors, sizes, sensors = self.fixtures()
            with self.assertRaisesRegex(ValueError, 'Original camera packet frame mismatch'):
                with CameraMedia(world, dirname, blueprints, mounts, actors,
                                 sizes=sizes, timeout_s=0.01) as media:
                    for sensor in sensors:
                        sensor.callback(NS(frame=100, width=4, height=4,
                                           raw_data=bytes([0, 0, 0, 255] * 16)))
                    media.readback(101)

    def test_encoder_rejects_returned_binary_destination(self):
        repo = ROOT.parents[1]
        with self.assertRaisesRegex(ValueError, 'under .runtime-work'):
            FourCameraEncoder(repo / 'work' / 'binary-camera-test',
                              sizes={name: (4, 4) for name in CAMERAS})


if __name__ == '__main__':
    unittest.main()
