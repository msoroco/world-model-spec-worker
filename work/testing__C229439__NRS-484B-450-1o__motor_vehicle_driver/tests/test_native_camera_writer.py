import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


FOLDER = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("native_camera_writer", FOLDER / "native_camera_writer.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Sensor:
    type_id = "sensor.camera.rgb"
    attributes = {"image_size_x": "2", "image_size_y": "2"}

    def listen(self, callback):
        self.callback = callback


class WriterTests(unittest.TestCase):
    def setUp(self):
        scratch = FOLDER.parents[1] / ".runtime-work" / "c229439-camera-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.sensors = {key: Sensor() for key in module.DIMENSIONS}
        dims = {key: (2, 2) for key in module.DIMENSIONS}
        self.writer = module.NativeCameraWriter(self.sensors, self.temp.name, dims)

    def tearDown(self):
        for archive in self.writer.archives.values():
            archive.close()
        self.temp.cleanup()

    def tick(self, frame, bad_camera=None):
        stamp = frame * 0.05
        for name, sensor in self.sensors.items():
            camera_frame = frame + 1 if name == bad_camera else frame
            sensor.callback(SimpleNamespace(frame=camera_frame, timestamp=stamp,
                                            width=2, height=2, raw_data=bytes(16)))
        return self.writer.capture(SimpleNamespace(frame=frame,
                                                    timestamp=SimpleNamespace(elapsed_seconds=stamp)))

    def test_complete_original_archives_and_row_bindings(self):
        rows = []
        for frame in range(900):
            bindings = self.tick(frame)
            rows.append({"frame": frame, "time_s": frame * 0.05, "camera_frames": bindings})
        refs = self.writer.close()
        self.assertEqual(refs["front"]["frame_count"], 900)
        sealed = module.seal_rows(self.temp.name, rows, refs)
        self.assertEqual(set(sealed["camera_archives"]), set(module.DIMENSIONS))

    def test_wrong_callback_frame_rejected(self):
        with self.assertRaisesRegex(ValueError, "camera callback frame"):
            self.tick(0, "left")

    def test_missing_frames_rejected_on_close(self):
        self.tick(0)
        with self.assertRaisesRegex(ValueError, "900-frame capture incomplete"):
            self.writer.close()


if __name__ == "__main__":
    unittest.main()
