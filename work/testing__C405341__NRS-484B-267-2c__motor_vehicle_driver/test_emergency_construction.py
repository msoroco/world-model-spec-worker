"""Native operation and geometry tests without CARLA."""

import unittest

from emergency_construction import CASES, execute, plan


def sources(case):
    road = {"source_kind": "native_map_readback", "road_type": "paved_road",
            "ego_route_connected": True, "unit_route_connected": True,
            "unit_route_intersects_ego_view": True,
            "ego_route_id": "road-1", "unit_route_id": "road-2"}
    if not case.visible:
        road["occluder"] = {"source_kind": "native_geometry_readback", "blocks_driver_view": True,
                            "spares_ego_route": True, "x_m": 8.0, "y_m": 2.0,
                            "length_m": 5.0, "width_m": 2.0, "height_m": 2.4}
    actors = {"source_kind": "native_blueprint_readback", "unit_class": case.unit_class,
              "ego_blueprint_id": "vehicle.ego", "unit_blueprint_id": "vehicle.unit",
              "driver_hand_signal_capability": True}
    authority = {"class": case.unit_class, "authorization_source": "sealed-authority",
                 "light_rule_source": "DEF-NRS-484A-480-3", "equipment_source": "sealed-equipment",
                 "qualifying_flashing_equipment_verified": True, "lights_can_flash": True,
                 "officer_direction_source": "sealed-officer"}
    return road, actors, authority


class Adapter:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def call(*arguments):
            self.calls.append((name, arguments))
            return name + "-object"
        return call


class ConstructionTests(unittest.TestCase):
    def test_all_six_execute_source_gated_operations(self):
        for case in CASES:
            with self.subTest(case=case.suffix):
                road, actors, authority = sources(case)
                adapter = Adapter()
                result = execute(adapter, case, road, actors, authority)
                names = [entry[0] for entry in adapter.calls]
                self.assertEqual(result["capture_frames"], 900)
                self.assertEqual(names.count("spawn_vehicle"), 2)
                self.assertEqual(names.count("configure_route"), 2)
                self.assertIn("configure_unit_movement", names)
                self.assertIn("configure_flashing_lights", names)
                self.assertEqual("spawn_occluder" in names, not case.visible)
                self.assertEqual("configure_driver_hand_signal" in names, case.cue == "hand_signal")
                self.assertEqual("configure_officer_direction" in names, case.officer_direction)

    def test_no_actor_call_when_authority_missing(self):
        case = CASES[0]
        road, actors, authority = sources(case)
        authority["qualifying_flashing_equipment_verified"] = False
        adapter = Adapter()
        with self.assertRaisesRegex(ValueError, "qualifying flashing equipment"):
            execute(adapter, case, road, actors, authority)
        self.assertEqual(adapter.calls, [])

    def test_occlusion_requires_physical_geometry(self):
        case = CASES[2]
        road, actors, authority = sources(case)
        road["occluder"]["height_m"] = 0.2
        with self.assertRaisesRegex(ValueError, "occluder cannot block"):
            plan(case, road, actors, authority)

    def test_officer_and_hand_signal_are_distinct(self):
        officer, hand = CASES[3], CASES[5]
        self.assertTrue(officer.officer_direction)
        self.assertFalse(hand.officer_direction)
        self.assertEqual(hand.cue, "hand_signal")
        self.assertEqual(officer.cue, "movement")


if __name__ == "__main__":
    unittest.main()
