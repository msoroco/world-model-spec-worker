import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("audit_comparison", ROOT / "audit_comparison.py")
audit_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit_module)
PLAN = json.loads((ROOT / "case-plan.json").read_text())
STATUTORY_REVIEW = json.loads((ROOT / "statutory-review.json").read_text())


def records(comparison):
    base = {
        "law_id": PLAN["law_id"], "cell_id": PLAN["cell_id"],
        "actor": PLAN["actor"], "governing_signal_id": "head-307-8a",
        "rate_hz": 20, "camera_profile": "four-camera-v1",
        "road_geometry_sha256": "a" * 64, "signal_program_sha256": "b" * 64,
        "native_source_sha256": "c" * 64, "camera_source_sha256": "d" * 64,
        "sealed_result_sha256": "e" * 64, "source_kind": "native_observed",
    }
    variable = comparison["deliberate_differences"][0]
    return [dict(base, case_id=case_id, measurements={variable: value})
            for case_id, value in zip(comparison["case_ids"], ("reference", "contrast"))]


class ComparisonTest(unittest.TestCase):
    def test_every_planned_pair_has_observable_difference(self):
        self.assertEqual(len(PLAN["comparisons"]), 1)
        self.assertEqual(len(PLAN["cases"]), 2)
        self.assertEqual(len(STATUTORY_REVIEW["controlled_comparisons"]), 12)
        self.assertEqual(len(STATUTORY_REVIEW["branches"]), 24)
        for comparison in PLAN["comparisons"]:
            with self.subTest(comparison=comparison["comparison_id"]):
                observed = audit_module.audit(PLAN, comparison["comparison_id"], records(comparison))
                self.assertEqual(observed["case_ids"], comparison["case_ids"])

    def test_rejects_missing_source_and_fixed_condition(self):
        comparison = PLAN["comparisons"][0]
        for key, bad, message in [
            ("native_source_sha256", None, "lacks source binding"),
            ("source_kind", "authored_cpu_request", "lacks original Native"),
            ("governing_signal_id", "other-head", "Fixed comparison condition differs"),
        ]:
            with self.subTest(key=key):
                pair = records(comparison)
                pair[1][key] = bad
                with self.assertRaisesRegex(ValueError, message):
                    audit_module.audit(PLAN, comparison["comparison_id"], pair)

    def test_rejects_no_observed_difference_and_wrong_member(self):
        comparison = PLAN["comparisons"][0]
        pair = records(comparison)
        pair[1]["measurements"] = pair[0]["measurements"].copy()
        with self.assertRaisesRegex(ValueError, "was not observed"):
            audit_module.audit(PLAN, comparison["comparison_id"], pair)
        pair = records(comparison)
        pair[1]["case_id"] = STATUTORY_REVIEW["controlled_comparisons"][1]["case_ids"][0]
        with self.assertRaisesRegex(ValueError, "identities differ"):
            audit_module.audit(PLAN, comparison["comparison_id"], pair)


if __name__ == "__main__":
    unittest.main()
