"""Derive one C158196 measurement row from an original Native tick.

The caller supplies actual CARLA body corners, velocity, snapshot and raycast.
This adapter does not infer legal right of way or fabricate a camera frame.
"""

from __future__ import annotations

import math

from shapely.geometry import Point, Polygon


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return float(value)


def _point(value: object, name: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{name} requires XY coordinates")
    return _number(value[0], name), _number(value[1], name)


def _body(value: object, name: str) -> Polygon:
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError(f"{name} requires four original body corners")
    polygon = Polygon([_point(p, name) for p in value])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError(f"{name} body geometry invalid")
    return polygon


def _axis(value: object, name: str) -> tuple[float, float]:
    axis = _point(value, name)
    if abs(math.hypot(*axis) - 1.0) > 1e-4:
        raise ValueError(f"{name} must be a unit direction")
    return axis


def _station(point: tuple[float, float], origin: tuple[float, float],
             axis: tuple[float, float]) -> float:
    return (point[0] - origin[0]) * axis[0] + (point[1] - origin[1]) * axis[1]


def derive(raw: dict, geometry: dict, *, expect_signal: bool = False) -> dict:
    frame = raw.get("frame")
    if isinstance(frame, bool) or not isinstance(frame, int) or frame < 0:
        raise ValueError("original snapshot frame missing")
    time = _number(raw.get("time_s"), "original snapshot time")
    ego = _body(raw.get("ego_body_xy_m"), "ego")
    through = _body(raw.get("through_body_xy_m"), "through")
    velocity = _point(raw.get("ego_velocity_xy_mps"), "ego velocity")
    center = _point(raw.get("through_center_xy_m"), "through center")
    if not through.covers(Point(center)):
        raise ValueError("through center differs from observed body")
    ray = raw.get("native_view_raycast")
    if not isinstance(ray, dict) or ray.get("source") != "native_raycast":
        raise ValueError("original Native visibility raycast required")
    if not isinstance(ray.get("occluded"), bool):
        raise ValueError("raycast occlusion state missing")
    start = _point(ray.get("origin_xy_m"), "ray origin")
    target = _point(ray.get("target_xy_m"), "ray target")
    if not ego.covers(Point(start)) or not through.covers(Point(target)):
        raise ValueError("raycast endpoint differs from observed bodies")
    if raw.get("yield_sign_readback") is not True:
        raise ValueError("original yield sign readback required")
    if raw.get("signal_controlling") is not expect_signal or raw.get("officer_controlling") is not False:
        raise ValueError("original controlling exception state differs")
    ego_origin = _point(geometry.get("ego_route_origin_xy_m"), "ego route origin")
    ego_axis = _axis(geometry.get("ego_route_axis_xy"), "ego route axis")
    through_origin = _point(geometry.get("through_route_origin_xy_m"), "through route origin")
    through_axis = _axis(geometry.get("through_route_axis_xy"), "through route axis")
    region = _body(geometry.get("intersection_polygon_xy_m"), "intersection")
    front = max(_station((x, y), ego_origin, ego_axis) for x, y in ego.exterior.coords[:-1])
    return {"frame": frame, "time_s": time,
            "ego_front_station_m": front, "ego_speed_mps": math.hypot(*velocity),
            "through_center_station_m": _station(center, through_origin, through_axis),
            "view_clear": not ray["occluded"],
            "through_occupied": through.intersects(region),
            "ego_within_intersection": ego.intersects(region)}
