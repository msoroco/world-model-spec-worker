"""Observed-pose controller for the two proposed signed-road movements.

Requested movement is never treated as observed statutory evidence.
"""
from __future__ import annotations

import math


def _clamp(value, low, high):
    return max(low, min(high, value))


class PathController:
    def __init__(self, route_xy_m, wheelbase_m, max_steer_deg, *, target_speed_mps, lookahead_m):
        if len(route_xy_m) < 3 or not 1.0 < wheelbase_m < 5.0 or not 5 < max_steer_deg < 60:
            raise ValueError('Missing Native route or measured vehicle steering geometry')
        if not 0 < target_speed_mps <= 8 or not 2 <= lookahead_m <= 8:
            raise ValueError('Engineering request outside declared range')
        self.route = [tuple(map(float, p)) for p in route_xy_m]
        self.stations = [0.0]
        for a, b in zip(self.route, self.route[1:]):
            gap = math.dist(a, b)
            if not 0 < gap < .2:
                raise ValueError('Duplicate or discontinuous route sample')
            self.stations.append(self.stations[-1] + gap)
        self.wheelbase_m = wheelbase_m
        self.max_steer_rad = math.radians(max_steer_deg)
        self.target_speed_mps = target_speed_mps
        self.lookahead_m = lookahead_m
        self.last_index = 0
        self.speed_integral = 0.0

    def step(self, *, position_xy_m, yaw_rad, speed_mps, dt_s):
        values = (*position_xy_m, yaw_rad, speed_mps, dt_s)
        if not all(math.isfinite(v) for v in values) or speed_mps < 0 or not 0 < dt_s <= .2:
            raise ValueError('Invalid observed Native state')
        lower = max(0, self.last_index - 10)
        upper = min(len(self.route), self.last_index + 200)
        nearest = min(range(lower, upper), key=lambda i: math.dist(position_xy_m, self.route[i]))
        self.last_index = max(self.last_index, nearest)
        station = self.stations[self.last_index]
        aim = self.last_index
        requested_lookahead = self.lookahead_m + .25 * speed_mps
        while aim < len(self.route) - 1 and self.stations[aim] < station + requested_lookahead:
            aim += 1
        dx = self.route[aim][0] - position_xy_m[0]
        dy = self.route[aim][1] - position_xy_m[1]
        alpha = math.atan2(dy, dx) - yaw_rad
        alpha = math.atan2(math.sin(alpha), math.cos(alpha))
        steering_rad = math.atan2(2 * self.wheelbase_m * math.sin(alpha), max(.01, math.hypot(dx, dy)))
        steering = _clamp(steering_rad / self.max_steer_rad, -.7, .7)
        remaining = max(0.0, self.stations[-1] - station - 2.0)
        requested_speed = min(self.target_speed_mps, math.sqrt(3.0 * remaining))
        speed_error = requested_speed - speed_mps
        trial = _clamp(self.speed_integral + dt_s * speed_error, -2, 2)
        raw = .1 + .48 * speed_error + .08 * trial
        if not ((raw > 1 and speed_error > 0) or (raw < -1 and speed_error < 0)):
            self.speed_integral = trial
        raw = .1 + .48 * speed_error + .08 * self.speed_integral
        return {
            'throttle': 0.0 if requested_speed < .05 else _clamp(raw, 0, 1),
            'brake': max(.6, _clamp(-raw, 0, 1)) if requested_speed < .05 else _clamp(-raw, 0, 1),
            'steer': steering,
            'hand_brake': requested_speed < .05 and speed_mps < .05,
            'requested_speed_mps': requested_speed,
            'observed_speed_mps': speed_mps,
            'observed_native_xy_m': list(position_xy_m),
            'observed_native_yaw_rad': yaw_rad,
            'route_station_m': station,
            'route_error_m': math.dist(position_xy_m, self.route[self.last_index]),
            'aim_native_xy_m': list(self.route[aim]),
        }
