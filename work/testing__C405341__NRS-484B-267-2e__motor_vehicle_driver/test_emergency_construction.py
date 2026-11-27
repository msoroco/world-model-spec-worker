"""Native lane setup tests without CARLA."""
import unittest
from emergency_construction import CASES, execute, plan


def sources(case):
    road = {"source_kind": "native_map_readback", "road_type": "paved_road",
            "ego_route_connected": True, "unit_route_connected": True,
            "ego_route_id": "ego-adjacent-route", "unit_route_id": "unit-route",
            "unit_lane_id": "lane-0", "adjacent_lane_id": "lane-1",
            "lane_adjacency_source": "sealed-lane-graph",
            "unit_lane_adjacent_to_ego_start": True,
            "nonadjacent_lane_id": "lane-2", "nonadjacent_route_id": "ego-nonadjacent-route",
            "nonadjacent_route_connected": case.condition != "roadway_impossible",
            "nonadjacent_lane_adjacent_to_unit": False,
            "nonadjacent_route_absence_source": "sealed-lane-graph",
            "movement_cue_visible_from_ego": True}
    actors = {"source_kind": "native_blueprint_readback", "unit_class": case.unit_class,
              "ego_vehicle_class": "ordinary_motor_vehicle",
              "ego_blueprint_id": "vehicle.ego", "unit_blueprint_id": "vehicle.unit",
              "ego_driver_control_source": "sealed-original-controls",
              "driver_hand_signal_capability": True,
              "driver_hand_signal_source": "sealed-driver-cue"}
    authority = {"class": case.unit_class, "authorization_source": "sealed-authority",
                 "light_rule_source": "DEF-NRS-484A-480-3", "equipment_source": "sealed-equipment",
                 "qualifying_flashing_equipment_verified": True, "lights_can_flash": True,
                 "officer_direction_source": "sealed-officer",
                 "law_enforcement_officer_verified": True}
    context = {"source_kind": "reviewed_native_condition_context",
               "traffic_occupies_nonadjacent_path": case.condition == "traffic_unsafe",
               "traffic_trajectory_source": "sealed-traffic-trajectory",
               "weather_adverse": case.condition == "weather_unsafe",
               "weather_readback_source": "sealed-weather", "road_surface_source": "sealed-surface",
               "visibility_source": "sealed-visibility"}
    context.update({"other_hazard_kind": "fallen_cargo" if case.condition == "other_hazard" else None,
                    "other_hazard_occupies_nonadjacent_path": case.condition == "other_hazard",
                    "other_hazard_geometry_source": "sealed-original-cargo-geometry"})
    return road, actors, authority, context


class Adapter:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def call(*arguments):
            self.calls.append((name, arguments))
            return name + "-object"
        return call


class ConstructionTests(unittest.TestCase):
    def test_all_twelve_execute_source_gated_operations(self):
        for case in CASES:
            with self.subTest(case=case.suffix):
                road, actors, authority, context = sources(case)
                adapter = Adapter()
                result = execute(adapter, case, road, actors, authority, context)
                names = [entry[0] for entry in adapter.calls]
                self.assertEqual(result["capture_frames"], 900)
                self.assertEqual(names.count("spawn_vehicle"), 2)
                self.assertEqual(names.count("configure_route"), 2)
                self.assertIn("configure_unit_movement", names)
                self.assertIn("configure_flashing_lights", names)
                self.assertIn("configure_ego_lane_route", names)
                self.assertEqual("configure_source_bound_traffic" in names,
                                 case.condition == "traffic_unsafe")
                self.assertEqual("configure_source_bound_weather" in names,
                                 case.condition == "weather_unsafe")
                self.assertEqual("configure_source_bound_hazard" in names,
                                 case.condition == "other_hazard")
                self.assertEqual("configure_hand_signal" in names,
                                 case.motion_state == "preparing_hand_signal")
                self.assertEqual("configure_officer_direction" in names, case.officer_direction)

    def test_no_actor_call_when_authority_missing(self):
        case = CASES[0]
        road, actors, authority, context = sources(case)
        authority["qualifying_flashing_equipment_verified"] = False
        adapter = Adapter()
        with self.assertRaisesRegex(ValueError, "qualifying flashing equipment"):
            execute(adapter, case, road, actors, authority, context)
        self.assertEqual(adapter.calls, [])

    def test_nonadjacent_route_requires_actual_separation(self):
        case = CASES[0]
        road, actors, authority, context = sources(case)
        road["nonadjacent_lane_adjacent_to_unit"] = True
        with self.assertRaisesRegex(ValueError, "cannot be adjacent"):
            plan(case, road, actors, authority, context)

    def test_roadway_impossibility_requires_absent_connected_route(self):
        case = next(c for c in CASES if c.condition == "roadway_impossible")
        road, actors, authority, context = sources(case)
        road["nonadjacent_route_connected"] = True
        with self.assertRaisesRegex(ValueError, "absent connected route"):
            plan(case, road, actors, authority, context)

    def test_traffic_weather_other_and_officer_sources_are_distinct(self):
        for target, change, error in (
            ("traffic_unsafe_adjacent", ("context", "traffic_trajectory_source", ""), "traffic_trajectory_source"),
            ("weather_unsafe_adjacent", ("context", "weather_readback_source", ""), "weather_readback_source"),
            ("other_hazard_adjacent", ("context", "other_hazard_geometry_source", ""), "other_hazard_geometry_source"),
            ("officer_directs_adjacent", ("authority", "law_enforcement_officer_verified", False), "law-enforcement")):
            case = next(c for c in CASES if c.suffix == target)
            road, actors, authority, context = sources(case)
            containers = {"context": context, "authority": authority}
            containers[change[0]][change[1]] = change[2]
            with self.assertRaisesRegex(ValueError, error):
                plan(case, road, actors, authority, context)

    def test_fallback_changes_lane_controller_window(self):
        case = CASES[0]
        road, actors, authority, context = sources(case)
        adapter = Adapter()
        execute(adapter, case, road, actors, authority, context,
                {"lane_change_start_s": 15.0, "lane_change_end_s": 24.0})
        call = next(arguments for name, arguments in adapter.calls
                    if name == "configure_ego_lane_route")
        self.assertEqual(call[1]["lane_change_start_s"], 15.0)


if __name__ == "__main__":
    unittest.main()
