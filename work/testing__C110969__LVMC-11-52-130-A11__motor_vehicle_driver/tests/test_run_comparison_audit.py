"""Focused CLI adapter tests; production source auditing remains independent."""
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

BASE = pathlib.Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
sys.path.insert(0, str(BASE))
from comparison_audit import ASSIGNMENT, SUFFIXES
from run_comparison_audit import run


class ComparisonCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".runtime-work")
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.attempts = {}
        for suffix in SUFFIXES:
            case = ASSIGNMENT + "__" + suffix
            folder = self.root / suffix
            folder.mkdir()
            self.attempts[suffix] = folder
            cause = {"traffic_14ft": "traffic_conflict_necessity",
                     "police_14ft": "police_direction_necessity",
                     "device_14ft": "device_direction_necessity"}.get(suffix, "ordinary_destination")
            (folder / "attempt.json").write_text(json.dumps({"case_id": case}) + "\n")
            measurement = {"case_id": case, "original_frame_count": 900, "pose_sha256": suffix,
                           "map_sha256": "a" * 64, "halt_frame_count": 40,
                           "halt_intervals": [{"first_frame": 800, "last_frame": 839}],
                           "minimum_halt_body_gap_m": (15 if suffix == "stop_15ft" else 16 if suffix == "stop_16ft" else 14) * 0.3048}
            context = {"case_id": case, "map_sha256": "a" * 64,
                       "intersection_boundary_sha256": "b" * 64, "vehicle_blueprint": "vehicle.test",
                       "vehicle_length_m": 4.5, "vehicle_width_m": 1.8, "approach": "east",
                       "route_sha256": "c" * 64, "camera_plan_sha256": "d" * 64,
                       "duration_s": 45, "fps": 20,
                       "activity": "stand" if suffix == "stand_14ft" else "stop",
                       "halt_cause": cause, "requested_front_body_gap_ft":
                           15 if suffix == "stop_15ft" else 16 if suffix == "stop_16ft" else 14,
                       "diagnostic_fixture": False}
            for name, value in (("comparison-measurement.json", measurement),
                                ("comparison-context.json", context),
                                ("comparison-observation.json", {"frames": [0, 899], "cause_observed": cause})):
                (folder / name).write_text(json.dumps(value) + "\n")
        self.audited = []

    def source_audit(self, path, *, allow_diagnostic):
        self.assertFalse(allow_diagnostic)
        self.audited.append(path)
        return {"case_id": json.loads(path.read_text())["case_id"],
                "native_source": True, "original_pixels_decoded": True}

    def test_seven_independent_sources_pass_and_remain_unresolved(self):
        receipt = run(self.attempts, self.root / "result", "stop_vs_stand", self.source_audit)
        self.assertEqual(receipt["case_count"], 7)
        self.assertEqual(receipt["requested_comparison_id"], "stop_vs_stand")
        self.assertFalse(receipt["legal_necessity_resolved"])
        self.assertEqual(len(self.audited), 7)

    def test_diagnostic_source_is_rejected(self):
        def diagnostic(path, *, allow_diagnostic):
            return {"case_id": json.loads(path.read_text())["case_id"],
                    "native_source": False, "original_pixels_decoded": False}
        with self.assertRaisesRegex(ValueError, "Original Native source audit"):
            run(self.attempts, self.root / "result", "stop_vs_stand", diagnostic)

    def test_missing_original_observation_is_rejected(self):
        (self.attempts["police_14ft"] / "comparison-observation.json").unlink()
        with self.assertRaisesRegex(ValueError, "regular original file"):
            run(self.attempts, self.root / "result", "stop_vs_stand", self.source_audit)

    def test_wrong_comparison_id_in_receipt_is_rejected(self):
        with patch("run_comparison_audit.audit_comparisons", return_value={"comparison_ids": ["exception_cause"]}):
            with self.assertRaisesRegex(ValueError, "Requested comparison ID absent"):
                run(self.attempts, self.root / "result", "stop_vs_stand", self.source_audit)


if __name__ == "__main__":
    unittest.main()
