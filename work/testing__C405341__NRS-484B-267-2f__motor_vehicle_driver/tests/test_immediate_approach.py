"""Source gating and actual Native adapter calls without CARLA."""
import sys
import unittest
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from emergency_construction import CASES, execute, plan
from analysis import measure_case


def sources(case):
    road = {"source_kind": "native_map_readback", "road_type": "paved_road",
            "ego_route_connected": True, "unit_route_connected": True,
            "unit_route_approaches_ego": case.immediate,
            "unit_route_direction": case.direction,
            "unit_state": case.state,
            "visible_preparation_source": "reviewed-original-hand-signal" if case.state == "preparing" else None,
            "stop_location_source": "reviewed-original-stop-site" if case.state == "stopped" else None,
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
    def test_ten_variants_execute_real_controller_calls(self):
        self.assertEqual(len(CASES), 10)
        for case in CASES:
            with self.subTest(case=case.suffix):
                adapter = Adapter()
                result = execute(adapter, case, *sources(case))
                names = [name for name, _ in adapter.calls]
                self.assertEqual(result["capture_frames"], 900)
                self.assertEqual(names.count("spawn_vehicle"), 2)
                self.assertEqual(names.count("configure_route"), 2)
                self.assertIn("configure_unit_movement", names)
                self.assertEqual("configure_visible_preparation" in names, case.state == "preparing")
                self.assertEqual("configure_unit_stop" in names, case.state == "stopped")
                self.assertIn("configure_ego_response", names)
                self.assertEqual("configure_officer_direction" in names, case.officer_direction)

    def test_legal_predicates_rejected_before_spawn(self):
        road, actors, authority = sources(CASES[0])
        adapter = Adapter()
        road["unit_route_approaches_ego"] = False
        with self.assertRaisesRegex(ValueError, "immediate approach"):
            execute(adapter, CASES[0], road, actors, authority)
        self.assertEqual(adapter.calls, [])
        road["unit_route_approaches_ego"] = True
        authority["light_rule_source"] = None
        with self.assertRaisesRegex(ValueError, "light_rule_source"):
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

    def test_original_branch_histories_reject_missing_cues_and_false_routes(self):
        root = Path(__file__).resolve().parents[1] / "diagnostics"
        for suffix in ("no_immediate_approach", "preparing_visible_hand_signal", "stopped_referral"):
            case = next(c for c in CASES if c.suffix == suffix)
            folder = root / suffix
            site = json.loads((folder / "emergency-site.json").read_text())
            history = [json.loads(x) for x in (folder / "original-emergency-movement-history.jsonl").read_text().splitlines()]
            measured = measure_case(case, site, history)
            self.assertEqual(measured["subsection_1_referral"]["requested"], suffix == "preparing_visible_hand_signal")
            if suffix == "no_immediate_approach":
                self.assertLess(history[200]["emergency_xy"][0], history[0]["emergency_xy"][0])
                history[200]["emergency_xy"][0] = history[0]["emergency_xy"][0]
                with self.assertRaisesRegex(ValueError, "move away"):
                    measure_case(case, site, history)
            elif suffix == "preparing_visible_hand_signal":
                self.assertTrue(measured["visible_hand_signal_original_frames"])
                for row in history:
                    row["visible_hand_signal"] = False
                with self.assertRaisesRegex(ValueError, "visible preparation"):
                    measure_case(case, site, history)
            else:
                self.assertEqual(max(measured["movement_original_frames"]), 500)
                history[600]["emergency_xy"][0] += 1
                with self.assertRaisesRegex(ValueError, "actual stop"):
                    measure_case(case, site, history)


if __name__ == "__main__":
    unittest.main()
