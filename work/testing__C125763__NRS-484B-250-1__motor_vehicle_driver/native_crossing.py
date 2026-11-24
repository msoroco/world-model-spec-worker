"""Lazy Native body sampler and vehicle control for the C125763 pair.

Placement/routes must be obtained from a separately reviewed real map. A requested
response mode is never reported as realized crossing behavior without saved audit.
"""
from __future__ import annotations

import math


def body_row(snapshot, actor):
    if not actor.is_alive:
        raise ValueError("original Native actor is dead")
    frame, time_s = snapshot.frame, snapshot.timestamp.elapsed_seconds
    if type(frame) is not int or type(time_s) not in (int, float) or not math.isfinite(time_s):
        raise ValueError("invalid original Native frame/time")
    vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
    if len(vertices) < 4:
        raise ValueError("original Native bounding box missing")
    points = set()
    for p in vertices:
        if not all(math.isfinite(v) for v in (p.x, p.y, p.z)):
            raise ValueError("nonfinite original Native body vertex")
        points.add((float(p.x), float(p.y)))
    if len(points) < 4:
        raise ValueError("degenerate original Native body footprint")
    points = sorted(points)
    def cross(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    lower, upper = [], []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1]+upper[:-1]
    if len(hull) < 3:
        raise ValueError("degenerate original Native body hull")
    return {"frame": frame, "time_s": time_s, "actor_id": actor.id,
            "body_vertices_xy_m": [list(p) for p in hull]}


def capture_pair(snapshot, actors, streams):
    """Write one original frame per actor, synchronized to one completed world tick."""
    import json
    if set(actors) != {"ego", "other"} or set(streams) != {"ego", "other"} or \
            actors["ego"].id == actors["other"].id:
        raise ValueError("two distinct original Native actors and streams required")
    rows = {name: body_row(snapshot, actors[name]) for name in ("ego", "other")}
    for name in ("ego", "other"):
        streams[name].write(json.dumps(rows[name], allow_nan=False)+"\n")
    return rows


def control_step(carla, actor, route, *, hold, target_speed_mps=5.0):
    """Hold or follow a reviewed route with bounded actuation; never teleport."""
    if not isinstance(hold, bool):
        raise ValueError("explicit response control state required")
    if hold:
        actor.apply_control(carla.VehicleControl(throttle=0.0, brake=1.0, steer=0.0))
        return "held"
    if len(route) < 2 or any(len(point) != 3 or not all(math.isfinite(v) for v in point)
                             for point in route):
        raise ValueError("reviewed route requires finite 3D points")
    if not math.isfinite(target_speed_mps) or not 0 < target_speed_mps <= 20:
        raise ValueError("bounded engineering target speed required")
    location = actor.get_location()
    velocity = actor.get_velocity()
    speed = math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
    target = min(route[1:], key=lambda p: math.hypot(p[0]-location.x, p[1]-location.y))
    desired = math.atan2(target[1]-location.y, target[0]-location.x)
    current = math.radians(actor.get_transform().rotation.yaw)
    error = math.atan2(math.sin(desired-current), math.cos(desired-current))
    steer = max(-1.0, min(1.0, error/.5))
    throttle = max(0.0, min(.55, .25*(target_speed_mps-speed)))
    brake = max(0.0, min(.8, .2*(speed-target_speed_mps)))
    actor.apply_control(carla.VehicleControl(throttle=throttle, brake=brake, steer=steer))
    return "released"
