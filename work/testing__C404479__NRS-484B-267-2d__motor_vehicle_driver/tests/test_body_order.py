"""Focused original-frame body-order and source-gate tests."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis import measure_case
from emergency_construction import CASES, plan


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


if __name__ == "__main__":
    unittest.main()
