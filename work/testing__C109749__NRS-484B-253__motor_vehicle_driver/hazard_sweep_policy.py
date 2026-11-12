"""Candidate control policy for source-measured approach sweeps.

The time-to-conflict setting is engineering control only, not a legal threshold.
This module is not yet selected by a canonical exact construction.
"""
import math


class HazardSweepPolicy:
    def __init__(self, *, release_ttc_s, approach_speed_mps):
        if not all(math.isfinite(x) and x > 0 for x in (release_ttc_s, approach_speed_mps)):
            raise ValueError("Positive finite engineering controls required")
        self.release_ttc_s = release_ttc_s
        self.approach_speed_mps = approach_speed_mps
        self.state = "approach"
        self.hazard_seen = False

    def step(self, *, distance_to_hold_m, ego_speed_mps,
             oncoming_distance_to_conflict_m, oncoming_closing_speed_mps,
             oncoming_in_intersection, oncoming_cleared, turn_complete):
        values = (distance_to_hold_m, ego_speed_mps,
                  oncoming_distance_to_conflict_m, oncoming_closing_speed_mps)
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or
               not math.isfinite(x) for x in values):
            raise ValueError("Finite measured control inputs required")
        if self.state == "complete" or turn_complete:
            self.state = "complete"
            return {"state": "complete", "throttle": 0.0, "brake": 1.0,
                    "steer": 0.0, "left_indicator": False}
        ttc = (oncoming_distance_to_conflict_m / oncoming_closing_speed_mps
               if oncoming_distance_to_conflict_m >= 0 and oncoming_closing_speed_mps > 0
               else None)
        demand_yield = oncoming_in_intersection or (ttc is not None and ttc < self.release_ttc_s)
        if demand_yield:
            self.hazard_seen = True
        if self.state in ("approach", "yield") and distance_to_hold_m <= 2.0:
            self.state = "yield"
        # An unentered, distant opponent need not become "cleared" before the
        # controller can express the far-approach construction. Body occupancy
        # and measured TTC still prevent the turn during the engineering hazard.
        # A controller that already observed the approaching hazard must not
        # treat a later increase in TTC as evidence that yielding is complete.
        # Require the source-measured clearance signal before turning.
        if self.state == "yield" and not demand_yield and (not self.hazard_seen or oncoming_cleared):
            self.state = "turn"
        if self.state == "yield":
            return {"state": "yield", "throttle": 0.0, "brake": 1.0,
                    "steer": 0.0, "left_indicator": True}
        if self.state == "turn":
            return {"state": "turn", "throttle": 0.35, "brake": 0.0,
                    "steer": -0.45, "left_indicator": True}
        error = self.approach_speed_mps - ego_speed_mps
        return {"state": "approach", "throttle": max(0.0, min(0.5, 0.12 * error)),
                "brake": 0.0 if distance_to_hold_m > 8 else 0.35,
                "steer": 0.0, "left_indicator": True}
