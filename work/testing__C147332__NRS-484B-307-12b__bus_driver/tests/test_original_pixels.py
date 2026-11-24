"""Source byte proof for lossless Native camera media."""
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from delivery_audit import _verify_original_pixels, _verify_pixel_map


class PixelBindingTest(unittest.TestCase):
    def test_ffv1_pixel_bytes_and_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frames = [bytes(range(16)), bytes(reversed(range(16)))]
            (root / "camera.raw").write_bytes(b"".join(frames))
            video = root / "camera.mkv"
            command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                       "-f", "rawvideo", "-pixel_format", "bgra", "-video_size", "2x2",
                       "-framerate", "20", "-i", str(root / "camera.raw"),
                       "-c:v", "ffv1", "-pix_fmt", "bgra", str(video)]
            subprocess.run(command, check=True, capture_output=True)
            hashes = [hashlib.sha256(frame).hexdigest() for frame in frames]
            _verify_original_pixels(video, hashes, width=2, height=2)
            with self.assertRaisesRegex(ValueError, "pixel bytes differ"):
                _verify_original_pixels(video, [hashes[0], "0" * 64], width=2, height=2)
            with self.assertRaisesRegex(ValueError, "extra decoded pixel frames"):
                _verify_original_pixels(video, hashes[:1], width=2, height=2)

    def test_missing_native_hash_map_rejected(self):
        with self.assertRaisesRegex(ValueError, "pixel hash map missing"):
            _verify_pixel_map(Path("unused"), [{"camera_names": ["overview"]}])


if __name__ == "__main__":
    unittest.main()
