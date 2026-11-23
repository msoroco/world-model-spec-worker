"""Pinned full-decode check on tiny diagnostic FFV1 pixels."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from source_decode import decode_one


class SourceDecodeTests(unittest.TestCase):
    def setUp(self):
        self.assertIn("SCENARIO_PIPELINE_OUTPUT_ROOT", os.environ)
        private = ROOT / ".runtime-work"
        private.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=private)
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def video(self, name, uniform=False):
        path = self.folder / name
        one = bytes([20, 40, 60, 255, 100, 120, 140, 255,
                     50, 70, 90, 255, 150, 170, 190, 255])
        if uniform:
            one = bytes([80, 80, 80, 255]) * 4
        two = one[::-1] if not uniform else one
        subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                        "-f", "rawvideo", "-pixel_format", "bgra",
                        "-video_size", "2x2", "-framerate", "20",
                        "-i", "pipe:0", "-frames:v", "2", "-an",
                        "-c:v", "ffv1", "-pix_fmt", "bgra", str(path)],
                       input=one + two, check=True)
        return path

    def test_two_full_original_frames_have_pinned_receipt(self):
        video = self.video("moving.mkv")
        receipt = self.folder / "decode.json"
        result = decode_one(video, receipt, "a" * 64, 2, (2, 2))
        self.assertEqual(result["frames"], 2)
        self.assertEqual(result["checks"]["frame_count"], "all-decoded-frames")
        self.assertEqual(len(result["checks"]["nonuniform_camera_samples_v1"]), 64)
        self.assertEqual(result["mapping_sha256"], "a" * 64)
        self.assertEqual(decode_one(video, receipt, "a" * 64, 2, (2, 2)), result)

    def test_blank_sampled_pixels_rejected(self):
        video = self.video("blank.mkv", uniform=True)
        with self.assertRaisesRegex(ValueError, "sampled-uniform"):
            decode_one(video, self.folder / "blank-decode.json", "b" * 64,
                       2, (2, 2))


if __name__ == "__main__":
    unittest.main()
