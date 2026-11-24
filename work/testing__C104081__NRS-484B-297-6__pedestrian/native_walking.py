"""Measured 20 Hz Native pedestrian route controller for an exact bypass case.

The command requests movement; only original pose readback establishes movement.
This module imports no CARLA package and leaves legal due care unresolved.
"""
from __future__ import annotations

import math
import hashlib
import json
from pathlib import Path

FPS = 20
DT = 1 / FPS


def world_route(local_route, transform):
    """Transform the checked local path using the source-bound Native survey."""
    if not isinstance(transform, dict) or not all(key in transform for key in
            ("x", "y", "yaw_degrees")):
        raise ValueError("surveyed local-to-world transform required")
    ox, oy, angle = float(transform["x"]), float(transform["y"]), math.radians(float(transform["yaw_degrees"]))
    if not all(map(math.isfinite, (ox, oy, angle))):
        raise ValueError("finite surveyed transform required")
    cosine, sine = math.cos(angle), math.sin(angle)
    return [(ox + x * cosine - y * sine, oy + x * sine + y * cosine)
            for x, y in map(_xy, local_route)]


def run_constructed(world, walker, carla, constructed: dict, survey_path: Path,
                    case_id: str, *, speed_m_s=1.4, on_sample=None):
    """Bind the walking request to the exact constructed case and survey bytes."""
    raw = Path(survey_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != constructed.get("survey_sha256"):
        raise ValueError("constructed walking route has stale survey")
    survey = json.loads(raw)
    if (constructed.get("case_id") != case_id or
            constructed.get("site_map_id") != survey.get("map_id") or
            world.get_map().name != survey.get("map_id")):
        raise ValueError("constructed walking route case/map mismatch")
    route = world_route(constructed.get("route_local_xy_m"), survey.get("local_to_world"))
    return run_walking_route(world, walker, carla, route, speed_m_s=speed_m_s,
                             on_sample=on_sample)


def _xy(value):
    x, y = float(value[0]), float(value[1])
    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError("finite route coordinates required")
    return x, y


def run_walking_route(world, walker, carla, route, *, speed_m_s=1.4,
                      frames=900, waypoint_tolerance_m=.25, on_sample=None):
    """Walk the surveyed-world route, rejecting stalled, stale or off-route motion.

    The caller owns world restoration and actor destruction. `route` must already
    be transformed to observed Native world coordinates from the site survey.
    """
    points = tuple(_xy(point) for point in route)
    if len(points) < 2 or any(math.dist(a, b) < .2 for a, b in zip(points, points[1:])):
        raise ValueError("nondegenerate surveyed walking route required")
    if not 0 < speed_m_s <= 3 or frames != 900 or not 0 < waypoint_tolerance_m <= .5:
        raise ValueError("invalid 20 Hz walking controller contract")
    pose = walker.get_transform().location
    if math.dist((float(pose.x), float(pose.y)), points[0]) > .5:
        raise ValueError("walker does not start at surveyed route")
    target_index = 1
    prior_frame = None
    prior_time = None
    initial_x, initial_y = float(pose.x), float(pose.y)
    samples = []
    completed = False
    try:
        for index in range(frames):
            pose = walker.get_transform().location
            x, y = float(pose.x), float(pose.y)
            if not all(map(math.isfinite, (x, y))):
                raise ValueError("nonfinite original walker position")
            if not completed and math.dist((x, y), points[target_index]) <= waypoint_tolerance_m:
                target_index += 1
                if target_index == len(points):
                    completed = True
            if completed:
                direction = carla.Vector3D(x=0.0, y=0.0, z=0.0)
                requested_speed = 0.0
            else:
                tx, ty = points[target_index]
                distance = math.hypot(tx - x, ty - y)
                direction = carla.Vector3D(x=(tx - x) / distance,
                                           y=(ty - y) / distance, z=0.0)
                requested_speed = speed_m_s
            walker.apply_control(carla.WalkerControl(direction=direction,
                                                      speed=requested_speed))
            frame = int(world.tick())
            snapshot = world.get_snapshot()
            time_s = float(snapshot.timestamp.elapsed_seconds)
            if frame != int(snapshot.frame) or not math.isfinite(time_s):
                raise ValueError("Native walker frame/time mismatch")
            if prior_frame is not None and (frame != prior_frame + 1 or
                    abs(time_s - prior_time - DT) > .005):
                raise ValueError("Native walker 20 Hz continuity failure")
            observed = walker.get_transform().location
            ox, oy = float(observed.x), float(observed.y)
            if not all(map(math.isfinite, (ox, oy))):
                raise ValueError("nonfinite original walker readback")
            # World-to-polyline distance; position is never replaced by a target.
            distance_to_route = min(_segment_distance((ox, oy), a, b)
                                    for a, b in zip(points, points[1:]))
            if distance_to_route > .8:
                raise ValueError("walker departed surveyed bypass route")
            if index >= FPS and math.dist((ox, oy), (initial_x, initial_y)) < .5:
                raise ValueError("walker failed measured-motion check")
            sample = {"frame": frame, "time_s": time_s,
                            "position_world_xy_m": [ox, oy],
                            "requested_speed_m_s": requested_speed,
                            "route_waypoint_index": min(target_index, len(points) - 1),
                            "route_completed": completed}
            if on_sample is not None:
                on_sample(sample)
            samples.append(sample)
            prior_frame, prior_time = frame, time_s
        if not completed:
            raise ValueError("walker did not complete surveyed bypass route")
        return samples
    finally:
        walker.apply_control(carla.WalkerControl(
            direction=carla.Vector3D(x=0.0, y=0.0, z=0.0), speed=0.0))


def _segment_distance(point, a, b):
    vx, vy = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((point[0] - a[0]) * vx + (point[1] - a[1]) * vy) /
                     (vx * vx + vy * vy)))
    return math.hypot(point[0] - a[0] - t * vx, point[1] - a[1] - t * vy)
