"""CPU checks for original pixel/frame joins and lossless encoding."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from native_media import encode, sha, validate_sources


VIEWS = (("overview", 2, 2), ("approach", 2, 2),
         ("reference_corner", 2, 2), ("driver_reference", 2, 2))


class NativeMediaTests(unittest.TestCase):
    def setUp(self):
        self.root = HERE.parents[1] / ".runtime-work"
        self.root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=self.root)
        self.addCleanup(self.temp.cleanup)
        self.attempt = Path(self.temp.name) / "attempt"
        self.attempt.mkdir()
        source = "a" * 64
        trace, mapping = [], []
        for index in range(2):
            frame = 400 + index
            time_s = 20 + index * .05
            cameras, hashes = {}, {}
            for name, width, height in VIEWS:
                pixels = bytes([index + 1, 2, 3, 255]) * (width * height)
                raw = self.attempt / "raw" / name / f"{frame}.bgra"
                raw.parent.mkdir(parents=True, exist_ok=True)
                raw.write_bytes(pixels)
                digest = hashlib.sha256(pixels).hexdigest()
                hashes[name] = digest
                cameras[name] = {"frame": frame, "time_s": time_s,
                                 "width": width, "height": height,
                                 "raw_bgra": f"{name}/{frame}.bgra", "sha256": digest}
            trace.append({"frame": frame, "time_s": time_s, "source_frame": frame,
                          "camera_sources": cameras, "source_packet_sha256": source,
                          "physical_acceptance_claimed": False})
            mapping.append({"video_frame": index, "carla_frame": frame,
                            "native_frame": frame, "time_s": time_s,
                            "camera_source_sha256": hashes})
        self.trace, self.mapping = trace, mapping
        self.write()

    def write(self):
        for name, rows in (("trace.jsonl", self.trace), ("video_frames.jsonl", self.mapping)):
            (self.attempt / name).write_text("".join(json.dumps(row) + "\n" for row in rows))

    def test_validated_source_encodes_same_two_frames_losslessly(self):
        receipt, files = validate_sources(self.attempt, count=2, views=VIEWS)
        self.assertEqual(receipt["frames"], 2)
        self.assertEqual(receipt["trace_sha256"], sha(self.attempt / "trace.jsonl"))
        video = self.attempt / "overview.mkv"
        encode(files["overview"], 2, 2, video)
        decoded = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video),
                                  "-f", "rawvideo", "-pix_fmt", "bgra", "pipe:1"],
                                 capture_output=True, check=True).stdout
        self.assertEqual(decoded, b"".join(path.read_bytes() for path in files["overview"]))

    def test_tampered_camera_bytes_or_frame_map_rejected(self):
        raw = self.attempt / "raw" / "overview" / "400.bgra"
        raw.write_bytes(b"\x00" * 16)
        with self.assertRaisesRegex(ValueError, "pixel source differs"):
            validate_sources(self.attempt, count=2, views=VIEWS)
        raw.write_bytes(bytes([1, 2, 3, 255]) * 4)
        self.mapping[1]["camera_source_sha256"]["overview"] = "b" * 64
        self.write()
        with self.assertRaisesRegex(ValueError, "camera source identity differs"):
            validate_sources(self.attempt, count=2, views=VIEWS)

    def test_missing_frame_and_escape_rejected(self):
        self.mapping.pop()
        self.write()
        with self.assertRaisesRegex(ValueError, "duration differs"):
            validate_sources(self.attempt, count=2, views=VIEWS)
        self.mapping.append({"video_frame": 1, "carla_frame": 401,
                             "native_frame": 401, "time_s": 20.05,
                             "camera_source_sha256": {name: self.trace[1]["camera_sources"][name]["sha256"]
                                                      for name, _, _ in VIEWS}})
        self.trace[1]["camera_sources"]["overview"]["raw_bgra"] = "../../outside.bgra"
        self.write()
        with self.assertRaisesRegex(ValueError, "pixel source differs"):
            validate_sources(self.attempt, count=2, views=VIEWS)


if __name__ == "__main__":
    unittest.main()
