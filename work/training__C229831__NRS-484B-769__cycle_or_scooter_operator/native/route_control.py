"""Readback-driven prospective bicycle route controller for the authored turn."""
from __future__ import annotations

from math import hypot, isfinite

from road import lane_center_route


def command(bicycle, *, prior_index, speed_mps=2.8, lookahead_m=2.0):
    if bicycle.type_id != "vehicle.bh.crossbike":
        raise ValueError("Selected bicycle actor required")
    if type(prior_index) is not int or prior_index < 0:
        raise ValueError("Prior route index required")
    if not all(isfinite(value) for value in (speed_mps, lookahead_m)) or not (0 < speed_mps <= 6 and 0.5 <= lookahead_m <= 6):
        raise ValueError("Invalid prospective route controls")
    points = lane_center_route()
    pose = bicycle.get_transform()
    x, y = float(pose.location.x), float(pose.location.y)
    if not isfinite(x) or not isfinite(y):
        raise ValueError("Original bicycle pose missing")
    nearest = min(range(prior_index, min(len(points), prior_index + 60)),
                  key=lambda index: hypot(points[index][0] - x,
                                          points[index][1] - y))
    cross_track = hypot(points[nearest][0] - x, points[nearest][1] - y)
    if cross_track > 3.0:
        raise ValueError("Bicycle left authored route corridor")
    target = nearest
    while target + 1 < len(points) and hypot(points[target][0] - x,
                                             points[target][1] - y) < lookahead_m:
        target += 1
    dx, dy = points[target][0] - x, points[target][1] - y
    norm = hypot(dx, dy)
    finished = target == len(points) - 1 and norm <= 0.3
    if norm < 1e-8 or finished:
        velocity = (0.0, 0.0)
    else:
        velocity = (speed_mps * dx / norm, speed_mps * dy / norm)
    return {"route_index": nearest, "target_index": target,
            "requested_velocity_xy_mps": list(velocity),
            "cross_track_error_m": cross_track, "route_end_reached": finished,
            "bicycle_actor_id": bicycle.id}


def apply(bicycle, carla, *, prior_index, speed_mps=2.8, lookahead_m=2.0):
    row = command(bicycle, prior_index=prior_index, speed_mps=speed_mps,
                  lookahead_m=lookahead_m)
    x, y = row["requested_velocity_xy_mps"]
    bicycle.set_target_velocity(carla.Vector3D(x=x, y=y, z=0))
    return row
