import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capture_cameras import CameraError, OriginalCameraCollector, VIEWS


class Image:
    def __init__(self, frame, width, height):
        self.frame, self.width, self.height = frame, width, height

    def save_to_disk(self, path):
        Path(path).write_bytes(b"fake-original-image")


class Sensor:
    def listen(self, callback):
        self.callback = callback


class CameraCollectionTest(unittest.TestCase):
    def setup_collector(self, directory):
        sensors = {view: Sensor() for view in VIEWS}
        collector = OriginalCameraCollector(Path(directory) / "camera-originals", sensors)
        return collector, sensors

    @staticmethod
    def emit(sensors, frame, *, altered=None):
        for view, (width, height) in VIEWS.items():
            if altered and view == altered[0]:
                frame_value, width = altered[1], altered[2]
            else:
                frame_value = frame
            sensors[view].callback(Image(frame_value, width, height))

    def test_complete_four_camera_original_frame_map(self):
        with tempfile.TemporaryDirectory() as directory:
            collector, sensors = self.setup_collector(directory)
            for frame in range(100, 1000):
                self.emit(sensors, frame)
                collector.read_frame(frame, frame * .05)
            receipt = collector.finish(expected_case="exact-case", native_path=Path("native.json"),
                                       native_sha256="source-seal", expected_frames=list(range(100, 1000)))
            packet = json.loads(Path(receipt["path"]).read_text())
            self.assertEqual(packet["frame_count"], 900)
            self.assertEqual(set(packet["views"]), set(VIEWS))
            for view in VIEWS:
                self.assertEqual(len(packet["views"][view]), 900)
                self.assertEqual(packet["views"][view][0]["frame"], 100)

    def test_rejects_mismatched_original_frame_and_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            collector, sensors = self.setup_collector(directory)
            self.emit(sensors, 100, altered=("overview", 101, 1920))
            with self.assertRaisesRegex(CameraError, "frame mismatch"):
                collector.read_frame(100, 5)
        with tempfile.TemporaryDirectory() as directory:
            collector, sensors = self.setup_collector(directory)
            self.emit(sensors, 100, altered=("overview", 100, 800))
            with self.assertRaisesRegex(CameraError, "dimensions mismatch"):
                collector.read_frame(100, 5)

    def test_rejects_missing_camera_and_incomplete_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(CameraError, "four-camera"):
                OriginalCameraCollector(Path(directory) / "camera-originals", {"overview": Sensor()})
            collector, sensors = self.setup_collector(directory)
            self.emit(sensors, 100)
            collector.read_frame(100, 5)
            with self.assertRaisesRegex(CameraError, "900 original"):
                collector.finish(expected_case="exact-case", native_path=Path("native.json"),
                                 native_sha256="source-seal", expected_frames=[100])
