"""Exercise the three exact isolation checks and missing-source rejection."""
import importlib.util
import json
import pathlib
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("comparison_audit", HERE / "comparison_audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class ComparisonAuditTests(unittest.TestCase):
    def test_each_pair_and_changed_fixed_condition(self):
        for comparison_id, row in audit.PAIRS.items():
            with self.subTest(comparison_id=comparison_id):
                first, second = [audit.config_from_construction(case)
                                 for case in row["case_ids"]]
                self.assertEqual(audit.isolate(comparison_id, first, second)[
                    "declared_difference"], row["deliberate_differences"][0])
                second["duration_s"] = 29
                with self.assertRaisesRegex(ValueError, "Fixed condition changed"):
                    audit.isolate(comparison_id, first, second)

    def test_missing_source_and_non_native_result(self):
        comparison_id, row = next(iter(audit.PAIRS.items()))
        scratch = ROOT / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            base = pathlib.Path(directory)
            roots = [base / "a", base / "b"]
            for root, case in zip(roots, row["case_ids"]):
                root.mkdir()
                (root / "config.json").write_text(json.dumps(
                    audit.config_from_construction(case)) + "\n")
                (root / "result.json").write_text(json.dumps({
                    "case_id": case, "provenance_kind": "diagnostic_fixture",
                    "measured_values": {"source_kind": "original_native_measurement",
                                        "frames": 600,
                                        "first_full_sidewalk_return_frame": 385}}) + "\n")
            with self.assertRaisesRegex(ValueError, "Missing original Native"):
                audit.audit(comparison_id, *roots, base / "audit.json")
            for root, case in zip(roots, row["case_ids"]):
                (root / "result.json").write_text(json.dumps({
                    "case_id": case, "provenance_kind": "original_native",
                    "measured_values": {"source_kind": "original_native_measurement",
                                        "frames": 600,
                                        "first_full_sidewalk_return_frame": 385}}) + "\n")
            with self.assertRaisesRegex(ValueError, "Missing original comparison source"):
                audit.audit(comparison_id, *roots, base / "audit.json")


if __name__ == "__main__":
    unittest.main()
