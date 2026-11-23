"""CPU source-pixel validation with tiny raw frames, without a recording claim."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from native_media import validate_sources


class NativeMediaTests(unittest.TestCase):
    def setUp(self):
        private = ROOT / ".runtime-work"
        private.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=private)
        self.addCleanup(self.temp.cleanup)
        self.attempt = Path(self.temp.name) / "attempt"
        raw = self.attempt / "raw" / "overview"
        raw.mkdir(parents=True)
        trace, mapping = [], []
        for index in range(2):
            frame, time_s = 400 + index, 20 + index * .05
            pixel = bytes([index]) * 16
            path = raw / f"{frame:08d}.bgra"
            path.write_bytes(pixel)
            pixel_hash = hashlib.sha256(pixel).hexdigest()
            camera = {"frame": frame, "time_s": time_s, "width": 2, "height": 2,
                      "raw_bgra": f"overview/{frame:08d}.bgra", "sha256": pixel_hash}
            trace.append({"frame": frame, "source_frame": frame, "time_s": time_s,
                          "source_packet_sha256": "a" * 64,
                          "camera_sources": {"overview": camera},
                          "physical_acceptance_claimed": False})
            mapping.append({"video_frame": index, "carla_frame": frame,
                            "native_frame": frame, "time_s": time_s,
                            "camera_source_sha256": {"overview": pixel_hash}})
        (self.attempt / "trace.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in trace))
        (self.attempt / "video_frames.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in mapping))

    def test_two_raw_source_frames_join_and_hash(self):
        receipt, files = validate_sources(self.attempt, count=2,
                                          views=(("overview", 2, 2),))
        self.assertEqual(receipt["frames"], 2)
        self.assertEqual(len(files["overview"]), 2)

    def test_changed_raw_pixels_rejected(self):
        raw = self.attempt / "raw" / "overview" / "00000401.bgra"
        raw.write_bytes(b"x" * 16)
        with self.assertRaisesRegex(ValueError, "pixel source differs"):
            validate_sources(self.attempt, count=2, views=(("overview", 2, 2),))

    def test_missing_frame_join_rejected(self):
        path = self.attempt / "video_frames.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[1]["carla_frame"] = 999
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        with self.assertRaisesRegex(ValueError, "camera/frame map join differs"):
            validate_sources(self.attempt, count=2, views=(("overview", 2, 2),))


if __name__ == "__main__":
    unittest.main()
