"""Original map turn plan and per-tick commanded/read-back turn intent."""

from __future__ import annotations

from hashlib import sha256
import json
from math import atan2, degrees, isfinite
from pathlib import Path


def _heading(waypoint):
    forward = waypoint.transform.get_forward_vector()
    return atan2(float(forward.y), float(forward.x))


def _angle(a, b):
    from math import pi
    return (b - a + pi) % (2 * pi) - pi


def select_turn_plan(route, *, step_m):
    """Find a downstream connected road turn; reject a straight continuation."""
    if len(route) < 2 or not isfinite(step_m) or step_m <= 0:
        raise ValueError("Original route and positive turn survey step required")
    origin = route[-1]
    start = _heading(origin)
    frontier = [(origin, 0)]
    seen = set()
    while frontier:
        waypoint, depth = frontier.pop(0)
        identity = (int(waypoint.road_id), int(waypoint.lane_id), round(float(waypoint.s), 1))
        if identity in seen or depth > 100:
            continue
        seen.add(identity)
        change = degrees(_angle(start, _heading(waypoint)))
        if 25 <= abs(change) <= 155 and int(waypoint.road_id) != int(origin.road_id):
            location = waypoint.transform.location
            return {"requested_movement": "turn", "direction": "left" if change > 0 else "right",
                    "origin_road_id": int(origin.road_id), "origin_lane_id": int(origin.lane_id),
                    "destination_road_id": int(waypoint.road_id),
                    "destination_lane_id": int(waypoint.lane_id),
                    "destination_xyz_m": [float(location.x), float(location.y), float(location.z)],
                    "heading_change_deg": change, "map_geometry_observed": True,
                    "lawful_turn_premise": None}
        if depth < 100:
            frontier.extend((candidate, depth + 1) for candidate in waypoint.next(step_m))
    raise ValueError("No downstream connected turning movement in selected Native route")


def save_turn_plan(path, plan):
    if plan.get("lawful_turn_premise") is not None or plan.get("direction") not in ("left", "right"):
        raise ValueError("Turn plan must leave independent legal permission open")
    target = Path(path)
    target.write_text(json.dumps(plan, indent=2, allow_nan=False) + "\n")
    return sha256(target.read_bytes()).hexdigest()


def turn_intent_row(frame, time_s, plan_sha256, ego, command, direction):
    """Record operator command and Native indicator readback as separate facts."""
    if direction not in ("left", "right") or not isinstance(command, dict):
        raise ValueError("Missing source-recorded turn command")
    transform = ego.get_transform()
    location = transform.location
    return {"frame": int(frame), "time_s": float(time_s), "turn_plan_sha256": plan_sha256,
            "requested_direction": direction, "command": command,
            "indicator_readback": str(ego.get_light_state()),
            "ego_xyz_m": [float(location.x), float(location.y), float(location.z)],
            "ego_heading_deg": float(transform.rotation.yaw),
            "lawful_turn_premise": None}
