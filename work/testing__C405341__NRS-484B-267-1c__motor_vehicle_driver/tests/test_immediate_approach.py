"""Source gating and actual Native adapter calls without CARLA."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from emergency_construction import CASES, execute, plan


def sources(case):
    road = {"source_kind": "native_map_readback", "road_type": "paved_road",
            "ego_route_connected": True, "unit_route_connected": True,
            "unit_route_approaches_ego": case.immediate,
            "unit_route_direction": case.direction,
            "ego_route_id": "ego-reviewed", "unit_route_id": "unit-reviewed",
            "conflict_location_source": "reviewed-map-pose"}
    actors = {"source_kind": "native_blueprint_readback", "unit_class": case.unit_class,
              "ego_blueprint_id": "vehicle.ego", "unit_blueprint_id": "vehicle.unit",
              "ego_vehicle_class": "ordinary_motor_vehicle",
              "ego_driver_control_source": "reviewed-driver-control"}
    authority = {"class": case.unit_class, "authorization_source": "reviewed-authorization",
                 "light_rule_source": "DEF-NRS-484A-480-3", "equipment_source": "reviewed-light",
                 "siren_equipment_source": "reviewed-siren", "siren_equipment_verified": True,
                 "front_red_lamp_source": "reviewed-front-pixel", "front_visible_red_lamp_verified": True,
                 "qualifying_flashing_equipment_verified": case.light_request != "unqualified_active",
                 "lights_can_flash": True, "officer_direction_source": "reviewed-officer"}
    return road, actors, authority


class Adapter:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def call(*args):
            self.calls.append((name, args))
            return name + "-object"
        return call


class ConstructionTest(unittest.TestCase):
    def test_nine_variants_execute_real_controller_calls(self):
        self.assertEqual(len(CASES), 9)
        for case in CASES:
            with self.subTest(case=case.suffix):
                adapter = Adapter()
                result = execute(adapter, case, *sources(case))
                names = [name for name, _ in adapter.calls]
                self.assertEqual(result["capture_frames"], 900)
                self.assertEqual(names.count("spawn_vehicle"), 2)
                self.assertEqual(names.count("configure_route"), 2)
                self.assertIn("configure_unit_movement", names)
                self.assertIn("configure_ego_response", names)
                self.assertEqual("configure_officer_direction" in names, case.officer_direction)
                control = next(args[1] for name, args in adapter.calls
                               if name == "configure_ego_response")
                self.assertEqual(control["stop_requested"], case.stopping)
                self.assertEqual(control["hold_until_unit_passes"],
                                 case.stopping and not case.early_departure)

    def test_legal_predicates_rejected_before_spawn(self):
        road, actors, authority = sources(CASES[0])
        adapter = Adapter()
        road["unit_route_approaches_ego"] = False
        with self.assertRaisesRegex(ValueError, "immediate approach"):
            execute(adapter, CASES[0], road, actors, authority)
        self.assertEqual(adapter.calls, [])
        road["unit_route_approaches_ego"] = True
        authority["siren_equipment_verified"] = False
        with self.assertRaisesRegex(ValueError, "siren"):
            execute(adapter, CASES[0], road, actors, authority)
        self.assertEqual(adapter.calls, [])

    def test_fallback_preserves_direction_and_immediacy(self):
        road, actors, authority = sources(CASES[0])
        road.update(alternate_unit_route_id="alternate-reviewed",
                    alternate_unit_route_connected=True,
                    alternate_unit_route_direction="same_direction",
                    alternate_unit_route_approaches_ego=True)
        with self.assertRaisesRegex(ValueError, "alternate direction"):
            execute(Adapter(), CASES[0], road, actors, authority, {"alternate_unit_route": True})
        road["alternate_unit_route_direction"] = "opposing"
        self.assertEqual(execute(Adapter(), CASES[0], road, actors, authority,
                                 {"alternate_unit_route": True})["capture_frames"], 900)


if __name__ == "__main__":
    unittest.main()
