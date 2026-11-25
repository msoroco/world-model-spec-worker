"""Bounded longitudinal control for the two sourced Native vehicles.

Target speeds and gaps are construction inputs, never legal speed limits.
Observed speed and body gap remain source measurements after capture.
"""
import math


def _positive(value, label, *, zero=False):
    if type(value) not in (int, float) or not math.isfinite(value) or (value < 0 if zero else value <= 0):
        raise ValueError("Finite positive " + label + " required")
    return float(value)


class LongitudinalController:
    def __init__(self, target_speed_mps, *, minimum_body_gap_m=4.0,
                 approach_body_gap_m=12.0, gain=0.2):
        self.target = _positive(target_speed_mps, "target speed", zero=True)
        self.minimum_gap = _positive(minimum_body_gap_m, "minimum body gap")
        self.approach_gap = _positive(approach_body_gap_m, "approach body gap")
        self.gain = _positive(gain, "speed gain")
        if self.approach_gap <= self.minimum_gap:
            raise ValueError("Approach gap must exceed minimum body gap")

    def step(self, speed_mps, *, lead_body_gap_m=None):
        speed = _positive(speed_mps, "observed speed", zero=True)
        if lead_body_gap_m is not None:
            gap = _positive(lead_body_gap_m, "observed body gap", zero=True)
            if gap <= self.minimum_gap:
                return {"throttle": 0.0, "brake": 1.0, "gap_guard": "emergency"}
            if gap <= self.approach_gap:
                ratio = (gap - self.minimum_gap) / (self.approach_gap - self.minimum_gap)
                allowed_speed = self.target * ratio
                if speed > allowed_speed:
                    return {"throttle": 0.0, "brake": min(1.0, .2 + (speed - allowed_speed) * self.gain),
                            "gap_guard": "approach"}
        error = self.target - speed
        if error <= 0:
            return {"throttle": 0.0, "brake": min(1.0, -error * self.gain),
                    "gap_guard": "clear"}
        return {"throttle": min(.45, error * self.gain), "brake": 0.0,
                "gap_guard": "clear"}
