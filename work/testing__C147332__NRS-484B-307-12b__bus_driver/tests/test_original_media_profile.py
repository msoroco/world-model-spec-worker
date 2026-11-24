"""Real FFmpeg profile proof and deliberate wrong-rate rejection."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from original_media_profile import CAMERAS, audit


class MediaProfileTest(unittest.TestCase):
    def test_four_saved_profiles_and_wrong_rate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in CAMERAS:
                width, height = (1920, 1080) if name == "overview" else (1280, 720)
                subprocess.run(
                    ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                     "-f", "lavfi", "-i", f"color=c=red:s={width}x{height}:r=20",
                     "-frames:v", "2", "-an", "-c:v", "ffv1", "-threads", "1",
                     str(root / (name + ".mkv"))], check=True, capture_output=True)
            self.assertEqual(set(audit(root)["cameras"]), set(CAMERAS))
            subprocess.run(
                ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                 "-f", "lavfi", "-i", "color=c=red:s=1280x720:r=10",
                 "-frames:v", "2", "-an", "-c:v", "ffv1", "-threads", "1",
                 str(root / "approach.mkv")], check=True, capture_output=True)
            with self.assertRaisesRegex(ValueError, "encoding profile differs: approach"):
                audit(root)


if __name__ == "__main__":
    unittest.main()
