"""Lazy, source-route vehicle controls for the 20 Hz intersection U-turn.

The route is a reviewed physical construction target. Controls are requests;
completion and legal context must be checked from original capture afterward.
"""
from __future__ import annotations

import math


class ControlError(ValueError):
    pass


def _need(ok, message):
    if not ok:
        raise ControlError(message)


def _finite(value):
    return isinstance(value, (float, int)) and math.isfinite(value)


def validate_route(points, *, expected_start_road=None):
    """Reject disconnected or malformed authored route samples before driving."""
    _need(isinstance(points, list) and len(points) >= 3, "route needs at least three samples")
    for index, point in enumerate(points):
        _need(all(_finite(point.get(key)) for key in ("x", "y", "target_speed_mps")),
              "route point missing finite position or speed")
        _need(0 < point["target_speed_mps"] <= 20, "route target speed outside controller range")
        _need(point.get("road_id") is not None and point.get("lane_id") is not None,
              "route lane identity missing")
        if index:
            distance = math.hypot(point["x"] - points[index - 1]["x"],
                                  point["y"] - points[index - 1]["y"])
            _need(0.15 <= distance <= 8, "route samples disconnected or repeated")
    if expected_start_road is not None:
        _need(points[0]["road_id"] == expected_start_road, "wrong route starting road")
    return points


class RouteFollower:
    """Follow a reviewed polyline without teleporting or lane-autopilot recovery.

    ``control_factory`` creates the simulator's vehicle-control object from
    throttle, steer and brake. The caller owns actor/world setup and cleanup.
    """

    def __init__(self, route, control_factory, *, arrival_radius_m=1.2,
                 max_cross_track_m=4.0, wheelbase_m=2.7):
        self.route = validate_route(route)
        _need(callable(control_factory), "control factory missing")
        _need(0.2 <= arrival_radius_m <= 3, "invalid waypoint arrival radius")
        _need(1 <= max_cross_track_m <= 8, "invalid cross-track limit")
        _need(1.5 <= wheelbase_m <= 5, "invalid wheelbase")
        self.factory = control_factory
        self.arrival_radius_m = arrival_radius_m
        self.max_cross_track_m = max_cross_track_m
        self.wheelbase_m = wheelbase_m
        self.index = 1
        self.finished = False

    def __call__(self, actor, tick_index):
        _need(isinstance(tick_index, int) and tick_index >= 0, "invalid control tick")
        transform = actor.get_transform()
        x, y = float(transform.location.x), float(transform.location.y)
        yaw = math.radians(float(transform.rotation.yaw))
        _need(all(math.isfinite(v) for v in (x, y, yaw)), "invalid live ego pose")
        velocity = actor.get_velocity()
        speed = math.hypot(float(velocity.x), float(velocity.y))
        _need(math.isfinite(speed), "invalid live ego speed")
        if self.finished:
            actor.apply_control(self.factory(throttle=0.0, steer=0.0, brake=1.0))
            return
        # Only advance when the next route sample is actually reached. Never
        # jump ahead to a geographically nearby branch of a hairpin.
        target = self.route[self.index]
        distance = math.hypot(target["x"] - x, target["y"] - y)
        if distance <= self.arrival_radius_m:
            if self.index == len(self.route) - 1:
                self.finished = True
                actor.apply_control(self.factory(throttle=0.0, steer=0.0, brake=1.0))
                return
            self.index += 1
            target = self.route[self.index]
            distance = math.hypot(target["x"] - x, target["y"] - y)
        previous = self.route[self.index - 1]
        dx, dy = target["x"] - previous["x"], target["y"] - previous["y"]
        segment = math.hypot(dx, dy)
        cross_track = abs((x - previous["x"]) * dy - (y - previous["y"]) * dx) / segment
        _need(cross_track <= self.max_cross_track_m, "route tracking lost")
        heading = math.atan2(target["y"] - y, target["x"] - x)
        error = (heading - yaw + math.pi) % (2 * math.pi) - math.pi
        # Pure-pursuit curvature, expressed as a bounded steering request.
        curvature = 2 * math.sin(error) / max(distance, self.arrival_radius_m)
        steer = max(-1.0, min(1.0, math.atan(self.wheelbase_m * curvature) / .65))
        speed_error = target["target_speed_mps"] - speed
        throttle = max(0.0, min(.6, .28 * speed_error))
        brake = max(0.0, min(.7, -.28 * speed_error))
        actor.apply_control(self.factory(throttle=throttle, steer=steer, brake=brake))


class TimedOtherVehicle:
    """Hold then follow the same other-vehicle path in near/far cases."""

    def __init__(self, follower, start_tick):
        _need(isinstance(start_tick, int) and 0 <= start_tick < 900,
              "invalid other-vehicle start tick")
        self.follower = follower
        self.start_tick = start_tick

    def __call__(self, actor, tick_index):
        if tick_index < self.start_tick:
            actor.apply_control(self.follower.factory(throttle=0.0, steer=0.0, brake=1.0))
        else:
            self.follower(actor, tick_index - self.start_tick)
