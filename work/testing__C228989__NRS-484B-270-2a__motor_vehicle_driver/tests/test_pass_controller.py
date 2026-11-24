"""Physical controller contract checks; no legal outcome is inferred."""

import importlib.util
import json
from pathlib import Path
import unittest


MODULE = Path(__file__).resolve().parents[1] / "pass_controller.py"
spec = importlib.util.spec_from_file_location("pass_controller", MODULE)
controller = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = controller
spec.loader.exec_module(controller)


class ControllerTests(unittest.TestCase):
    def sample(self, **changes):
        values = dict(ego_lane="right", control_lane="right", immediate_left_lane="left",
                      same_direction_lane_count=2, longitudinal_gap_m=12.0,
                      relative_speed_mps=3.0, left_lane_occupants=(),
                      left_lane_restricted=False, left_lane_obstructed=False,
                      source_frame=20)
        values.update(changes)
        return controller.Observation(**values)

    def test_open_left_move_request_is_one_frame_intent(self):
        move = controller.command("move_left", self.sample())
        self.assertEqual(move["lane_change"], "immediate_left")
        self.assertEqual(move["longitudinal"], "hold_back")
        self.assertEqual(move["source_frame"], 20)

    def test_occupied_restricted_or_obstructed_lane_inhibits_move(self):
        for change in ({"left_lane_occupants": ("other_car",)},
                       {"left_lane_restricted": True}, {"left_lane_obstructed": True}):
            with self.subTest(change=change):
                result = controller.command("move_left", self.sample(**change))
                self.assertEqual(result["lane_change"], "none")
                self.assertEqual(result["longitudinal"], "hold_back")

    def test_requested_stay_is_distinct_from_move(self):
        result = controller.command("stay", self.sample())
        self.assertEqual((result["lane_change"], result["longitudinal"]),
                         ("none", "pass_control"))

    def test_one_lane_pass_and_follow_controls(self):
        sample = self.sample(same_direction_lane_count=1, immediate_left_lane=None)
        self.assertEqual(controller.command("pass", sample)["longitudinal"], "pass_control")
        self.assertEqual(controller.command("follow", sample)["longitudinal"], "follow_control")

    def test_mismatched_lanes_and_requests_fail_closed(self):
        for request, sample in (("move_left", self.sample(control_lane="left")),
                                ("pass", self.sample()),
                                ("move_left", self.sample(immediate_left_lane=None)),
                                ("unknown", self.sample()),
                                ("move_left", self.sample(longitudinal_gap_m=0))):
            with self.subTest(request=request, sample=sample):
                with self.assertRaises(ValueError):
                    controller.command(request, sample)

    def test_every_planned_case_binds_and_traffic_mismatch_rejects(self):
        plan = json.loads((MODULE.parent / "case-plan.json").read_text(encoding="utf-8"))
        self.assertEqual(len(plan["cases"]), 14)
        for case in plan["cases"]:
            with self.subTest(case=case["case_id"]):
                lane_count = case["same_direction_lane_count_requested"]
                occupied = case["left_lane_traffic_requested"] == "occupied"
                sample = self.sample(same_direction_lane_count=lane_count,
                                     immediate_left_lane="left" if lane_count == 2 else None,
                                     left_lane_occupants=("other_car",) if occupied else ())
                result = controller.command_for_case(case, sample)
                self.assertEqual(result["source_frame"], 20)
                if lane_count == 2:
                    opposite = self.sample(left_lane_occupants=() if occupied else ("other_car",))
                    with self.assertRaises(ValueError):
                        controller.command_for_case(case, opposite)


if __name__ == "__main__":
    unittest.main()
