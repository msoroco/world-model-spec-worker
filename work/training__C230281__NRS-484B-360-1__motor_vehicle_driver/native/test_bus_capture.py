"""Source and exact-scope checks for the prospective Native bus capture."""
import unittest

from bus_capture import AID, SPEEDS, capture_plan, preflight, validate_survey


class BusCapturePlanTest(unittest.TestCase):
    def survey(self):
        return {"source_kind": "original_native_school_bus_route_survey",
                "assignment_id": AID, "cell_id": "C230281", "layout": "road",
                "maneuver": "travel", "control": "school_bus", "map_name": "SurveyedMap",
                "bus_blueprint": "source.reviewed.school_bus",
                "bus_design_source": "original design review id",
                "route_source": "original road survey id", "clear_road_length_m": 950,
                "spawn_xyz_yaw_deg": [0, 0, 0.5, 0]}

    def test_exact_cases_and_camera_duration(self):
        self.assertEqual(SPEEDS, (53, 55, 57))
        for speed in SPEEDS:
            plan = capture_plan(speed)
            self.assertEqual(plan["case_id"], f"{AID}__{speed}")
            self.assertEqual(plan["camera_names"], ["overview", "approach", "reference_corner", "driver_reference"])
            self.assertEqual((plan["frames"], plan["rate_hz"]), (600, 20))
            self.assertFalse(plan["physical_acceptance_claimed"])
        self.assertFalse(preflight()["simulation_started"])

    def test_rejects_unreviewed_or_wrong_survey(self):
        self.assertEqual(validate_survey(self.survey())["cell_id"], "C230281")
        for field, bad in (("assignment_id", "another assignment"),
                           ("control", "speed_limit"),
                           ("source_kind", "synthetic_diagnostic"),
                           ("bus_design_source", ""),
                           ("route_source", ""),
                           ("clear_road_length_m", 500),
                           ("spawn_xyz_yaw_deg", [0, 0, 0])):
            with self.subTest(field=field):
                survey = self.survey()
                survey[field] = bad
                with self.assertRaises(ValueError):
                    validate_survey(survey)

    def test_rejects_out_of_scope_speed(self):
        with self.assertRaises(ValueError):
            capture_plan(58)


if __name__ == "__main__":
    unittest.main()
