import json
import subprocess
import tempfile
import unittest
from pathlib import Path
import importlib.util


spec = importlib.util.spec_from_file_location("camera_encoder", Path(__file__).resolve().parents[1] / "camera_encoder.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class EncoderTests(unittest.TestCase):
    def test_lossless_source_stream_two_frames(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "overview.mkv"
            with module.FFV1Writer(path, 2, 2, 20) as writer:
                writer.write(bytes([0, 0, 255, 255] * 4))
                writer.write(bytes([0, 255, 0, 255] * 4))
            probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                                    "-select_streams", "v:0", "-show_entries",
                                    "stream=codec_name,nb_read_frames", "-of", "json", str(path)],
                                   check=True, capture_output=True, text=True)
            stream = json.loads(probe.stdout)["streams"][0]
            self.assertEqual(stream["codec_name"], "ffv1")
            self.assertEqual(stream["nb_read_frames"], "2")

    def test_wrong_frame_size_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "overview.mkv"
            with module.FFV1Writer(path, 2, 2, 20) as writer:
                with self.assertRaisesRegex(ValueError, "size mismatch"):
                    writer.write(b"bad")
                writer.write(bytes([0, 0, 0, 255] * 4))


if __name__ == "__main__":
    unittest.main()
