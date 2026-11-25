"""Check that canonical case proposals preserve the complete frozen inventory."""

import importlib.util
import json
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "c158208_semantic_builder", HERE / "build_semantic_proposals.py")
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


class FullSemanticCaseInventoryTests(unittest.TestCase):
    def test_all_accepted_cases_have_distinct_source_plans(self):
        assignment = json.loads((HERE.parents[1] / "inputs" / HERE.name / "assignment.json").read_text())
        expected = {row["case_id"] for row in assignment["local_snapshot"]["memberships"]["demo-test"]}
        self.assertEqual({HERE.name + "__" + kind for kind in BUILDER.KINDS}, expected)
        plans = {kind: BUILDER.case_settings(kind) for kind in BUILDER.KINDS}
        self.assertEqual(plans["nearest_view_response"]["stopping_reference"],
                         plans["nearest_view_uninterrupted"]["stopping_reference"])
        self.assertNotEqual(plans["nearest_view_response"]["response_mode"],
                            plans["nearest_view_uninterrupted"]["response_mode"])
        self.assertNotEqual(plans["nearest_view_response"]["stopping_reference"],
                            plans["marked_stop_line_response"]["stopping_reference"])
        self.assertNotEqual(plans["approaching_phase_probe"]["through_traffic_phase"],
                            plans["later_history_probe"]["through_traffic_phase"])

    def test_unknown_case_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown statutory case"):
            BUILDER.case_settings("invented_case")


if __name__ == "__main__":
    unittest.main()
