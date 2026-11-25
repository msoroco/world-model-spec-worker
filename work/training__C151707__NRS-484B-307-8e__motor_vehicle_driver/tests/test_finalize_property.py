"""In-memory saved Native normalization and missing-source rejection."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from finalize_property import normalize
from property_bypass_measure import ASSIGNMENT


def enc(value):
    return json.dumps(value, sort_keys=True).encode()


def sources(via_property=True):
    survey = {"source_kind": "original_native_property_survey", "assignment_id": ASSIGNMENT,
              "approach_signal_lens_form": "circular_red_alone",
              "approach_signal_facing_source_id": "surveyed-facing-approach",
              "approach_signal_actor_id": 12, "cross_signal_actor_id": 13,
              "approach_lane_source": "surveyed-approach", "cross_street_lane_source": "surveyed-cross",
              "property_id": "surveyed-parcel", "property_boundary_source_id": "surveyed-boundary",
              "property_polygon_xy_m": [[9, -2], [11, -2], [11, 2], [9, 2]],
              "cross_street_polygon_xy_m": [[19, -2], [21, -2], [21, 2], [19, 2]]}
    purpose = {"source_kind": "original_controller_purpose_declaration",
               "assignment_id": ASSIGNMENT, "declaration_source_id": "controller-plan-1",
               "declared_purpose": "avoid_red_signal"}
    rows = []
    for i in range(600):
        zone = "approach_road"
        if via_property and 200 <= i < 260:
            zone = "property"
        elif via_property and i >= 260:
            zone = "intersecting_street"
        x = 0 if zone == "approach_road" else 10 if zone == "property" else 20
        rows.append({"source_kind": "original_native_observation", "frame": i,
                     "t_s": i / 20, "vehicle_id": 1, "zone": zone,
                     "x_m": x, "y_m": 0,
                     "body_vertices_xy_m": [[x - 0.4, -0.4], [x + 0.4, -0.4],
                                            [x + 0.4, 0.4], [x - 0.4, 0.4]],
                     "approach_signal_actor_id": 12, "cross_signal_actor_id": 13,
                     "approach_signal_native_state": "Red",
                     "cross_signal_native_state": "Green"})
    return rows, survey, purpose


def run(rows, survey, purpose):
    return normalize(("\n".join(json.dumps(row) for row in rows) + "\n").encode(),
                     enc(survey), enc(purpose))


class SavedNormalizationTest(unittest.TestCase):
    def test_property_and_road_only(self):
        rows, survey, purpose = sources(True)
        property_result = run(rows, survey, purpose)
        self.assertTrue(property_result["property_then_intersecting_street"])
        self.assertEqual(property_result["first_property_frame"], 200)
        self.assertEqual(property_result["first_intersecting_street_frame"], 260)
        self.assertEqual(property_result["source_path_length_m"], 20)
        rows, survey, purpose = sources(False)
        road_result = run(rows, survey, purpose)
        self.assertFalse(road_result["property_then_intersecting_street"])

    def test_missing_facing_source_rejected(self):
        rows, survey, purpose = sources()
        survey["approach_signal_facing_source_id"] = ""
        with self.assertRaisesRegex(ValueError, "facing survey"):
            run(rows, survey, purpose)

    def test_mismatched_signal_actor_rejected(self):
        rows, survey, purpose = sources()
        rows[250]["approach_signal_actor_id"] = 99
        with self.assertRaisesRegex(ValueError, "signal identity"):
            run(rows, survey, purpose)

    def test_missing_purpose_source_rejected(self):
        rows, survey, purpose = sources()
        purpose["declaration_source_id"] = ""
        with self.assertRaisesRegex(ValueError, "purpose declaration"):
            run(rows, survey, purpose)

    def test_unobserved_body_footprint_rejected(self):
        rows, survey, purpose = sources()
        rows[250].pop("body_vertices_xy_m")
        with self.assertRaisesRegex(ValueError, "body footprint missing"):
            run(rows, survey, purpose)

    def test_synthetic_trace_rejected(self):
        rows, survey, purpose = sources()
        rows[100]["source_kind"] = "synthetic_native_sample"
        with self.assertRaisesRegex(ValueError, "original Native trace"):
            run(rows, survey, purpose)

    def test_explicit_diagnostic_provenance(self):
        rows, survey, purpose = sources()
        for row in rows:
            row["source_kind"] = "synthetic_native_fixture"
        survey["source_kind"] = "synthetic_native_property_survey"
        purpose["source_kind"] = "synthetic_controller_purpose_declaration"
        measured = run(rows, survey, purpose)
        self.assertEqual(measured["source_kind"], "synthetic_native_sample")

    def test_authored_zone_cannot_replace_body_geometry(self):
        rows, survey, purpose = sources()
        for row in rows:
            row["zone"] = "approach_road"
        measured = run(rows, survey, purpose)
        self.assertTrue(measured["property_then_intersecting_street"])

    def test_red_must_precede_property_entry(self):
        rows, survey, purpose = sources()
        rows[199]["approach_signal_native_state"] = "Green"
        measured = run(rows, survey, purpose)
        self.assertFalse(measured["steady_red_alone_before_property_entry"])

    def test_short_trace_rejected(self):
        rows, survey, purpose = sources()
        with self.assertRaisesRegex(ValueError, "shorter than 30 seconds"):
            run(rows[:-1], survey, purpose)


if __name__ == "__main__":
    unittest.main()
