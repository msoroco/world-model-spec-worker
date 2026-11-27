"""Focused original-frame body-order and source-gate tests."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis import measure_case
from emergency_construction import CASES, plan, execute


class BodyOrderTest(unittest.TestCase):
    def load(self, case):
        root = ROOT / "diagnostics" / case.suffix
        site = json.loads((root / "emergency-site.json").read_text())
        frames = [json.loads(row) for row in
                  (root / "original-emergency-movement-history.jsonl").read_text().splitlines()]
        return site, frames

    def test_exact_maneuver_sequence(self):
        outcomes = {}
        for case in CASES:
            site, frames = self.load(case)
            outcomes[case.suffix] = measure_case(case, site, frames)
        self.assertFalse(outcomes["moving_hold_behind"]["abreast_observed"])
        self.assertTrue(outcomes["moving_overtake"]["ego_overtook"])
        self.assertTrue(outcomes["moving_abreast"]["abreast_observed"])
        self.assertFalse(outcomes["moving_abreast"]["ego_overtook"])
        self.assertTrue(outcomes["unit_overtakes_ego"]["unit_overtook"])
        self.assertFalse(outcomes["no_approach"]["subject_approach_observed"])

    def test_pose_and_extent_tampering_rejected(self):
        case = CASES[1]
        site, frames = self.load(case)
        frames[520]["ego_body_polygon_xy"] = [[0, 0]] * 4
        with self.assertRaisesRegex(ValueError, "body polygons"):
            measure_case(case, site, frames)

    def test_missing_visible_preparation_rejected(self):
        case = next(item for item in CASES if item.suffix == "preparing_visible_hand_signal")
        site, frames = self.load(case)
        for frame in frames:
            frame["visible_hand_signal"] = False
        with self.assertRaisesRegex(ValueError, "visible hand signal"):
            measure_case(case, site, frames)

    def test_vehicle_movement_is_distinct_preparation_cue(self):
        case = next(item for item in CASES if item.suffix == "preparing_visible_vehicle_movement")
        site, frames = self.load(case)
        measured = measure_case(case, site, frames)
        self.assertTrue(measured["visible_preparation_movement_original_frames"])
        self.assertFalse(measured["visible_hand_signal_original_frames"])
        for frame in frames:
            frame["preparation_movement_visible"] = False
        with self.assertRaisesRegex(ValueError, "visible preparation movement"):
            measure_case(case, site, frames)

    def test_inactive_lights_contrast_rejects_flashing(self):
        case = next(item for item in CASES if item.suffix == "lights_inactive")
        site, frames = self.load(case)
        frames[0]["flashing_light_on"] = True
        with self.assertRaisesRegex(ValueError, "inactive light contrast"):
            measure_case(case, site, frames)

    def test_rotated_adjacent_lanes_and_opposite_side(self):
        for case in (CASES[0], CASES[1]):
            site, frames = self.load(case)
            for frame in frames:
                for key in ("ego_xy", "emergency_xy"):
                    x, y = frame[key]
                    frame[key] = [-y, x]
                for key in ("ego_body_polygon_xy", "emergency_body_polygon_xy"):
                    frame[key] = [[-y, x] for x, y in frame[key]]
                frame["ego_route_tangent_xy"] = [0.0, 1.0]
                frame["unit_route_tangent_xy"] = [0.0, 1.0]
            measured = measure_case(case, site, frames)
            self.assertEqual(measured["ego_overtook"], case.suffix == "moving_overtake")

    def test_route_and_qualification_required(self):
        case = CASES[0]
        m = {
            "source_kind": "native_map_readback", "road_type": "paved_road",
            "ego_route_connected": True, "unit_route_connected": True,
            "same_direction": True, "adjacent_traversable_lanes": True,
            "ego_approaches_unit": True, "unit_state": "moving",
            "ego_route_id": "ego", "unit_route_id": "unit",
            "lane_geometry_source": "map", "passing_clearance_source": "width"}
        a = {"source_kind": "native_blueprint_readback", "ego_blueprint_id": "ego",
             "unit_blueprint_id": "unit", "ego_body_extent_source": "box",
             "unit_body_extent_source": "box", "ego_vehicle_class": "ordinary_motor_vehicle",
             "ego_driver_control_source": "driver", "unit_class": "authorized_emergency"}
        q = {"class": "authorized_emergency", "authorization_source": "record",
             "light_rule_source": "DEF-NRS-484A-480-3", "equipment_source": "record",
             "qualifying_flashing_equipment_verified": True, "lights_can_flash": True}
        plan(case, m, a, q)
        m["same_direction"] = False
        with self.assertRaisesRegex(ValueError, "same-direction"):
            plan(case, m, a, q)
        m["same_direction"] = True
        q["qualifying_flashing_equipment_verified"] = False
        with self.assertRaisesRegex(ValueError, "qualification"):
            plan(case, m, a, q)

    def test_reviewed_alternate_route_controls_native_calls(self):
        case = CASES[1]
        m = {
            "source_kind": "native_map_readback", "road_type": "paved_road",
            "ego_route_connected": True, "unit_route_connected": True,
            "same_direction": True, "adjacent_traversable_lanes": True,
            "ego_approaches_unit": True, "unit_state": "moving",
            "ego_route_id": "ego-lane", "unit_route_id": "unit-lane",
            "lane_geometry_source": "map", "passing_clearance_source": "width",
            "alternate_unit_route_connected": True, "alternate_unit_route_id": "unit-lane-alt",
            "alternate_same_direction": True, "alternate_ego_approaches_unit": True}
        a = {"source_kind": "native_blueprint_readback", "ego_blueprint_id": "ego",
             "unit_blueprint_id": "unit", "ego_body_extent_source": "box",
             "unit_body_extent_source": "box", "ego_vehicle_class": "ordinary_motor_vehicle",
             "ego_driver_control_source": "driver", "unit_class": "authorized_emergency"}
        q = {"class": "authorized_emergency", "authorization_source": "record",
             "light_rule_source": "DEF-NRS-484A-480-3", "equipment_source": "record",
             "qualifying_flashing_equipment_verified": True, "lights_can_flash": True}

        class Adapter:
            def __init__(self):
                self.calls = []

            def spawn_vehicle(self, spec):
                self.calls.append(("spawn", spec["identity"]))
                return spec["identity"]

            def configure_route(self, actor, route):
                self.calls.append(("route", actor, route))

            def configure_flashing_lights(self, actor, spec):
                self.calls.append(("lights", actor, spec["active"]))

            def configure_unit_movement(self, actor, spec):
                self.calls.append(("movement", actor, spec["target_mps"]))

            def configure_ego_response(self, actor, spec):
                self.calls.append(("passing", actor, spec["passing_maneuver"]))

        adapter = Adapter()
        execute(adapter, case, m, a, q, {"alternate_unit_route": True})
        self.assertIn(("route", "unit", "unit-lane-alt"), adapter.calls)
        self.assertIn(("passing", "ego", "overtake"), adapter.calls)
        m["alternate_same_direction"] = False
        with self.assertRaisesRegex(ValueError, "alternate direction"):
            execute(Adapter(), case, m, a, q, {"alternate_unit_route": True})

    def test_vehicle_movement_cue_reaches_native_adapter(self):
        case = next(item for item in CASES if item.suffix == "preparing_visible_vehicle_movement")
        m = {"source_kind": "native_map_readback", "road_type": "paved_road",
             "ego_route_connected": True, "unit_route_connected": True,
             "same_direction": True, "adjacent_traversable_lanes": True,
             "ego_approaches_unit": True, "unit_state": "preparing",
             "visible_preparation_source": "reviewed-driver-view-cue",
             "ego_route_id": "ego-lane", "unit_route_id": "unit-lane",
             "lane_geometry_source": "map", "passing_clearance_source": "width"}
        a = {"source_kind": "native_blueprint_readback", "ego_blueprint_id": "ego",
             "unit_blueprint_id": "unit", "ego_body_extent_source": "box",
             "unit_body_extent_source": "box", "ego_vehicle_class": "ordinary_motor_vehicle",
             "ego_driver_control_source": "driver", "unit_class": "authorized_emergency"}
        q = {"class": "authorized_emergency", "authorization_source": "record",
             "light_rule_source": "DEF-NRS-484A-480-3", "equipment_source": "record",
             "qualifying_flashing_equipment_verified": True, "lights_can_flash": True}
        adapter = Mock()
        adapter.spawn_vehicle.side_effect = ["ego", "unit"]
        execute(adapter, case, m, a, q)
        cue = adapter.configure_visible_preparation.call_args.args[1]
        self.assertEqual(cue["cue"], "vehicle_movement")
        self.assertEqual(cue["reviewed_source"], "reviewed-driver-view-cue")


if __name__ == "__main__":
    unittest.main()
