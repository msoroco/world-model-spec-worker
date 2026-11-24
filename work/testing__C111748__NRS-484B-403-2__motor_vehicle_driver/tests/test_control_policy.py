import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("device_control_policy", ROOT / "control_policy.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
BASE = "testing__C111748__NRS-484B-403-2__motor_vehicle_driver__"


def site(prohibited=True):
    return {"device": {"device_id": 77, "governed_approach": "A",
                       "prohibits_u_turn": prohibited},
            "u_turn_route": [{"road_id": 1, "lane_id": 1, "x": 0, "y": 0},
                             {"road_id": 1, "lane_id": 1, "x": 10, "y": 0},
                             {"road_id": 1, "lane_id": -1, "x": 0, "y": 5}]}


def ego(x=0, y=0, yaw=0):
    return {"x": x, "y": y, "yaw_deg": yaw, "approach_id": "A"}


def readback(prohibited=True, visible=True):
    return {"device_id": 77, "prohibits_u_turn": prohibited,
            "visible_to_ego": visible}


class Tests(unittest.TestCase):
    def test_turn_waits_for_prior_governed_observation(self):
        case = BASE + "prohibited_attempt"
        before = mod.command(case, site(), ego(), readback(),
                             first_visible_frame=100, original_frame=100)
        self.assertEqual(before["phase"], "hold_before_observation")
        self.assertFalse(before["requested_turn"])
        after = mod.command(case, site(), ego(), readback(),
                            first_visible_frame=100, original_frame=101)
        self.assertEqual(after["phase"], "route_turn")
        self.assertEqual(after["throttle"], 0.25)

    def test_prohibition_obedience_holds_after_observation(self):
        out = mod.command(BASE + "prohibited_obey", site(), ego(), readback(),
                          first_visible_frame=100, original_frame=101)
        self.assertEqual(out["phase"], "obey_no_turn")
        self.assertEqual(out["brake"], 1)

    def test_neutral_device_turn_uses_same_route(self):
        out = mod.command(BASE + "neutral_device_turn", site(False), ego(9, 0),
                          readback(False), first_visible_frame=100, original_frame=101)
        self.assertEqual(out["phase"], "route_turn")
        self.assertGreater(out["steer"], 0)

    def test_reject_display_and_governed_approach_drift(self):
        with self.assertRaisesRegex(mod.PolicyError, "reviewed display"):
            mod.command(BASE + "neutral_device_turn", site(), ego(), readback(False),
                        first_visible_frame=100, original_frame=101)
        bad = ego(); bad["approach_id"] = "B"
        with self.assertRaisesRegex(mod.PolicyError, "governed approach"):
            mod.command(BASE + "prohibited_attempt", site(), bad, readback(),
                        first_visible_frame=100, original_frame=101)

    def test_reject_route_without_coordinates(self):
        item = site(); del item["u_turn_route"][1]["x"]
        with self.assertRaisesRegex(mod.PolicyError, "waypoint coordinates"):
            mod.command(BASE + "prohibited_attempt", item, ego(), readback(),
                        first_visible_frame=100, original_frame=101)
