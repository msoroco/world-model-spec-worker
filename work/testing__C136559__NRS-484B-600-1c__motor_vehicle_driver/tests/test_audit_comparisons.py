import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_comparisons import audit
from speed_source_review import ASSIGNMENT
import test_speed_source_review as fixture_module


class SixComparisonTests(unittest.TestCase):
    def attempts(self, root):
        fixture = fixture_module.OriginalSpeedReviewTests()
        roots = {}
        for suffix in ("above", "below", "equal", "outside_zone", "opposite_direction",
                       "non_authority_sign", "metric_equivalent", "sign_not_in_view"):
            folder = root / suffix
            folder.mkdir()
            speed = 12 if suffix == "below" else 13.4112 if suffix == "equal" else 15
            unit = "km/h" if suffix == "metric_equivalent" else "mph"
            rate = 48.28032 if suffix == "metric_equivalent" else 30
            case, inventory = fixture._attempt(folder, suffix=suffix, speed=speed, unit=unit, rate=rate)
            if suffix in ("outside_zone", "opposite_direction"):
                route = json.loads((folder / "route_occupancy.json").read_text())
                for row in route["samples"]:
                    if suffix == "outside_zone":
                        row["segment_id"] = "outside"
                    else:
                        row["direction"] = "west"
                fixture._change(folder, inventory, "route_occupancy", "samples", route["samples"])
            if suffix == "non_authority_sign":
                fixture._change(folder, inventory, "posted_control", "public_authority_posted", False)
            if suffix == "sign_not_in_view":
                fixture._change(folder, inventory, "posted_control", "sign_in_camera_view", False)
                fixture._change(folder, inventory, "posted_control", "off_camera_reading_assumption_source", "synthetic assumption")
            (folder / "inventory.json").write_text(json.dumps(inventory) + "\n")
            roots[case] = str(folder)
        return roots

    def test_all_six_frozen_comparisons(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = audit(self.attempts(Path(directory)))
            self.assertEqual(len(receipt["comparisons"]), 6)
            self.assertEqual(sum(len(c["pair_audits"]) for c in receipt["comparisons"]), 7)
            self.assertFalse(receipt["physical_completion_confirmed"])

    def test_missing_original_case_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            roots = self.attempts(Path(directory))
            roots.pop(ASSIGNMENT + "__sign_not_in_view")
            with self.assertRaisesRegex(ValueError, "all eight"):
                audit(roots)
