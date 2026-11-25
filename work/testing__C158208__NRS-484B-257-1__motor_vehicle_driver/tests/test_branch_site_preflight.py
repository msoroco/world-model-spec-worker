"""Check reviewed branch findings before any production selection."""

from pathlib import Path
import sys
import unittest


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from branch_site_preflight import (COMMON, REFERENCE_FINDINGS,
                                   SURVEY_FOR_FINDING, validate_site_branch)
from build_semantic_proposals import KINDS, case_settings


class BranchSitePreflightTests(unittest.TestCase):
    def site_for(self, kind):
        reference = next((key for key in REFERENCE_FINDINGS if kind.startswith(key)),
                         "nearest_view")
        findings = COMMON + REFERENCE_FINDINGS[reference]
        cited = {name: SURVEY_FOR_FINDING[name] for name in findings}
        cited["planned_through_traffic_phase"] = "through_highway_survey"
        settings = case_settings(kind)
        return {"reviewed_context": {name: True for name in findings},
                "finding_sources": cited,
                "source_bindings": {name: {"sha256": "source-bound-in-caller"}
                                    for name in set(cited.values())},
                "planned_response_mode": settings["response_mode"],
                "planned_through_traffic_phase": settings["through_traffic_phase"],
                "native_scene": {"through_vehicle": {"motion_plan": {
                    "target_speed_mps": 4.0, "start_delay_s": 0.0,
                    "steering_mode": "follow_reviewed_route_axis"}}}}

    def test_every_exact_case_requires_its_own_reference_and_phase(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                site = self.site_for(kind)
                result = validate_site_branch(site, HERE.name + "__" + kind)
                self.assertEqual(result["planned_response_mode"],
                                 case_settings(kind)["response_mode"])
                site["planned_through_traffic_phase"] = "unsupported_phase"
                with self.assertRaisesRegex(ValueError, "plan differs"):
                    validate_site_branch(site, HERE.name + "__" + kind)

    def test_marking_presence_and_survey_are_not_inferred_from_absence(self):
        kind = "marked_stop_line_response"
        site = self.site_for(kind)
        site["reviewed_context"].pop("marked_stop_line_present")
        with self.assertRaisesRegex(ValueError, "marked_stop_line_present"):
            validate_site_branch(site, HERE.name + "__" + kind)
        site = self.site_for(kind)
        site["finding_sources"]["marked_stop_line_present"] = "crosswalk_survey"
        with self.assertRaisesRegex(ValueError, "matching original survey"):
            validate_site_branch(site, HERE.name + "__" + kind)
        site = self.site_for("nearest_view_response")
        site["reviewed_context"]["marked_stop_line_present"] = True
        with self.assertRaisesRegex(ValueError, "contradictory"):
            validate_site_branch(site, HERE.name + "__nearest_view_response")
        site = self.site_for("nearest_view_response")
        site["native_scene"]["through_vehicle"].pop("motion_plan")
        with self.assertRaisesRegex(ValueError, "motion plan required"):
            validate_site_branch(site, HERE.name + "__nearest_view_response")


if __name__ == "__main__":
    unittest.main()
