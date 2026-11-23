import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "controlled_access_exit.py"
spec = importlib.util.spec_from_file_location("controlled_access_exit", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def site():
    return {
        "cell_id": "C228302", "layout": "road", "maneuver": "exit_road",
        "ego_blueprint": "vehicle.car", "ego_blueprint_source_sha256": "ego-hash",
        "approach_blueprint": "vehicle.car", "approach_blueprint_source_sha256": "other-hash",
        "driver_control_source_sha256": "driver-hash",
        "road": {
            "map_sha256": "map-hash", "public_dedication_source_sha256": "dedication-hash",
            "public_access_source_sha256": "access-hash", "restricted_access_authority_source_sha256": "authority-hash",
            "restricted_access_determination_source_sha256": "determination-hash",
            "highway_boundary_source_sha256": "boundary-hash", "exit_connection_source_sha256": "connection-hash",
            "route_source_sha256": "route-hash", "controlled_access_readback": True,
            "exit_connection_readback": True, "exit_waypoints": [[-3, 0], [-2, 0], [0, 0], [2, 0]],
            "highway_approach_waypoints": [[0, -10], [0, -5], [0, 0], [0, 5]],
            "exit_merge_polygon_xy": [[-1, -1], [1, -1], [1, 1], [-1, 1]],
        },
    }


class Adapter:
    def __init__(self, fail_at=None):
        self.calls = []
        self.fail_at = fail_at

    def read_map_hash(self):
        return "map-hash"

    def read_controlled_access(self, road):
        return True

    def read_exit_connection(self, road):
        return True

    def spawn_vehicle(self, point, blueprint, role):
        self.calls.append(("spawn", role, tuple(point)))
        if len([c for c in self.calls if c[0] == "spawn"]) == self.fail_at:
            return None
        return len([c for c in self.calls if c[0] == "spawn"])

    def set_route(self, actor, route, role):
        self.calls.append(("route", role, actor))

    def set_headway(self, actor, headway):
        self.calls.append(("headway", actor, headway))

    def set_exit_policy(self, ego, policy, approaching):
        self.calls.append(("policy", policy, tuple(approaching)))

    def destroy(self, actor):
        self.calls.append(("destroy", actor))


def rows(case):
    result = []
    for i in range(900):
        result.append({
            "case_id": case.name, "original_frame": 100 + i, "elapsed_s": i * .05,
            "ego_id": 1, "map_sha256": "map-hash", "site_sha256": "site-hash",
            "camera_plan_sha256": "camera-hash", "road_authority_source_sha256": "authority-hash",
            "source_sha256": "packet-hash", "control_source_sha256": "control-hash",
            "ego_center_xy": [0, 0] if i >= 20 else [-3, 0],
            "ego_speed_mps": 0 if i < 20 else 2,
            "approaching_vehicles": [{
                "actor_id": j + 2, "source_sha256": "vehicle-hash",
                "highway_occupancy_source_sha256": "occupancy-hash", "on_highway": True,
                "range_to_interaction_m": max(0, 50 - i * .1 + j * 5), "speed_mps": 5,
            } for j in range(case.approaching_count)],
        })
    return result


def audit_record(case):
    return {
        "case_id": case.name, "frame_count": 900, "original_history_sha256": "history-hash",
        "map_sha256": "map-hash", "site_sha256": "site-hash", "camera_plan_sha256": "camera-hash",
        "exit_route_sha256": "exit-hash", "approach_route_sha256": "approach-hash",
        "blueprints_sha256": "blueprint-hash", "policy": case.policy,
        "approaching_count": case.approaching_count, "approach_headway_s": case.approach_headway_s,
    }


class Tests(unittest.TestCase):
    def test_source_gates(self):
        module.validate_site(site(), module.CASES[0])
        for key in ("restricted_access_determination_source_sha256", "exit_connection_source_sha256"):
            s = site()
            del s["road"][key]
            with self.assertRaisesRegex(ValueError, "road source missing"):
                module.validate_site(s, module.CASES[0])

    def test_construct_two_approachers(self):
        a = Adapter()
        built = module.build_case(a, site(), module.CASES[2])
        self.assertEqual(len(built["approaching"]), 2)
        self.assertEqual(len([x for x in a.calls if x[0] == "spawn"]), 3)
        self.assertIn(("policy", "yield_until_clear", (2, 3)), a.calls)

    def test_spawn_failure_rolls_back(self):
        a = Adapter(fail_at=3)
        with self.assertRaisesRegex(ValueError, "approaching vehicle spawn failed"):
            module.build_case(a, site(), module.CASES[2])
        self.assertEqual(a.calls[-2:], [("destroy", 2), ("destroy", 1)])

    def test_measure_original_history_and_all_vehicles(self):
        case = module.CASES[2]
        measured = module.measure_history(rows(case), site(), case)
        self.assertEqual(measured["first_entry_frame"], 120)
        self.assertEqual(measured["pre_entry_wait_frames"], 20)
        self.assertEqual(measured["approaching_actor_ids"], [2, 3])
        self.assertIsNone(measured["immediate_hazard_judgment"])

    def test_reject_missing_approacher(self):
        case = module.CASES[2]
        history = rows(case)
        history[150]["approaching_vehicles"].pop()
        with self.assertRaisesRegex(ValueError, "all approaching vehicles required"):
            module.measure_history(history, site(), case)

    def test_reject_time_or_road_source_change(self):
        case = module.CASES[0]
        history = rows(case)
        history[5]["elapsed_s"] += .02
        with self.assertRaisesRegex(ValueError, "20 Hz"):
            module.measure_history(history, site(), case)
        history = rows(case)
        history[5]["road_authority_source_sha256"] = "other"
        with self.assertRaisesRegex(ValueError, "fixed source"):
            module.measure_history(history, site(), case)

    def test_comparison_isolation(self):
        left, right = map(audit_record, module.CASES[:2])
        self.assertEqual(module.audit_comparison(left, right, "policy")["difference"], "policy")
        right["camera_plan_sha256"] = "different"
        with self.assertRaisesRegex(ValueError, "fixed comparison condition changed"):
            module.audit_comparison(left, right, "policy")

    def test_reject_undeclared_difference(self):
        left, right = map(audit_record, module.CASES[:2])
        right["approach_headway_s"] = 5
        with self.assertRaisesRegex(ValueError, "undeclared difference"):
            module.audit_comparison(left, right, "policy")


if __name__ == "__main__":
    unittest.main()
