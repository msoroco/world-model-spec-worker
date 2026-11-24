import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_camera_adapter import NativeCameraAdapter
from native_media import CAMERAS
from PIL import Image
import io


class Sensor:
    type_id = "sensor.camera.rgb"

    def __init__(self, size):
        self.attributes = {"image_size_x": str(size[0]), "image_size_y": str(size[1])}
        self.callback = None
        self.stopped = False

    def listen(self, callback):
        self.callback = callback

    def emit(self, frame, size=None, short=False, timestamp=None):
        width, height = size or (int(self.attributes["image_size_x"]),
                                 int(self.attributes["image_size_y"]))
        raw = bytes((5, 10, 20, 255)) * (width * height)
        if short:
            raw = raw[:-1]
        self.callback(SimpleNamespace(frame=frame, timestamp=frame * 0.05 if timestamp is None else timestamp,
                                      width=width, height=height,
                                      raw_data=raw))

    def stop(self):
        self.stopped = True


class CameraAdapterTests(unittest.TestCase):
    def setUp(self):
        self.sensors = {key: Sensor(size) for key, size in CAMERAS.items()}
        self.adapter = NativeCameraAdapter(self.sensors, timeout_s=0.01)

    def tearDown(self):
        self.adapter.close()

    def test_original_callbacks_join_and_lossless_color(self):
        for sensor in self.sensors.values():
            sensor.emit(8)
        result = self.adapter.capture(SimpleNamespace(frame=8, timestamp=SimpleNamespace(elapsed_seconds=0.4)), None)
        self.assertEqual(set(result), set(CAMERAS))
        for key, entry in result.items():
            self.assertEqual(entry["frame"], 8)
            with Image.open(io.BytesIO(entry["png"])) as image:
                self.assertEqual(image.size, CAMERAS[key])
                self.assertEqual(image.getpixel((0, 0)), (20, 10, 5))
        self.assertTrue(all(sensor.stopped for sensor in self.sensors.values()) is False)

    def test_missing_callback_and_wrong_frame_rejected(self):
        for key, sensor in self.sensors.items():
            if key != "approach":
                sensor.emit(3)
        with self.assertRaisesRegex(ValueError, "missing original"):
            self.adapter.capture(SimpleNamespace(frame=3, timestamp=SimpleNamespace(elapsed_seconds=0.15)), None)
        self.sensors["approach"].emit(4)
        with self.assertRaisesRegex(ValueError, "missing original"):
            self.adapter.capture(SimpleNamespace(frame=3, timestamp=SimpleNamespace(elapsed_seconds=0.15)), None)

    def test_bad_callback_dimensions_and_bytes_rejected(self):
        for sensor in self.sensors.values():
            sensor.emit(1)
        self.sensors["overview"].emit(1, short=True)
        with self.assertRaisesRegex(ValueError, "byte count differs"):
            self.adapter.capture(SimpleNamespace(frame=1, timestamp=SimpleNamespace(elapsed_seconds=0.05)), None)
        self.assertIsNone(self.adapter.last_frame)
        self.sensors["overview"].emit(1)
        recovered = self.adapter.capture(SimpleNamespace(frame=1, timestamp=SimpleNamespace(elapsed_seconds=0.05)), None)
        self.assertEqual({entry["frame"] for entry in recovered.values()}, {1})

    def test_timestamp_drift_rejected_without_consuming_frame(self):
        for sensor in self.sensors.values():
            sensor.emit(5)
        self.sensors["overview"].emit(5, timestamp=0.3)
        snapshot = SimpleNamespace(frame=5, timestamp=SimpleNamespace(elapsed_seconds=0.25))
        with self.assertRaisesRegex(ValueError, "camera timestamp differs"):
            self.adapter.capture(snapshot, None)
        self.assertIsNone(self.adapter.last_frame)
        self.sensors["overview"].emit(5)
        self.assertEqual({entry["frame"] for entry in self.adapter.capture(snapshot, None).values()}, {5})

    def test_wrong_sensor_profile_rejected(self):
        sensors = {key: Sensor(size) for key, size in CAMERAS.items()}
        sensors["overview"].type_id = "sensor.camera.depth"
        with self.assertRaisesRegex(ValueError, "RGB camera required"):
            NativeCameraAdapter(sensors)


if __name__ == "__main__":
    unittest.main()
