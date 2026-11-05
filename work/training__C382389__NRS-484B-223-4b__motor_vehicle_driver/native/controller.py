"""Observed-pose path controller for proposed C382389 straight constructions.

The route and target speed are requests. Completion is determined separately
from saved Native body/heading evidence; this controller never asserts it.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class EngineeringKnobs:
    lookahead_base_m: float = 4.0
    lookahead_speed_factor_s: float = 0.35
    max_steer_fraction: float = 0.70
    target_speed_mps: float = 5.0
    final_brake_mps2: float = 1.5
    final_margin_m: float = 3.0

    def validate(self) -> None:
        values = vars(self).values()
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Nonfinite engineering knob")
        if not (1 <= self.lookahead_base_m <= 10 and
                0 <= self.lookahead_speed_factor_s <= 2 and
                0 < self.max_steer_fraction <= 1 and
                0 < self.target_speed_mps <= 12 and
                0 < self.final_brake_mps2 <= 5 and
                0 <= self.final_margin_m <= 10):
            raise ValueError("Engineering knob outside declared range")


class PathController:
    def __init__(self, route_xy_m: list[list[float]], wheelbase_m: float,
                 max_steer_deg: float, knobs: EngineeringKnobs):
        knobs.validate()
        if len(route_xy_m) < 3 or wheelbase_m <= 0 or max_steer_deg <= 0:
            raise ValueError("Missing route or native vehicle steering geometry")
        self.route = [tuple(map(float, p)) for p in route_xy_m]
        self.stations = [0.0]
        for a, b in zip(self.route, self.route[1:]):
            gap = math.dist(a, b)
            if not (0 < gap < 0.3):
                raise ValueError("Route sample gap is discontinuous or duplicated")
            self.stations.append(self.stations[-1] + gap)
        self.wheelbase_m = wheelbase_m
        self.max_steer_rad = math.radians(max_steer_deg)
        self.knobs = knobs
        self.last_index = 0
        self.speed_integral = 0.0

    def step(self, *, position_xy_m: tuple[float, float], yaw_rad: float,
             speed_mps: float, dt_s: float) -> dict:
        values = (*position_xy_m, yaw_rad, speed_mps, dt_s)
        if not all(math.isfinite(v) for v in values) or speed_mps < 0 or not 0 < dt_s <= .2:
            raise ValueError("Invalid measured Native pose, speed or sample interval")
        # Search forward from observed pose. A prior index limits route snapping
        # but cannot teleport or claim completed motion.
        upper = min(len(self.route), self.last_index + 200)
        candidates = range(max(0, self.last_index - 10), upper)
        index = min(candidates, key=lambda i: math.dist(position_xy_m, self.route[i]))
        self.last_index = max(self.last_index, index)
        station = self.stations[self.last_index]
        error_m = math.dist(position_xy_m, self.route[self.last_index])
        lookahead_m = self.knobs.lookahead_base_m + self.knobs.lookahead_speed_factor_s * speed_mps
        target_station = min(self.stations[-1], station + lookahead_m)
        aim = self.last_index
        while aim < len(self.route) - 1 and self.stations[aim] < target_station:
            aim += 1
        dx = self.route[aim][0] - position_xy_m[0]
        dy = self.route[aim][1] - position_xy_m[1]
        alpha = math.atan2(dy, dx) - yaw_rad
        alpha = math.atan2(math.sin(alpha), math.cos(alpha))
        steer_rad = math.atan2(2 * self.wheelbase_m * math.sin(alpha), max(.01, math.hypot(dx, dy)))
        steer = clamp(steer_rad / self.max_steer_rad,
                      -self.knobs.max_steer_fraction, self.knobs.max_steer_fraction)
        remaining = max(0.0, self.stations[-1] - station - self.knobs.final_margin_m)
        braking_target = math.sqrt(2 * self.knobs.final_brake_mps2 * remaining)
        requested_speed = min(self.knobs.target_speed_mps, braking_target)
        error = requested_speed - speed_mps
        trial = clamp(self.speed_integral + dt_s * error, -2, 2)
        raw = .10 + .48 * error + .08 * trial
        # Hold integral at actuation saturation to avoid windup.
        if not ((raw > 1 and error > 0) or (raw < -1 and error < 0)):
            self.speed_integral = trial
        raw = .10 + .48 * error + .08 * self.speed_integral
        throttle = 0.0 if requested_speed < .05 else clamp(raw, 0, 1)
        brake = clamp(-raw, 0, 1)
        if requested_speed < .05:
            brake = max(brake, .6)
        return {"throttle": throttle, "brake": brake, "steer": steer,
                "hand_brake": requested_speed < .05 and speed_mps < .05,
                "requested_speed_mps": requested_speed,
                "observed_speed_mps": speed_mps,
                "route_station_m": station,
                "route_error_m": error_m,
                "aim_native_xy_m": list(self.route[aim]),
                "observed_native_xy_m": list(position_xy_m),
                "observed_native_yaw_rad": yaw_rad,
                "controller_integral_mps_s": self.speed_integral}
