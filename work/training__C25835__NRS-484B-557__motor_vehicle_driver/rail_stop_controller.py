"""Feedback controller policy for five rail stop positions.

The policy requests motion only. Native readback and independent review determine
whether a stop, subsequent movement, and due care actually occurred.
"""

import math


RATE_HZ = 20
FRAME_COUNT = 600
FEET_PER_METRE = 3.280839895013123
STOP_CENTER_DISTANCE_FT = {"probe_1": 25.0, "probe_2": 10.0, "probe_3": 15.0, "probe_4": 50.0, "probe_5": 50.5}


class RailStopController:
    def __init__(self, case, nearest_track_approach_edge_x_m, brake_gain=0.7):
        if case not in STOP_CENTER_DISTANCE_FT:
            raise ValueError("Unknown rail stop case")
        if not isinstance(nearest_track_approach_edge_x_m, (int, float)) or not math.isfinite(nearest_track_approach_edge_x_m):
            raise ValueError("Missing observed rail geometry")
        if isinstance(brake_gain, bool) or not isinstance(brake_gain, (int, float)) or not 0.6 <= brake_gain <= 1.0:
            raise ValueError("Invalid braking gain")
        self.case = case
        self.target_x = float(nearest_track_approach_edge_x_m) - STOP_CENTER_DISTANCE_FT[case] / FEET_PER_METRE
        self.brake_gain = float(brake_gain)
        self.phase = "approach"
        self.hold_frames = 0

    def command(self, frame, vehicle_center_x_m, observed_speed_mps, rail_approach_visibility):
        if type(frame) is not int or not 0 <= frame < FRAME_COUNT:
            raise ValueError("Invalid frame")
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
               for x in (vehicle_center_x_m, observed_speed_mps)) or observed_speed_mps < 0:
            raise ValueError("Missing Native pose or speed")
        if rail_approach_visibility not in {"clear", "occluded", "unknown"}:
            raise ValueError("Missing sourced visibility")
        remaining = self.target_x - vehicle_center_x_m
        if self.phase == "approach":
            if remaining < -1.0:
                raise ValueError("Vehicle overshot requested stop position")
            if remaining <= 0.5 and observed_speed_mps <= 0.10:
                self.phase = "hold"
            elif remaining <= max(1.0, observed_speed_mps ** 2 / 4.0 + 1.0):
                return {"phase": "brake", "throttle": 0.0, "brake": self.brake_gain, "steer": 0.0}
            else:
                return {"phase": "approach", "throttle": 0.25, "brake": 0.0, "steer": 0.0}
        if self.phase == "hold":
            if observed_speed_mps > 0.10:
                self.hold_frames = 0
            else:
                self.hold_frames += 1
            # Hold for acquisition stability. This is not a statutory minimum.
            if self.hold_frames >= RATE_HZ and rail_approach_visibility == "clear":
                self.phase = "proceed"
            else:
                return {"phase": "hold", "throttle": 0.0, "brake": 1.0, "steer": 0.0}
        if self.phase == "proceed":
            if rail_approach_visibility != "clear":
                self.phase = "hold"
                self.hold_frames = 0
                return {"phase": "hold", "throttle": 0.0, "brake": 1.0, "steer": 0.0}
            return {"phase": "proceed", "throttle": 0.20, "brake": 0.0, "steer": 0.0}
        raise AssertionError("Unreachable controller phase")
