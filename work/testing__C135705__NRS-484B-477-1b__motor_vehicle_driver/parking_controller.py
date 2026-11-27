"""Low-level route tracking, braking, hold and departure for an alley attempt.

Controls are requests; only Native readback establishes actual parking motion.
"""
from __future__ import annotations

import math


def _point(value):
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ValueError("vehicle position missing")
    x, y = value
    if any(type(a) not in (int, float) or not math.isfinite(a) for a in (x, y)):
        raise ValueError("vehicle position nonfinite")
    return float(x), float(y)


class ParkingController:
    def __init__(self, plan: dict):
        self.plan = plan
        self.phase = "approach"
        self.hold_since = None
        self.target = _point(plan["target_xy_m"])
        self.depart = _point(plan["depart_xy_m"])
        self.axis = _point(plan["route_axis_xy"])
        self.direction = plan["direction"]
        if abs(math.hypot(*self.axis) - 1) > .001 or self.direction not in (-1, 1):
            raise ValueError("invalid surveyed route axis")

    def step(self, *, xy_m, yaw_rad, speed_mps, time_s) -> dict:
        xy = _point(xy_m)
        if any(type(x) not in (int, float) or not math.isfinite(x)
               for x in (yaw_rad, speed_mps, time_s)) or speed_mps < 0:
            raise ValueError("Native vehicle state invalid")
        axis = (self.axis[0] * self.direction, self.axis[1] * self.direction)
        dx, dy = xy[0] - self.target[0], xy[1] - self.target[1]
        remaining = -(dx * axis[0] + dy * axis[1])
        lateral = abs(dx * -axis[1] + dy * axis[0])
        if lateral > 3.0:
            raise ValueError("vehicle left surveyed alley route")
        if self.phase == "approach" and remaining < 1.0:
            self.phase = "braking"
        if self.phase == "braking" and speed_mps <= .1 and math.hypot(dx, dy) <= .75:
            self.phase = "hold"
            self.hold_since = time_s
        if self.phase == "hold" and time_s - self.hold_since >= self.plan["controller"]["hold_min_s"]:
            self.phase = "depart"
        if self.phase == "depart" and math.dist(xy, self.depart) <= 1.0:
            self.phase = "done"
        if self.phase in ("braking", "hold", "done"):
            return {"phase": self.phase, "throttle": 0.0, "brake": 1.0, "steer": 0.0}
        desired_yaw = math.atan2(axis[1], axis[0])
        heading_error = (desired_yaw - yaw_rad + math.pi) % (2 * math.pi) - math.pi
        signed_lateral = dx * -axis[1] + dy * axis[0]
        steer = max(-.45, min(.45, 1.2 * heading_error - .12 * signed_lateral))
        target_speed = min(4.0, max(.8, remaining / 2)) if self.phase == "approach" else 3.0
        throttle = max(0.0, min(.6, .2 * (target_speed - speed_mps)))
        brake = max(0.0, min(.6, .3 * (speed_mps - target_speed)))
        return {"phase": self.phase, "throttle": throttle, "brake": brake, "steer": steer}
