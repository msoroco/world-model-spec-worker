import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT.parents[1] / ".runtime-work" / "c125714-2031-encode-tests"
sys.path.insert(0, str(ROOT))
from media_encode import commands, encode


class MediaEncodeTests(unittest.TestCase):
    def setUp(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.media = self.root / "media"
        self.media.mkdir()
        names = ("overview", "approach", "reference_corner", "driver_reference")
        rows = [{"frame": i, "views": {name: {"sha256": "diagnostic"} for name in names}}
                for i in range(900)]
        (self.media / "camera-manifest.json").write_text(json.dumps(rows) + "\n")

    def test_five_videos_from_four_exact_views(self):
        invoked = []
        def fake_run(command, check):
            self.assertTrue(check)
            invoked.append(command)
            Path(command[-1]).write_bytes(b"diagnostic-video")
        codes = encode(self.media, self.root, run=fake_run)
        self.assertEqual(len(invoked), 5)
        self.assertEqual(set(codes), {"overview", "approach", "reference_corner",
                                     "driver_reference", "raw"})
        self.assertTrue(any("xstack=inputs=4" in item for item in
                            commands(self.media, self.root)["raw"]))

    def test_missing_camera_or_frame_rejected_before_encoder(self):
        path = self.media / "camera-manifest.json"
        rows = json.loads(path.read_text())
        del rows[40]["views"]["approach"]
        path.write_text(json.dumps(rows) + "\n")
        with self.assertRaisesRegex(ValueError, "four original camera views"):
            encode(self.media, self.root)
        self.assertFalse((self.root / "overview.mkv").exists())


if __name__ == "__main__":
    unittest.main()
