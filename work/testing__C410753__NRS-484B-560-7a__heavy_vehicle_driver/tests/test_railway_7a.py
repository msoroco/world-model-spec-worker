"""Source-shaped CPU checks for the exact railroad crossing measurement contract."""
import copy
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "railway_7a.py"
spec = importlib.util.spec_from_file_location("railway_7a", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def site(case_name):
    axis, mode = module.CASE_AXES[case_name]
    case = {"name": case_name, "axis": axis, "mode": mode}
    if axis == "opposite_space":
        case.update(downstream_occupancy_source_ref="original:obstacle",
                    available_space_m=10.0,
                    opposite_side_boundary_ref="original:road edge")
    elif axis == "undercarriage":
        case.update(road_profile_source_ref="original:grade",
                    undercarriage_source_ref="original:vehicle belly",
                    minimum_clearance_m=0.12)
    else:
        case["target_trailing_end_ft"] = {"below": 14.9, "at": 15.0,
                                          "above": 15.1}[mode]
    return {"law_id": module.LAW, "cell_id": module.CELL, "actor": module.ACTOR,
            "layout": "paved_road", "maneuver": "cross_railway", "control": "rail_track",
            "source_sha256": "sitehash", "_packet_sha256": "packet-hash",
            "crossing_axis_unit": [1.0, 0.0, 0.0],
            "track": {"grade_crossing": True, "crossing_profile_ref": "original:profile",
                      "source_sha256": "trackhash",
                      "rails": [{"rail_id": "near", "point_m": [0., 0., 0.],
                                 "tangent_unit": [0., 1., 0.],
                                 "original_geometry_ref": "original:rail near"},
                                {"rail_id": "far", "point_m": [3., 0., 0.],
                                 "tangent_unit": [0., 1., 0.],
                                 "original_geometry_ref": "original:rail far"}]},
            "vehicle": {"driver_role": module.ACTOR, "blueprint_id": "source:truck",
                        "blueprint_source_ref": "original:blueprint",
                        "bounding_box_source_ref": "original:bbox",
                        "undercarriage_geometry_ref": "original:bottom",
                        "dimensions_m": [8., 2.5, 3.], "coupled_units": []},
            "route_clearance_source_ref": "original:route",
            "approach_visibility_source_ref": "original:view",
            "case": case}


def row(frame, rear_x, *, speed=1., gap=1., contact=False):
    body = [[rear_x + dx, y, z] for dx in (0., 8.) for y in (-1.25, 1.25)
            for z in (0., 3.)]
    return {"source_frame": frame, "time_s": frame * .05,
            "source_site_sha256": "packet-hash", "speed_mps": speed,
            "downstream_body_gap_m": gap, "undercarriage_contact": contact,
            "contact_source_ref": "original:contacts",
            "control_source_ref": "original:controls",
            "traffic_conflict_source_ref": "original:conflicts",
            "traffic_conflict": False, "brake_applied": False,
            "vehicle_units": [{"actor_id": "12", "blueprint_id": "source:truck",
                               "body_source_ref": "original:bbox",
                               "body_vertices_m": body}]}


class RailwayExactSourceTests(unittest.TestCase):
    def test_all_separate_constructions_require_source(self):
        for name in module.CASE_AXES:
            with self.subTest(name=name):
                module.validate_site(site(name), name)

    def test_missing_downstream_obstruction_source_rejected(self):
        p = site("space_halt_before_15ft")
        del p["case"]["downstream_occupancy_source_ref"]
        with self.assertRaisesRegex(ValueError, "opposite-side-space"):
            module.validate_site(p, "space_halt_before_15ft")

    def test_missing_undercarriage_geometry_rejected(self):
        p = site("clearance_grounded_before_15ft")
        del p["vehicle"]["undercarriage_geometry_ref"]
        with self.assertRaisesRegex(ValueError, "undercarriage_geometry_ref"):
            module.validate_site(p, "clearance_grounded_before_15ft")

    def test_wrong_rail_or_cell_rejected(self):
        p = site("space_clear_beyond_15ft")
        p["cell_id"] = "other"
        with self.assertRaisesRegex(ValueError, "identity"):
            module.validate_site(p, "space_clear_beyond_15ft")
        p = site("space_clear_beyond_15ft")
        p["track"]["rails"][1]["rail_id"] = "near"
        with self.assertRaisesRegex(ValueError, "repeated"):
            module.validate_site(p, "space_clear_beyond_15ft")

    def test_nearest_rail_and_fifteen_foot_measure(self):
        p = site("trailing_end_15_0ft")
        module.validate_site(p, "trailing_end_15_0ft")
        measured = module.measure_frames(p, [row(1, 3. + 15. * module.FOOT_M),
                                             row(2, 3. + 15.1 * module.FOOT_M)])
        self.assertAlmostEqual(measured["samples"][0]["trailing_end_past_nearest_rail_ft"], 15., places=8)
        self.assertEqual(measured["legal_judgment"], "unresolved")
        self.assertFalse(measured["halt_before_15ft_observed"])

    def test_cause_observation_separate_from_legal_verdict(self):
        p = site("clearance_grounded_before_15ft")
        module.validate_site(p, "clearance_grounded_before_15ft")
        measured = module.measure_frames(p, [row(1, 3. + 14.8 * module.FOOT_M,
                                                  speed=0., gap=0., contact=True)])
        self.assertTrue(measured["halt_before_15ft_observed"])
        self.assertTrue(measured["space_evidence"])
        self.assertTrue(measured["contact_evidence"])
        self.assertEqual(measured["causal_attribution"], "requires independent source review")

    def test_missing_original_contact_and_frame_join_rejected(self):
        p = site("space_halt_before_15ft")
        a, b = row(1, 1.), row(2, 1.)
        del b["contact_source_ref"]
        with self.assertRaisesRegex(ValueError, "contact evidence"):
            module.measure_frames(p, [a, b])
        b = row(3, 1.)
        with self.assertRaisesRegex(ValueError, "consecutive"):
            module.measure_frames(p, [a, b])

    def test_coupled_unit_requires_its_actual_body(self):
        p = site("space_halt_before_15ft")
        p["vehicle"]["coupled_units"] = [{"actor_id": "13",
                                           "dimensions_source_ref": "original:trailer",
                                           "coupling_source_ref": "original:hitch"}]
        module.validate_site(p, "space_halt_before_15ft")
        with self.assertRaisesRegex(ValueError, "coupled-unit samples"):
            module.measure_frames(p, [row(1, 1.)])


if __name__ == "__main__":
    unittest.main()
