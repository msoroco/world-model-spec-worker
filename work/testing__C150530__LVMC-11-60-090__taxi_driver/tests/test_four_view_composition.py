"""Small saved-video tests for the four original view join."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from four_view_composition import NAMES, compose, count_frames, digest


class FourViewCompositionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for i, name in enumerate(NAMES):
            subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                            "-f", "lavfi", "-i", f"color=c=0x{i+1:02x}0000:s=32x24:r=20",
                            "-frames:v", "2", "-c:v", "ffv1", str(self.root / (name + ".mkv"))],
                           check=True)
        rows = [{"video_frame": i, "carla_frame": 100 + i, "time_s": i / 20}
                for i in range(2)]
        (self.root / "video_frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))

    def test_composes_and_hash_binds_all_original_views(self):
        receipt = compose(self.root)
        self.assertEqual(receipt["frames"], 2)
        self.assertEqual(count_frames(self.root / "raw.mkv"), 2)
        self.assertEqual(receipt["primary_sha256"], digest(self.root / "raw.mkv"))
        self.assertEqual(set(receipt["sources"]), set(NAMES))
        with self.assertRaises(ValueError):
            compose(self.root)

    def test_rejects_missing_source(self):
        (self.root / "approach.mkv").unlink()
        with self.assertRaisesRegex(ValueError, "source video absent"):
            compose(self.root)
        self.assertFalse((self.root / "raw.mkv").exists())

    def test_rejects_unjoined_frame_map(self):
        (self.root / "video_frames.jsonl").write_text(json.dumps(
            {"video_frame": 1, "carla_frame": 100, "time_s": 0}) + "\n")
        with self.assertRaisesRegex(ValueError, "frame map"):
            compose(self.root)
        self.assertFalse((self.root / "raw.mkv").exists())


if __name__ == "__main__":
    unittest.main()
