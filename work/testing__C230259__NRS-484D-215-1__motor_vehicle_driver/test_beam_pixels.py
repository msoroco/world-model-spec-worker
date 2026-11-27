"""CPU proof that original source pixels and ROI joins are actually read."""
from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
import zipfile
import subprocess
from pathlib import Path

from PIL import Image

from beam_pixels import measure

TEMP_ROOT = Path(__file__).resolve().parents[2] / ".runtime-work" / "c230259-pixel-tests"


def _fixture(root: Path, count: int = 9, start_frame: int = 251):
    frames = list(range(start_frame, start_frame + count))
    maps = []
    rois = []
    for frame in frames:
        maps.append({"frame": frame, "approach_source_frame": frame,
                     "driver_reference_source_frame": frame})
        rois.append({"frame": frame, "source_kind": "reviewed_original_projection",
                     "diagnostic_fixture": True,
                     "regions": {"person": [1, 1, 5, 5], "target_vehicle": [6, 1, 10, 5],
                                 "oncoming_eye": [1, 6, 5, 10]}})
    for name, rows in (("camera-frame-map.jsonl", maps), ("roi-frames.jsonl", rois)):
        (root / name).write_text("".join(json.dumps(row) + "\n" for row in rows))
    for view, color in (("approach", (25, 35, 45)), ("driver_reference", (100, 110, 120))):
        with zipfile.ZipFile(root / (view + ".zip"), "w") as archive:
            for frame in frames:
                output = io.BytesIO()
                Image.new("RGB", (16, 12), color).save(output, format="PNG")
                archive.writestr(str(frame) + ".png", output.getvalue())
    names = ("roi-frames.jsonl", "approach.zip", "driver_reference.zip", "camera-frame-map.jsonl")
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}


class BeamPixelTests(unittest.TestCase):
    def setUp(self):
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix="pixels-", dir=TEMP_ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.hashes = _fixture(self.root)

    def test_person_vehicle_eye_pixel_values(self):
        value = measure(self.root, self.hashes, expected_frames=9, diagnostic=True)
        self.assertEqual(value["frame_count"], 9)
        self.assertAlmostEqual(value["rows"][0]["person_mean_luma_8bit"], 33.596)
        self.assertGreater(value["rows"][0]["oncoming_eye_mean_luma_8bit"], 100)
        self.assertFalse(value["physical_glare_claimed"])

    def test_changed_original_png_archive_rejected(self):
        (self.root / "approach.zip").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "missing or changed"):
            measure(self.root, self.hashes, expected_frames=9, diagnostic=True)

    def test_stale_roi_frame_join_rejected(self):
        path = self.root / "roi-frames.jsonl"
        rows = [json.loads(x) for x in path.read_text().splitlines()]
        rows[3]["frame"] -= 1
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        hashes = {**self.hashes, path.name: hashlib.sha256(path.read_bytes()).hexdigest()}
        with self.assertRaisesRegex(ValueError, "ROI frame identity"):
            measure(self.root, hashes, expected_frames=9, diagnostic=True)

    def test_missing_eye_roi_rejected(self):
        path = self.root / "roi-frames.jsonl"
        rows = [json.loads(x) for x in path.read_text().splitlines()]
        del rows[2]["regions"]["oncoming_eye"]
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        hashes = {**self.hashes, path.name: hashlib.sha256(path.read_bytes()).hexdigest()}
        with self.assertRaisesRegex(ValueError, "oncoming-eye ROIs"):
            measure(self.root, hashes, expected_frames=9, diagnostic=True)

    def test_diagnostic_movie_pixels_and_hashes(self):
        for view, color in (("approach", "red"), ("driver_reference", "blue")):
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                            "-i", "color=c=" + color + ":s=1280x720:r=20", "-frames:v", "9",
                            "-c:v", "ffv1", str(self.root / (view + ".mkv"))], check=True)
        hashes = {name: hashlib.sha256((self.root / name).read_bytes()).hexdigest()
                  for name in ("roi-frames.jsonl", "camera-frame-map.jsonl", "approach.mkv", "driver_reference.mkv")}
        value = measure(self.root, hashes, expected_frames=9, diagnostic=True)
        self.assertEqual(value["frame_count"], 9)
        self.assertGreater(value["rows"][0]["person_mean_luma_8bit"], 40)
        self.assertGreater(value["rows"][0]["oncoming_eye_mean_luma_8bit"], 15)
        (self.root / "approach.mkv").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "missing or changed"):
            measure(self.root, hashes, expected_frames=9, diagnostic=True)


if __name__ == "__main__":
    unittest.main()
