"""Synthetic positive and negative tests for independent duration comparison."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "native"))
from comparison_audit import ASSIGNMENT, HELD, audit
from duration_policy import TARGETS, TOTAL_FRAMES


class ComparisonAuditTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[3] /
                                                ".runtime-work")
        self.root = Path(self.temp.name)
        self.paths = {}
        for suffix, target in TARGETS.items():
            folder = self.root / suffix
            folder.mkdir()
            sources = {}
            for name in ("frame_map", "actor_motion", "source_review", "camera_frame_map"):
                source = folder / (name + ".json")
                source.write_text(json.dumps({"synthetic": name, "case": suffix}) + "\n")
                sources[name] = {"path": source.name,
                                 "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
            report = {"format": "c229398-measured-duration-report-v1",
                      "case_id": ASSIGNMENT + "__" + suffix,
                      "capture_frames": TOTAL_FRAMES, "rate_hz": 20,
                      "provenance_kind": "synthetic_fixture",
                      "requested_duration_s": target,
                      "stationary_duration_ms": int(target * 1000),
                      "sources": sources,
                      "road_sha256": "same road", "device_review_sha256": "same device",
                      "parking_review_sha256": "same activity",
                      "street_review_sha256": "same street",
                      "civil_clock_review_sha256": "same clock",
                      "camera_policy_sha256": "same cameras",
                      "weather": "same clear night", "parking_target_xy_m": [40.0, -1.75]}
            self.paths[suffix] = folder / "measured.json"
            self.paths[suffix].write_text(json.dumps(report) + "\n")

    def tearDown(self):
        self.temp.cleanup()

    def change(self, suffix, key, value):
        path = self.paths[suffix]
        report = json.loads(path.read_text())
        report[key] = value
        path.write_text(json.dumps(report) + "\n")

    def test_positive(self):
        result = audit(self.paths)
        self.assertFalse(result["physical_or_legal_acceptance"])
        self.assertEqual(set(result["held_conditions"]), set(HELD))

    def test_held_condition_and_target_negative(self):
        self.change("at_30", "weather", "fog")
        with self.assertRaisesRegex(ValueError, "changed held condition"):
            audit(self.paths)
        self.change("at_30", "weather", "same clear night")
        self.change("at_30", "requested_duration_s", 1801.0)
        with self.assertRaisesRegex(ValueError, "target changed"):
            audit(self.paths)

    def test_missing_or_changed_source_negative(self):
        source = self.paths["above_30"].parent / "actor_motion.json"
        source.write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "source hash differs"):
            audit(self.paths)
        source.unlink()
        with self.assertRaisesRegex(ValueError, "source missing"):
            audit(self.paths)

    def test_incomplete_capture_negative(self):
        self.change("below_30", "capture_frames", TOTAL_FRAMES - 1)
        with self.assertRaisesRegex(ValueError, "Incomplete duration capture"):
            audit(self.paths)


if __name__ == "__main__":
    unittest.main()
