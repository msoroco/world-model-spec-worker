"""Focused source and statutory boundary geometry tests."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from curb_geometry import ASSIGNMENT, INCH_M, SOURCES, load_site, measure_right_wheels
from curb_construction import TARGETS, build_plan


class CurbGeometryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = ASSIGNMENT + "__park_18in_parallel"
        sources = {}
        for name in SOURCES:
            path = self.root / (name + ".source")
            path.write_text("reviewed synthetic source for " + name + "\n")
            sources[name] = {"path": path.name,
                             "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        self.site = {"format": "worker-right-curb-site-v1", "case_id": self.case,
                     "sources": sources,
                     "reviewed_assertions": {
                         "public_highway": True, "residence_district": True,
                         "adjacent_right_curb": True, "ordinary_motor_vehicle": True,
                         "right_side_default_branch": True,
                         "left_curb_ordinance_applies": False,
                         "angle_parking_ordinance_applies": False},
                     "right_curb_xy_m": [[-10, 0], [10, 0]],
                     "parking_route_xy_m": [[-8, 1], [8, 1]],
                     "roadway_side_of_curb": "left",
                     "reviewed_right_wheel_axle_spacing_m": 2.7,
                     "reviewed_curb_station_m": 8}
        self.packet = self.root / "site.json"
        self.save()

    def save(self):
        self.packet.write_text(json.dumps(self.site) + "\n")

    def test_source_checked_default_branch(self):
        self.assertEqual(load_site(self.packet, self.case)["right_curb_xy_m"], [[-10, 0], [10, 0]])

    def test_missing_and_changed_source_rejected(self):
        source = self.root / "curb_survey.source"
        source.unlink()
        with self.assertRaisesRegex(ValueError, "source hash differs"):
            load_site(self.packet, self.case)
        source.write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "source hash differs"):
            load_site(self.packet, self.case)

    def test_ordinance_exception_cannot_be_assumed_absent(self):
        self.site["reviewed_assertions"]["left_curb_ordinance_applies"] = None
        self.save()
        with self.assertRaisesRegex(ValueError, "exception applicability"):
            load_site(self.packet, self.case)

    def test_statutory_boundary_is_measured_in_inch_units(self):
        for inches in (17, 18, 19):
            y = inches * INCH_M
            measured = measure_right_wheels([2, y], [-2, y], self.site["right_curb_xy_m"])
            self.assertAlmostEqual(measured["max_right_wheel_distance_inches"], inches)
            self.assertAlmostEqual(measured["wheel_curb_alignment_deg"], 0)
            self.assertEqual(measured["statutory_distance_inch"], 18)

    def test_skew_is_measured_from_original_wheel_axis(self):
        measured = measure_right_wheels([2, 17 * INCH_M + .2], [-2, 17 * INCH_M],
                                        self.site["right_curb_xy_m"])
        self.assertGreater(measured["wheel_curb_alignment_deg"], 2)

    def test_degenerate_curb_rejected(self):
        with self.assertRaisesRegex(ValueError, "degenerate"):
            measure_right_wheels([2, .4], [-2, .4], [[0, 0], [0, 0]])

    def test_each_original_pose_request_and_bounded_fallback(self):
        for variant, (activity, inches, angle) in TARGETS.items():
            case = ASSIGNMENT + "__" + variant
            self.site["case_id"] = case
            self.save()
            for fallback in (False, True):
                plan = build_plan(self.packet, case, fallback=fallback)
                self.assertEqual(plan["activity_request"], activity)
                self.assertEqual(plan["capture"]["frame_count"], 900)
                measured = measure_right_wheels(plan["requested_right_front_wheel_xy_m"],
                                                plan["requested_right_rear_wheel_xy_m"],
                                                self.site["right_curb_xy_m"])
                self.assertAlmostEqual(measured["max_right_wheel_distance_inches"], inches, places=4)
                self.assertAlmostEqual(measured["wheel_curb_alignment_deg"], angle, places=4)
                self.assertEqual(plan["physical_completion"], "pending_original_native_readback")

    def test_construction_rejects_unreviewed_roadway_side_and_short_curb(self):
        self.site.pop("roadway_side_of_curb")
        self.save()
        with self.assertRaisesRegex(ValueError, "roadway side"):
            build_plan(self.packet, self.case)
        self.site["roadway_side_of_curb"] = "left"
        self.site["right_curb_xy_m"] = [[0, 0], [2, 0]]
        self.save()
        with self.assertRaisesRegex(ValueError, "too short"):
            build_plan(self.packet, self.case)


if __name__ == "__main__":
    unittest.main()
