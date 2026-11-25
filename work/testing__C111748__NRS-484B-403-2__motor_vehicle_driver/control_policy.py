"""Case-bound, source-gated U-turn control policy for a local CARLA adapter.

This module plans controls from original-frame observations. The local adapter
applies the returned command to the live ego and records the actual motion.
"""
from __future__ import annotations
import math

BASE = "testing__C111748__NRS-484B-403-2__motor_vehicle_driver__"
CASES = {"prohibited_obey": (True, False),
         "prohibited_attempt": (True, True),
         "neutral_device_turn": (False, True)}


class PolicyError(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise PolicyError(reason)


def command(case_id: str, site: dict, ego: dict, device_readback: dict,
            *, first_visible_frame: int | None, original_frame: int,
            controller_variant: str = 'primary') -> dict:
    """Plan one command; no intended action is accepted as observed evidence."""
    suffix = case_id.removeprefix(BASE)
    require(suffix in CASES and case_id == BASE + suffix, "unknown exact case")
    expected_display, should_turn = CASES[suffix]
    require(controller_variant in ('primary', 'fallback1'), 'unknown controller variant')
    device = site.get("device", {})
    require(device.get("prohibits_u_turn") is expected_display, "reviewed display differs from case")
    require(device_readback.get("device_id") == device.get("device_id"), "live device identity mismatch")
    require(device_readback.get("prohibits_u_turn") is expected_display, "live display differs from case")
    require(ego.get("approach_id") == device.get("governed_approach"), "ego is not on governed approach")
    require(isinstance(original_frame, int) and not isinstance(original_frame, bool), "original frame missing")
    route = site.get("u_turn_route", [])
    require(len(route) >= 3, "U-turn route missing")
    require(route[0].get("road_id") == route[-1].get("road_id") and
            route[0].get("lane_id") != route[-1].get("lane_id"), "opposite-lane route missing")
    for point in route:
        require(all(isinstance(point.get(k), (int, float)) and math.isfinite(point[k]) for k in ("x", "y")),
                "route waypoint coordinates missing")
    for key in ("x", "y", "yaw_deg"):
        require(isinstance(ego.get(key), (int, float)) and math.isfinite(ego[key]), "ego pose missing")
    observed = (device_readback.get("visible_to_ego") is True and
                first_visible_frame is not None and first_visible_frame < original_frame)
    if not observed or not should_turn:
        return {"throttle": 0.0, "brake": 1.0, "steer": 0.0,
                "phase": "hold_before_observation" if not observed else "obey_no_turn",
                "requested_turn": False}
    closest = min(range(len(route)), key=lambda i: (route[i]["x"] - ego["x"]) ** 2 +
                  (route[i]["y"] - ego["y"]) ** 2)
    target = route[min(closest + 1, len(route) - 1)]
    dx, dy = target["x"] - ego["x"], target["y"] - ego["y"]
    if closest == len(route) - 1 and dx * dx + dy * dy < 4.0:
        return {"throttle": 0.0, "brake": 1.0, "steer": 0.0,
                "phase": "hold_destination", "requested_turn": False}
    require(dx * dx + dy * dy > 1e-9, "zero-length route segment")
    desired = math.degrees(math.atan2(dy, dx))
    error = (desired - ego["yaw_deg"] + 180.0) % 360.0 - 180.0
    limit = 0.45 if controller_variant == 'fallback1' else 0.7
    steer = max(-limit, min(limit, error / 90.0))
    return {"throttle": 0.18 if controller_variant == 'fallback1' else 0.25,
            "brake": 0.0, "steer": steer,
            "phase": "route_turn", "requested_turn": True}
