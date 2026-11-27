"""Saved comparison preserves common road and independent authority source."""

import json
from pathlib import Path
import tempfile
import unittest

from comparison_audit import audit
from measure_uturn import digest
from test_measure_uturn import fixture


class DividedRoadComparisonTest(unittest.TestCase):
    def setUp(self):
        root = Path.cwd() / ".runtime-work"
        root.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=root)
        self.base = Path(self.tmp.name)
        self.opening = self.base / "opening"
        self.barrier = self.base / "barrier"
        self.opening.mkdir()
        self.barrier.mkdir()
        fixture(self.opening, "authorized_opening")
        fixture(self.barrier, "barrier_crossing")
        for folder in (self.opening, self.barrier):
            case = json.loads((folder / "request.json").read_text())["case_id"]
            (folder / "config.json").write_text(json.dumps({
                "selected_case_id": case, "cell_id": "C82860",
                "law_id": "NRS-484B-227-1", "actor": "motor_vehicle_driver",
                "rate_hz": 20, "duration_s": 30, "frames": 600,
                "cameras": ["overview", "approach", "reference_corner", "driver_reference"],
                "physical_completion": "full-body U-turn"}) + "\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_original_shaped_geometry_contrast_is_unjudged(self):
        result = audit(self.opening, self.barrier)
        self.assertTrue(result["fixed_context_checked"])
        self.assertTrue(result["diagnostic_geometry_contrast"])
        self.assertFalse(result["physical_or_legal_acceptance"])

    def test_changed_authority_source_and_map_rejected(self):
        source = self.barrier / "authority-source.json"
        source.write_text('{"public_authority_establishment":"changed"}\n')
        review = json.loads((self.barrier / "authority-review.json").read_text())
        review["source"]["sha256"] = digest(source)
        (self.barrier / "authority-review.json").write_text(json.dumps(review) + "\n")
        with self.assertRaisesRegex(ValueError, "Fixed authority source differs"):
            audit(self.opening, self.barrier)
        fixture(self.barrier, "barrier_crossing")
        context = json.loads((self.barrier / "divided-road-context.json").read_text())
        context["native_roadways"][0]["heading_deg"] = 2
        (self.barrier / "divided-road-context.json").write_text(json.dumps(context) + "\n")
        with self.assertRaisesRegex(ValueError, "Fixed original road or median context differs"):
            audit(self.opening, self.barrier)

    def test_changed_camera_or_duration_rejected(self):
        path = self.barrier / "config.json"
        original = json.loads(path.read_text())
        changed = dict(original, duration_s=29)
        path.write_text(json.dumps(changed) + "\n")
        with self.assertRaisesRegex(ValueError, "Fixed camera, duration"):
            audit(self.opening, self.barrier)
        changed = dict(original, cameras=["overview"])
        path.write_text(json.dumps(changed) + "\n")
        with self.assertRaisesRegex(ValueError, "Fixed camera, duration"):
            audit(self.opening, self.barrier)


if __name__ == "__main__":
    unittest.main()
