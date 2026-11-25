"""Exercise case-neutral saved measurements from source-shaped tick packets."""

from pathlib import Path
import sys
import unittest


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from source_tick_capture import derive
from statutory_branch_measurement import measure_branch
from test_branch_site_preflight import BranchSitePreflightTests
from test_source_tick_capture import CONTEXT, GEOMETRY, raw


class StatutoryBranchMeasurementTests(unittest.TestCase):
    def packet(self, site):
        rows = [derive(raw(index), GEOMETRY) for index in range(3)]
        for row in rows:
            row.pop("original")
        rows[1]["ego_front_station_m"] = 0.0
        rows[2]["ego_front_station_m"] = 12.0
        rows[2]["intersection_entry"] = True
        return {"reviewed_context": site["reviewed_context"],
                "geometry": GEOMETRY, "samples": rows}

    def site(self, kind):
        site = BranchSitePreflightTests().site_for(kind)
        site["stopping_reference_station_m"] = 0.0
        return site

    def test_all_case_plans_measure_without_legal_cutoff(self):
        for kind in ("nearest_view_response", "marked_stop_line_response",
                     "near_side_marked_crosswalk_response",
                     "near_side_sidewalk_derived_crosswalk_response",
                     "approaching_phase_probe", "later_history_probe"):
            with self.subTest(kind=kind):
                site = self.site(kind)
                measured = measure_branch(self.packet(site), site,
                                          HERE.name + "__" + kind)
                self.assertEqual(measured["legal_status"], "unresolved")
                self.assertEqual(len(measured["observed_history"]), 3)
                self.assertIsInstance(measured["minimum_approach_speed_mps"], float)

    def test_rejects_unsourced_reference_or_changed_context(self):
        site = self.site("nearest_view_response")
        packet = self.packet(site)
        site.pop("stopping_reference_station_m")
        with self.assertRaisesRegex(ValueError, "reviewed stopping reference"):
            measure_branch(packet, site, HERE.name + "__nearest_view_response")
        site = self.site("nearest_view_response")
        packet["reviewed_context"] = dict(CONTEXT, no_marked_stop_line=False)
        with self.assertRaisesRegex(ValueError, "tick context differs"):
            measure_branch(packet, site, HERE.name + "__nearest_view_response")


if __name__ == "__main__":
    unittest.main()
