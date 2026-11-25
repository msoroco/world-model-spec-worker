"""Conservative engineering controller for the surveyed intersection.

The controller uses current Native observations only. A proximity hold is an
engineering safety choice and never labels a statutory immediate hazard.
"""
from __future__ import annotations

from math import atan2, cos, hypot, isfinite, pi, sin


def _number(value, name):
    if type(value) not in (int, float) or not isfinite(value):
        raise ValueError("missing Native " + name)
    return float(value)


def _inside(x, y, bounds):
    return bounds[0] <= x <= bounds[2] and bounds[1] <= y <= bounds[3]


class IntersectionController:
    """One policy instance per exact attempt, with explicit source readers."""

    def __init__(self, counterpart_reader, authority_reader):
        if not callable(counterpart_reader) or not callable(authority_reader):
            raise ValueError("original counterpart and authority readers required")
        self.counterpart_reader = counterpart_reader
        self.authority_reader = authority_reader
        self.full_stop_observed = False

    def __call__(self, role, actor, target, route, bounds, devices):
        if role not in {"ego", "counterpart"}:
            raise ValueError("unknown Native participant")
        frame = self.authority_reader()
        if not isinstance(frame, dict) or type(frame.get("native_frame")) is not int:
            raise ValueError("original authority frame required")
        if frame.get("control_context") != devices.get("control_context"):
            raise ValueError("Native authority context changed")
        if frame.get("ego_control_actor_id") != devices.get("ego_control_actor_id"):
            raise ValueError("Native authority actor changed")
        transform = actor.get_transform()
        location, rotation = transform.location, transform.rotation
        x, y = _number(location.x, "x"), _number(location.y, "y")
        velocity = actor.get_velocity()
        speed = hypot(_number(velocity.x, "vx"), _number(velocity.y, "vy"))
        points = route.get("native_waypoints")
        if not isinstance(points, list) or len(points) < 2:
            raise ValueError("source-surveyed route missing")
        # Select the next waypoint strictly ahead of the nearest sampled station.
        nearest = min(range(len(points)), key=lambda i:
                      hypot(x - points[i]["x"], y - points[i]["y"]))
        aim = points[min(nearest + 1, len(points) - 1)]
        desired = atan2(aim["y"] - y, aim["x"] - x)
        heading = _number(rotation.yaw, "yaw") * pi / 180
        error = atan2(sin(desired - heading), cos(desired - heading))
        steer = max(-0.65, min(0.65, error / 1.2))
        if role == "counterpart":
            return {"throttle": 0.3 if speed < target else 0.0,
                    "brake": 0.15 if speed > target + 0.6 else 0.0,
                    "steer": steer}
        context = devices["control_context"]
        if context == "signal_exception":
            if frame.get("signal_state") != devices.get("signal_state"):
                raise ValueError("Native controlling signal changed")
            go = frame.get("signal_permission") is True
        elif context == "officer_exception":
            if frame.get("officer_actor_visible") is not True:
                raise ValueError("original officer control observation missing")
            go = frame.get("officer_permission") is True
        elif context in {"stop_sign", "yield_sign"}:
            if frame.get("signal_controlling") is not False or frame.get("officer_controlling") is not False:
                raise ValueError("sign no longer independently controls")
            go = True
        else:
            raise ValueError("unsupported authority")
        counterpart = self.counterpart_reader()
        if (not isinstance(counterpart, dict) or
                counterpart.get("native_frame") != frame["native_frame"] or
                counterpart.get("unobligated") is not True):
            raise ValueError("same-frame original counterpart priority missing")
        ox, oy = _number(counterpart.get("x"), "counterpart x"), _number(counterpart.get("y"), "counterpart y")
        # Engineering hold distance protects test actors; it is not a legal
        # definition of an immediate hazard and is never emitted as one.
        occupied_or_close = _inside(ox, oy, bounds) or hypot(ox - x, oy - y) < 8
        before_entry = not _inside(x, y, bounds)
        entry_x = min(max(x, bounds[0]), bounds[2])
        entry_y = min(max(y, bounds[1]), bounds[3])
        distance_to_entry = hypot(x - entry_x, y - entry_y)
        if context == "stop_sign" and before_entry and distance_to_entry <= 5:
            if speed <= 0.05:
                self.full_stop_observed = True
            if not self.full_stop_observed:
                return {"throttle": 0.0, "brake": 0.75, "steer": steer}
        if not go or (before_entry and occupied_or_close):
            return {"throttle": 0.0, "brake": 0.7, "steer": steer}
        return {"throttle": 0.25 if speed < target else 0.0,
                "brake": 0.12 if speed > target + 0.5 else 0.0,
                "steer": steer}
