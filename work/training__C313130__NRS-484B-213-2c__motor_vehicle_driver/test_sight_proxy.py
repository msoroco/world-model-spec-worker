"""Source-shaped tests for the original incoming-lane ray bracket adapter."""

import unittest

from sight_proxy import incoming_lane_bracket


class SightProxyTests(unittest.TestCase):
    def source(self, bound, **horizon):
        return {"method": "actual_actor_body_raycast_v3",
                "ego_projection": {"road_id": 7, "lane_id": -1},
                "approaches": [{"lane_id": -1,
                    "any_body_sight_horizon": {"bound": bound, **horizon}},
                    {"lane_id": 1, "any_body_sight_horizon":
                        {"bound": "at_least", "distance_m": 230.0}}]}

    def test_blocked_bracket_is_measured_proxy(self):
        result = incoming_lane_bracket(self.source("first_sampled_occlusion",
            bracket_m=[29.75, 30.0]), 7, -1)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["clear_lower_bound_m"], 29.75)
        self.assertEqual(result["blocker_upper_bound_m"], 30.0)
        self.assertEqual(result["legal_view_obstructed"], "independent_judgment_required")

    def test_clear_to_limit_is_censored(self):
        result = incoming_lane_bracket(self.source("at_least", distance_m=230.0), 7, -1)
        self.assertEqual(result["status"], "clear_to_limit")
        self.assertEqual(result["clear_lower_bound_m"], 230.0)
        self.assertIsNone(result["blocker_upper_bound_m"])

    def test_wrong_road_lane_and_missing_route_remain_unknown(self):
        source = self.source("route_limit", distance_m=10.0, unknown=True)
        for road, lane in ((8, -1), (7, -2), (7, -1)):
            self.assertEqual(incoming_lane_bracket(source, road, lane)["status"], "unknown")

    def test_invalid_horizon_does_not_invent_blocker(self):
        for horizon in ({"bracket_m": [30.0, 29.0]}, {"bracket_m": [0.0, float("nan")]},
                        {"distance_m": -1.0}):
            bound = "at_least" if "distance_m" in horizon else "first_sampled_occlusion"
            self.assertEqual(incoming_lane_bracket(self.source(bound, **horizon), 7, -1)["status"],
                             "unknown")


if __name__ == "__main__":
    unittest.main()
