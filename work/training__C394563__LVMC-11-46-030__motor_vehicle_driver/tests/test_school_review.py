"""Review input staging requires sealed local sources before Native capture."""

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import _review


class Library:
    def find(self, name):
        if name not in ("static.prop.school_lane", "static.prop.warning",
                        "walker.pedestrian.0001"):
            raise ValueError("Unknown reviewed asset")
        return name


class ReviewStaging(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.output = self.root / "attempt"
        self.output.mkdir()
        self.review = self.root / "school-review.json"
        packet = {"school_pedestrian_lane_survey": True,
                  "municipal_jurisdiction_reviewed": True,
                  "lane_marker_blueprint": "static.prop.school_lane",
                  "warning_blueprint": "static.prop.warning",
                  "child_blueprint": "walker.pedestrian.0001",
                  "nearest_lane_side_x_m": 0.0}
        for name in ("school_lane_source", "child_identity_source",
                     "warning_asset_source", "municipal_jurisdiction_source"):
            source = self.root / name
            source.write_text(name + " source-shaped fixture\n")
            packet[name + "_path"] = str(source)
            packet[name + "_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        self.review.write_text(json.dumps(packet) + "\n")

    def test_review_staged_with_original_hash(self):
        with patch.dict(os.environ, {"SCHOOL_LANE_REVIEW": str(self.review)}):
            packet = _review(self.output, Library())
        self.assertTrue(packet["school_pedestrian_lane_survey"])
        self.assertEqual((self.output / "original-school-lane-review.json").read_bytes(),
                         self.review.read_bytes())

    def test_missing_review_env_rejected(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "SCHOOL_LANE_REVIEW"):
                _review(self.output, Library())

    def test_stale_child_source_rejected(self):
        packet = json.loads(self.review.read_text())
        Path(packet["child_identity_source_path"]).write_text("changed\n")
        with patch.dict(os.environ, {"SCHOOL_LANE_REVIEW": str(self.review)}):
            with self.assertRaisesRegex(ValueError, "source hash differs"):
                _review(self.output, Library())

    def test_missing_lane_survey_rejected(self):
        packet = json.loads(self.review.read_text())
        packet["school_pedestrian_lane_survey"] = False
        self.review.write_text(json.dumps(packet) + "\n")
        with patch.dict(os.environ, {"SCHOOL_LANE_REVIEW": str(self.review)}):
            with self.assertRaisesRegex(ValueError, "survey missing"):
                _review(self.output, Library())


if __name__ == "__main__":
    unittest.main()
