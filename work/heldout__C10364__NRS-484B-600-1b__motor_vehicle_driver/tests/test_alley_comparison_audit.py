import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / "alley_comparison_audit.py"
spec = importlib.util.spec_from_file_location("alley_comparison_audit", MODULE)
audit_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit_module
spec.loader.exec_module(audit_module)


class ComparisonAuditTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.reports = []
        for speed in (3, 5, 7):
            path = self.root / f"{speed}.json"
            path.write_text(json.dumps({"case_id": f"{audit_module.ASSIGNMENT}__person_{speed}mps",
                "fixed_conditions": {"map": "same-source-map", "geometry": "same-source-geometry",
                                     "camera_plan": "same-four-cameras"},
                "source_sha256": {name: "a"*64 for name in
                    ("participant_footprints.jsonl", "ego_motion.jsonl", "trace.jsonl", "video_frames.jsonl")},
                "maximum_observed_speed_mps": speed, "minimum_pedestrian_gap_m": 1.2,
                "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}))
            self.reports.append(path)

    def edit(self, index, key, value):
        data = json.loads(self.reports[index].read_text())
        data[key] = value
        self.reports[index].write_text(json.dumps(data))

    def test_ordered_measurements_with_fixed_conditions(self):
        result = audit_module.audit(self.reports, "person")
        self.assertTrue(result["comparison_complete"])
        self.assertEqual(result["measured_speeds_mps"], [3, 5, 7])

    def test_rejects_missing_source_and_changed_fixed_condition(self):
        self.edit(1, "source_sha256", {})
        with self.assertRaisesRegex(ValueError, "original source hashes"):
            audit_module.audit(self.reports, "person")
        self.edit(1, "source_sha256", {name: "a"*64 for name in
                    ("participant_footprints.jsonl", "ego_motion.jsonl", "trace.jsonl", "video_frames.jsonl")})
        self.edit(2, "fixed_conditions", {"map": "different"})
        with self.assertRaisesRegex(ValueError, "fixed conditions differ"):
            audit_module.audit(self.reports, "person")

    def test_nonrealized_speed_order_remains_incomplete(self):
        self.edit(2, "maximum_observed_speed_mps", 4)
        result = audit_module.audit(self.reports, "person")
        self.assertFalse(result["comparison_complete"])


if __name__ == "__main__":
    unittest.main()
