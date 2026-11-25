"""Bounded Native vehicle controls for the caravan and entering participant.

The clearance parameter is a control safety setting, not a legal danger cutoff.
"""
import math


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Finite " + name + " required")
    return float(value)


def command(position_xy, yaw_deg, speed_mps, waypoint_xy, *, target_speed_mps,
            nearest_body_clearance_m=None, control_clearance_m=3.0):
    x, y = (_finite(value, "vehicle position") for value in position_xy)
    tx, ty = (_finite(value, "waypoint") for value in waypoint_xy)
    yaw = math.radians(_finite(yaw_deg, "Native heading"))
    speed = _finite(speed_mps, "Native speed")
    target_speed = _finite(target_speed_mps, "target speed")
    if speed < 0 or target_speed < 0 or target_speed > 15:
        raise ValueError("Unsafe speed input")
    clearance = None if nearest_body_clearance_m is None else _finite(nearest_body_clearance_m, "body clearance")
    if control_clearance_m <= 0:
        raise ValueError("Positive control clearance required")
    dx, dy = tx - x, ty - y
    distance = math.hypot(dx, dy)
    angle = math.atan2(dy, dx) if distance > 1e-6 else yaw
    error = math.atan2(math.sin(angle - yaw), math.cos(angle - yaw))
    steer = max(-.6, min(.6, 1.2 * error))
    if clearance is not None and clearance < control_clearance_m:
        return {"throttle": 0.0, "brake": 1.0, "steer": 0.0, "reverse": False,
                "reason": "engineering_body_clearance_guard"}
    if distance <= .75 or (abs(error) > .8 and speed > 2):
        return {"throttle": 0.0, "brake": min(1.0, max(.25, speed / 6)),
                "steer": steer, "reverse": False, "reason": "waypoint_or_heading_brake"}
    speed_error = target_speed - speed
    return {"throttle": max(0.0, min(.45, speed_error * .18)),
            "brake": max(0.0, min(.8, -speed_error * .25)),
            "steer": steer, "reverse": False, "reason": "waypoint_tracking"}


def apply(actor, carla, values):
    required = {"throttle", "brake", "steer", "reverse", "reason"}
    if set(values) != required or values["reverse"] is not False:
        raise ValueError("Incomplete forward Native vehicle control")
    control = carla.VehicleControl(throttle=values["throttle"], brake=values["brake"],
                                   steer=values["steer"], reverse=False)
    actor.apply_control(control)
    return control
