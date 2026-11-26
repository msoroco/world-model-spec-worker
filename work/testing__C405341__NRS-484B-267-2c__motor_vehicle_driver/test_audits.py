"""Independent audit negative gates and frame-level cue checks."""

import tempfile
from pathlib import Path
import unittest

from comparison_audit import audit_comparison
from delivery_audit import audit_attempt, audit_cues
from emergency_construction import CASES
from native_packet import AID


class AuditTests(unittest.TestCase):
    def test_missing_original_is_rejected(self):
        scratch = Path(__file__).resolve().parents[2] / ".runtime-work/c405341/tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            case_id = AID + "__" + CASES[0].suffix
            with self.assertRaisesRegex(ValueError, "original attempt missing"):
                audit_attempt(root / "missing", root / "result.json", case_id)

    def test_cue_join_and_pixel_review_are_required(self):
        history = [{"frame": i, "native_frame": 100 + i, "movement_visible": i == 340}
                   for i in range(900)]
        cues = [{"frame": i, "native_frame": 100 + i, "camera": "driver_reference",
                 "pixel_review_source": "original-roi", "reviewer": "independent",
                 "roi_pixels": [1, 2, 3, 4], "frame_md5": "0" * 32,
                 "movement_visible": i == 340}
                for i in range(900)]
        self.assertEqual(audit_cues(cues, history, CASES[0])["movement_visible_frames"], 1)
        cues[340]["native_frame"] += 1
        with self.assertRaisesRegex(ValueError, "frame join"):
            audit_cues(cues, history, CASES[0])

    def test_comparison_requires_exact_original_audits(self):
        with self.assertRaisesRegex(ValueError, "comparison must include every exact case"):
            audit_comparison("movement_visibility", {})


if __name__ == "__main__":
    unittest.main()
