"""Tiny FFV1 fixture exercises callback ordering, not physical visibility."""
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "original_camera_recorder.py"
spec = importlib.util.spec_from_file_location("c158196_camera_recorder", MODULE)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)
SCRATCH = Path(__file__).resolve().parents[3] / ".runtime-work" / "c158196-camera-tests"
SCRATCH.mkdir(parents=True, exist_ok=True)


class Sensor:
    def __init__(self):
        self.callback = None
        self.stopped = False

    def listen(self, callback):
        self.callback = callback

    def stop(self):
        self.stopped = True


class Image:
    def __init__(self, frame):
        self.frame = frame
        self.width = self.height = 2
        self.raw_data = bytes([frame * 10, 20, 30, 255] * 4)


class RecorderTest(unittest.TestCase):
    def test_original_four_camera_join_and_lossless_encode(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
            root = Path(temporary)
            scratch = root / "camera-scratch"
            scratch.mkdir()
            output = root / "attempt"
            output.mkdir()
            sensors = {name: Sensor() for name in mod.VIEWS}
            profile = {name: (2, 2) for name in mod.VIEWS}
            recorder = mod.OriginalCameraRecorder(sensors, scratch, profile=profile,
                        expected_frames=2, diagnostic_fixture=True)
            try:
                for frame in (1, 2):
                    for sensor in sensors.values():
                        sensor.callback(Image(frame))
                    snapshot = type("Snapshot", (), {"frame": frame})()
                    self.assertEqual(recorder.read(snapshot), {name: frame for name in mod.VIEWS})
                refs = recorder.finish(output)
                self.assertEqual(set(refs), set(mod.VIEWS))
                for ref in refs.values():
                    result = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i",
                        str(output / ref["path"]), "-f", "null", "-"], capture_output=True)
                    self.assertEqual(result.returncode, 0, result.stderr.decode())
            finally:
                recorder.close()
            self.assertTrue(all(sensor.stopped for sensor in sensors.values()))

    def test_camera_frame_drift_rejected(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
            root = Path(temporary)
            scratch = root / "camera-scratch"
            scratch.mkdir()
            sensors = {name: Sensor() for name in mod.VIEWS}
            recorder = mod.OriginalCameraRecorder(sensors, scratch,
                profile={name: (2, 2) for name in mod.VIEWS},
                expected_frames=2, diagnostic_fixture=True)
            try:
                for sensor in sensors.values():
                    sensor.callback(Image(1))
                snapshot = type("Snapshot", (), {"frame": 2})()
                with self.assertRaisesRegex(ValueError, "frame or dimensions differ"):
                    recorder.read(snapshot)
            finally:
                recorder.close()


if __name__ == "__main__":
    unittest.main()
