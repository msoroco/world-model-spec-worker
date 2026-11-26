import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from qualitative_sweeps import AXES, build, review


class QualitativeSweepsTest(unittest.TestCase):
    def test_plan_binds_selected_exact_cases_and_source(self):
        plan = build()
        self.assertEqual(plan, json.loads((HERE / "qualitative-sweep-plan.json").read_text()))
        self.assertEqual([row["axis_id"] for row in plan["axes"]], list(AXES))
        self.assertTrue(all(len(row["construction_sha256"]) == 2 for row in plan["axes"]))
        self.assertFalse(plan["physical_acceptance"])

    def test_review_rejects_stale_plan_and_incomplete_original_paths(self):
        plan = build()
        with self.assertRaisesRegex(ValueError, "stale or incomplete"):
            review({**plan, "manifest_sha256": "0" * 64}, {})
        with self.assertRaisesRegex(ValueError, "both original attempts"):
            review(plan, {key: {} for key in AXES})

    def test_review_calls_original_mode_and_rejects_changed_receipt(self):
        plan = build()
        keys = ("left_attempt", "right_attempt", "left_processed", "right_processed",
                "authority_root", "left_site", "right_site", "left_review", "right_review")
        paths = {axis: {key: Path("/original/" + axis + "/" + key) for key in keys}
                 for axis in AXES}
        def good(comparison, *args, **kwargs):
            self.assertIs(kwargs["diagnostic"], False)
            axis = next(row for row in plan["axes"] if row["comparison_id"] == comparison)
            return {"comparison_id": comparison, "case_ids": axis["case_ids"],
                    "diagnostic_fixture": False, "physical_acceptance": False,
                    "legal_verdict": None}
        with patch("qualitative_sweeps.audit_comparison", side_effect=good) as audit:
            receipt = review(plan, paths)
        self.assertEqual(audit.call_count, 2)
        self.assertEqual(len(receipt["comparisons"]), 2)
        with patch("qualitative_sweeps.audit_comparison", return_value={"diagnostic_fixture": True}):
            with self.assertRaisesRegex(ValueError, "receipt differs"):
                review(plan, paths)


if __name__ == "__main__":
    unittest.main()
