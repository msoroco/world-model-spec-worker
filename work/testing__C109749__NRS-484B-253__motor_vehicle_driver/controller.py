"""Engineering control policy for the authored left-turn interaction.

The four-second release rule is a controller tuning parameter. It does not
define the statute's phrase "immediate hazard" or decide right-of-way.
"""

import math


class LeftTurnController:
    def __init__(self, *, release_ttc_s=4.0, approach_speed_mps=5.0):
        if release_ttc_s <= 0 or approach_speed_mps <= 0:
            raise ValueError("Positive controller parameters required")
        self.release_ttc_s = release_ttc_s
        self.approach_speed_mps = approach_speed_mps
        self.state = "approach"

    def step(self, *, distance_to_hold_m, ego_speed_mps, oncoming_distance_to_conflict_m,
             oncoming_closing_speed_mps, oncoming_in_intersection, oncoming_cleared,
             turn_complete):
        values = (distance_to_hold_m, ego_speed_mps,
                  oncoming_distance_to_conflict_m, oncoming_closing_speed_mps)
        if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) for v in values):
            raise ValueError("Finite measured control inputs required")
        if self.state == "complete":
            return {"state": self.state, "throttle": 0.0, "brake": 1.0,
                    "steer": 0.0, "left_indicator": False}
        if turn_complete:
            self.state = "complete"
            return {"state": self.state, "throttle": 0.0, "brake": 1.0,
                    "steer": 0.0, "left_indicator": False}
        ttc = (oncoming_distance_to_conflict_m / oncoming_closing_speed_mps
               if oncoming_distance_to_conflict_m >= 0 and oncoming_closing_speed_mps > 0 else None)
        demand_yield = oncoming_in_intersection or (ttc is not None and ttc < self.release_ttc_s)
        if self.state in ("approach", "yield") and distance_to_hold_m <= 2.0:
            self.state = "yield"
        if self.state == "yield" and oncoming_cleared and not demand_yield:
            self.state = "turn"
        if self.state == "yield":
            return {"state": self.state, "throttle": 0.0, "brake": 1.0,
                    "steer": 0.0, "left_indicator": True}
        if self.state == "turn":
            return {"state": self.state, "throttle": 0.35, "brake": 0.0,
                    "steer": -0.45, "left_indicator": True}
        error = self.approach_speed_mps - ego_speed_mps
        return {"state": self.state, "throttle": max(0.0, min(0.5, 0.12 * error)),
                "brake": 0.0 if distance_to_hold_m > 8 else 0.35,
                "steer": 0.0, "left_indicator": True}
