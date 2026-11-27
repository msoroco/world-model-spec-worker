"""Source inventory and original-review rejection tests."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from source_review import ASSIGNMENT, SOURCES, join


class SourceReviewTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "source_context").mkdir()
        self.case = ASSIGNMENT + "__probe_04"
        refs = {}
        for name in SOURCES:
            path = self.root / "source_context" / (name + ".txt")
            path.write_text("diagnostic " + name + "\n")
            refs[name] = {"path": "source_context/" + name + ".txt",
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        self.review = {"assignment_id": ASSIGNMENT, "case_id": self.case,
                       "review_kind": "synthetic_diagnostic", "sources": refs}
        self.save()

    def save(self):
        (self.root / "emergency-review.json").write_text(json.dumps(self.review) + "\n")

    def test_diagnostic_is_source_joined_but_not_original(self):
        self.assertFalse(join(self.root, self.case, diagnostic=True)["source_reviewed"])
        with self.assertRaisesRegex(ValueError, "Original Native"):
            join(self.root, self.case)

    def test_missing_and_altered_source_rejected(self):
        (self.root / "source_context" / "vehicle_authorization.txt").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source"):
            join(self.root, self.case, diagnostic=True)
        (self.root / "source_context" / "vehicle_authorization.txt").write_text("altered\n")
        with self.assertRaisesRegex(ValueError, "hash differs"):
            join(self.root, self.case, diagnostic=True)

    def test_original_hand_signal_requires_pixel_review(self):
        self.review["review_kind"] = "original_native"
        self.review.update({name: True for name in (
            "vehicle_authorized", "flashing_equipment_qualifies",
            "flashing_lamps_reviewed_in_original_pixels", "lane_graph_reviewed",
            "roadway_reviewed", "traffic_reviewed", "weather_reviewed",
            "officer_direction_reviewed")})
        self.review["hand_signal_visibility_reviewed"] = False
        self.save()
        with self.assertRaisesRegex(ValueError, "visible hand signal"):
            join(self.root, self.case)
        self.review["hand_signal_visibility_reviewed"] = True
        self.save()
        self.assertTrue(join(self.root, self.case)["source_reviewed"])


if __name__ == "__main__":
    unittest.main()
