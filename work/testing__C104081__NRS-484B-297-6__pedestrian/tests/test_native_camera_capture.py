import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_camera_capture import NativeCameraRecorder, CAMERAS


class OriginalImageTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT.parents[1] / ".runtime-work" / "c104081-camera-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sensors = {name: types.SimpleNamespace(id=100 + index)
                        for index, name in enumerate(CAMERAS)}
        self.dimensions = {name: (4, 2) for name in CAMERAS}

    def recorder(self):
        recorder = NativeCameraRecorder(self.root / "encoding", self.sensors,
                                        dimensions=self.dimensions, expected_frames=2)
        self.addCleanup(recorder.abort)
        return recorder

    def images(self, frame):
        return {name: types.SimpleNamespace(frame=frame, sensor_id=self.sensors[name].id,
                    width=4, height=2, raw_data=bytes([frame % 256, 30, 50, 255]) * 8)
                for name in CAMERAS}

    def test_original_pixels_are_encoded_and_bound_to_packet(self):
        recorder = self.recorder()
        self.assertEqual(recorder(40, self.images(40)), {name: 40 for name in CAMERAS})
        self.assertEqual(recorder(41, self.images(41)), {name: 41 for name in CAMERAS})
        packet_dir = self.root / "packet"
        packet_dir.mkdir()
        packet_path = packet_dir / "source-packet.json"
        packet_path.write_text(json.dumps({"source_kind": "original_saved_acquisition"}))
        media = recorder.seal(packet_dir)
        self.assertEqual(set(media), set(CAMERAS))
        self.assertEqual(media["overview"]["sensor_id"], 100)
        self.assertTrue(all((packet_dir / item["path"]).stat().st_size > 0
                            for item in media.values()))
        self.assertEqual(json.loads(packet_path.read_text())["camera_media"], media)
        decoded = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(packet_dir / "overview.mkv"),
             "-f", "rawvideo", "-pix_fmt", "bgra", "pipe:1"],
            capture_output=True, check=True).stdout
        self.assertEqual(decoded, self.images(40)["overview"].raw_data +
                         self.images(41)["overview"].raw_data)

    def test_rejects_duplicate_sensor_and_stale_or_missing_pixels(self):
        self.sensors["approach"].id = self.sensors["overview"].id
        with self.assertRaisesRegex(ValueError, "distinct original camera"):
            self.recorder()
        self.sensors["approach"].id = 101
        recorder = self.recorder()
        images = self.images(40)
        images["approach"].raw_data = b""
        with self.assertRaisesRegex(ValueError, "pixel payload"):
            recorder(40, images)
        self.assertEqual(recorder.count, 0)
        images = self.images(40)
        images["approach"].sensor_id = 999
        with self.assertRaisesRegex(ValueError, "identity"):
            recorder(40, images)
        recorder(40, self.images(40))
        with self.assertRaisesRegex(ValueError, "contiguous"):
            recorder(42, self.images(42))


if __name__ == "__main__":
    unittest.main()
