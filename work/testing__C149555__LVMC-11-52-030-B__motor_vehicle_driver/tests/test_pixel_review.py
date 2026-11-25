"""Positive and negative joins for independent reviewed original pixels."""

import copy
import hashlib
import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from freight_contract import SourceError
from pixel_review import audit_pixels
from saved_delivery import CAMERAS


class PixelReviewTests(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd() / ".runtime-work" / "c149555-pixel-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = {"case_id": "case", "native_result_sha256": "native", "media": {}}
        self.review = {"format": "worker-freight-pixel-review-v1", "case_id": "case",
                       "native_result_sha256": "native", "reviewer": "independent reviewer",
                       "method": "original and encoded frame visual inspection", "views": {}}
        self.rgb = {}
        for name, size in CAMERAS.items():
            video = self.root / (name + ".mkv")
            video.write_bytes(b"test video " + name.encode())
            self.manifest["media"][name] = {
                "path": video.name, "sha256": hashlib.sha256(video.read_bytes()).hexdigest()}
            image = Image.new("RGB", size, (20, 40, 60))
            self.rgb[name] = image.tobytes()
            entries = []
            for frame in (20, 400, 800):
                source = self.root / "cameras" / name / f"{frame:06d}.png"
                source.parent.mkdir(parents=True, exist_ok=True)
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                source.write_bytes(buffer.getvalue())
                entry = {"frame": frame,
                         "original_png_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                         "yellow_curb_visible": True, "ego_visible": True,
                         "sign_visible": True, "cargo_visible": True}
                entries.append(entry)
            self.review["views"][name] = entries

    def decode(self, video, frame):
        return self.rgb[video.stem]

    def test_reviewed_pixels_join_original_and_video(self):
        result = audit_pixels(self.manifest, attempt=self.root,
                              review=self.review, decode=self.decode)
        self.assertTrue(result["actual_pixels_reviewed"])
        self.assertEqual(set(result["reviewed_frames"]), set(CAMERAS))

    def test_rejects_false_visibility(self):
        review = copy.deepcopy(self.review)
        review["views"]["reference_corner"][2]["cargo_visible"] = False
        with self.assertRaises(SourceError):
            audit_pixels(self.manifest, attempt=self.root, review=review, decode=self.decode)

    def test_rejects_stale_original_pixels(self):
        source = self.root / "cameras" / "overview" / "000020.png"
        source.write_bytes(b"changed")
        with self.assertRaises(SourceError):
            audit_pixels(self.manifest, attempt=self.root,
                         review=self.review, decode=self.decode)

    def test_rejects_encoded_pixel_difference(self):
        def different(video, frame):
            return b"different"
        with self.assertRaises(SourceError):
            audit_pixels(self.manifest, attempt=self.root,
                         review=self.review, decode=different)

    def test_rejects_stale_media(self):
        (self.root / "overview.mkv").write_bytes(b"changed")
        with self.assertRaises(SourceError):
            audit_pixels(self.manifest, attempt=self.root,
                         review=self.review, decode=self.decode)


if __name__ == "__main__":
    unittest.main()
