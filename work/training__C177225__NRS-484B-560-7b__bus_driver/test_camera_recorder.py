import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from types import SimpleNamespace

from camera_recorder import CameraRecorder
from native_scene import VIEWS


ROOT = Path(__file__).resolve().parents[2]


class Camera:
    def listen(self, callback):
        self.callback = callback

    def emit(self, frame, width=8, height=8):
        self.callback(SimpleNamespace(frame=frame, width=width, height=height,
                                      raw_data=bytes([0, 0, 255, 255]) * width * height))


class CameraRecorderTest(unittest.TestCase):
    def cameras(self):
        return {name: Camera() for name in VIEWS}

    def test_four_source_streams_encode_and_decode_exact_frames(self):
        scratch = ROOT / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='c177225-camera-', dir=scratch) as tmp:
            cameras = self.cameras()
            recorder = CameraRecorder(tmp, cameras, {name: (8, 8) for name in VIEWS})
            for frame in (10, 11, 12):
                for camera in cameras.values():
                    camera.emit(frame)
                recorder.capture(frame)
            self.assertEqual({name: 0 for name in VIEWS}, recorder.close())
            for name in VIEWS:
                output = subprocess.run([
                    'ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                    '-show_entries', 'stream=nb_read_frames', '-of', 'json',
                    str(Path(tmp) / (name + '.mkv'))], capture_output=True,
                    text=True, check=True, timeout=30)
                frames = json.loads(output.stdout)['streams'][0]['nb_read_frames']
                self.assertEqual('3', frames)

    def test_mismatched_native_tick_is_rejected(self):
        scratch = ROOT / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='c177225-camera-', dir=scratch) as tmp:
            cameras = self.cameras()
            recorder = CameraRecorder(tmp, cameras, {name: (8, 8) for name in VIEWS})
            for camera in cameras.values():
                camera.emit(20)
            with self.assertRaisesRegex(ValueError, 'differ from Native tick'):
                recorder.capture(21)
            recorder.close(check=False)


if __name__ == '__main__':
    unittest.main()
