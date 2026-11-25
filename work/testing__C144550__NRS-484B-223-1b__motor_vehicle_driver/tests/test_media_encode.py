import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from camera_capture import SIZES
from media_encode import encode


class MediaEncodeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd() / ".runtime-work")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        media = self.root / "original-camera-frames"
        media.mkdir()
        self.manifest = media / "camera-manifest.json"
        self.rows = [{"frame": i, "views": {name: {} for name in SIZES}}
                     for i in range(900)]
        self.manifest.write_text(json.dumps(self.rows) + "\n")

    def test_lossless_four_views_and_composed_primary_are_requested(self):
        commands = []
        def fake_run(command, check):
            commands.append(command)
            Path(command[-1]).write_bytes(b"encoded")
        receipt = encode(self.root, run=fake_run)
        self.assertEqual(set(receipt), {*SIZES, "raw"})
        self.assertEqual(len(commands), 5)
        self.assertTrue(all("ffv1" in cmd and "900" in cmd for cmd in commands))
        self.assertIn("xstack=inputs=4", " ".join(commands[-1]))

    def test_missing_original_camera_frame_prevents_encoding(self):
        self.rows.pop()
        self.manifest.write_text(json.dumps(self.rows) + "\n")
        with self.assertRaisesRegex(ValueError, "900 frames"):
            encode(self.root, run=lambda *a, **kw: self.fail("encoder ran"))


if __name__ == "__main__":
    unittest.main()
