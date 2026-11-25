"""Independent pixel review must bind exact saved sources and reject weak review."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from original_pixel_audit import CAMERAS, audit, sha


class PixelReviewTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).parent / "pixel-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.root = Path(self.temporary.name)
        self.attempt = self.root / "attempt"
        self.processed = self.root / "processed"
        self.attempt.mkdir()
        (self.processed / "analysis").mkdir(parents=True)
        (self.processed / "processing.json").write_text("{}\n")
        (self.processed / "analysis/result.json").write_text("{}\n")
        self.case = "testing__C111125__NRS-484B-307-8d__cycle_or_scooter_operator__fails_to_yield"
        pixels = b"\x08" * (8 * 8 * 3)
        for name in CAMERAS:
            (self.attempt / (name + ".mkv")).write_bytes(name.encode())
        self.packet = {
            "case_id": self.case, "reviewer": "independent diagnostic test",
            "diagnostic_fixture": True, "actual_original_pixels": False,
            "processing_sha256": sha(self.processed / "processing.json"),
            "result_sha256": sha(self.processed / "analysis/result.json"),
            "original_camera_sha256": {name: sha(self.attempt / (name + ".mkv")) for name in CAMERAS},
            "observations": [{"camera": name, "frame_index": index,
                              "crop_xywh": [0, 0, 8, 8],
                              "rgb24_sha256": hashlib.sha256(pixels).hexdigest(),
                              "bicycle_rider_visible": True,
                              "official_device_visible": True,
                              "directed_participant_visible": True}
                             for index, name in enumerate(CAMERAS)]}
        self.review = self.root / "review.json"
        self.pixels = pixels

    def tearDown(self):
        self.temporary.cleanup()

    def check(self, **changes):
        self.packet.update(changes)
        self.review.write_text(json.dumps(self.packet) + "\n")
        return audit(self.attempt, self.processed, self.case, self.review,
                     diagnostic=self.packet["diagnostic_fixture"],
                     source_auditor=lambda *args, **kwargs: {
                         "software_checks_passed": True, "joined_frames": 900},
                     crop_decoder=lambda *args: self.pixels)

    def test_diagnostic_four_camera_source_bound_review(self):
        self.assertEqual(self.check()["status"], "software_diagnostic_only")

    def test_rejects_changed_original_video(self):
        (self.attempt / "overview.mkv").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "camera source differs"):
            self.check()

    def test_rejects_uniform_physical_crop(self):
        with self.assertRaisesRegex(ValueError, "uniform original pixel crop"):
            self.check(diagnostic_fixture=False, actual_original_pixels=True)

    def test_rejects_missing_camera_review(self):
        self.packet["observations"].pop()
        with self.assertRaisesRegex(ValueError, "four original camera observations required"):
            self.check()


if __name__ == "__main__":
    unittest.main()
