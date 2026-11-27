"""Build saved arm measurements from original rider bones and map geometry.

This source join does not infer pixel visibility, signaling intent or legal result.
"""
from __future__ import annotations

from math import hypot, isfinite, radians


CAMERAS = {"overview", "approach", "reference_corner", "driver_reference"}


def _point_inside(point, polygon):
    x, y = point
    inside = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        ax, ay = a
        bx, by = b
        if (ay > y) != (by > y):
            cross_x = ax + (y - ay) * (bx - ax) / (by - ay)
            if x < cross_x:
                inside = not inside
    return inside


def _route_distance(point, route):
    px, py = point
    best = float("inf")
    for a, b in zip(route, route[1:]):
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) /
                              (dx * dx + dy * dy)))
        best = min(best, hypot(px - ax - t * dx, py - ay - t * dy))
    return best


def _finite_polygon(points, minimum):
    return (isinstance(points, list) and len(points) >= minimum and all(
        isinstance(point, list) and len(point) == 2 and all(
            type(value) in (int, float) and isfinite(value) for value in point)
        for point in points))


def make_rows(rig_rows, camera_rows, context):
    """Require 600 original joins and derive roadway/route booleans from geometry."""
    if len(rig_rows) != 600 or len(camera_rows) != 600:
        raise ValueError("600 original Native and camera frames required")
    if context.get("source_kind") != "original_native_map_and_capture":
        raise ValueError("Original map and capture context required")
    polygon = context.get("roadway_polygon_xy_m")
    route = context.get("right_turn_route_xy_m")
    if not _finite_polygon(polygon, 3) or not _finite_polygon(route, 2):
        raise ValueError("Sourced roadway polygon and turn route required")
    if any(a == b for a, b in zip(route, route[1:])):
        raise ValueError("Zero-length turn route segment")
    if context.get("roadway_polygon_source_id") is None or context.get("right_turn_route_source_id") is None:
        raise ValueError("Original roadway and route source IDs required")
    if context.get("rider_actor_id") == context.get("bicycle_actor_id"):
        raise ValueError("Rider and bicycle identities must differ")
    output = []
    previous_native_frame = None
    for frame, (rig, camera) in enumerate(zip(rig_rows, camera_rows)):
        if rig.get("frame") != frame or camera.get("frame") != frame:
            raise ValueError("Original frame identity differs")
        native_frame = rig.get("native_frame")
        if (type(native_frame) is not int or native_frame < 0 or
                camera.get("native_frame") != native_frame or
                (previous_native_frame is not None and native_frame <= previous_native_frame)):
            raise ValueError("Original Native and camera frame join differs")
        previous_native_frame = native_frame
        if abs(float(camera.get("time_s", -1)) - frame / 20) > 1e-8:
            raise ValueError("Original camera time join differs")
        pixels = camera.get("pixel_source_ids")
        if (set(camera.get("camera_names", [])) != CAMERAS or
                not isinstance(pixels, dict) or set(pixels) != CAMERAS or
                any(pixels[name] != f"{name}.mkv#frame={frame}"
                    for name in CAMERAS)):
            raise ValueError("Four original camera pixel sources required")
        if rig.get("rider_actor_id") != context["rider_actor_id"] or rig.get("bicycle_actor_id") != context["bicycle_actor_id"]:
            raise ValueError("Original rider or bicycle identity differs")
        center = rig.get("bicycle_center_xyz_m")
        if not isinstance(center, list) or len(center) != 3 or not all(
            type(value) in (int, float) and isfinite(value) for value in center):
            raise ValueError("Original bicycle position missing")
        yaw = float(rig.get("bicycle_yaw_deg", float("nan")))
        if not isfinite(yaw):
            raise ValueError("Original bicycle heading missing")
        body = rig.get("bicycle_body_vertices_xyz_m")
        if not isinstance(body, list) or len(body) < 4 or not all(
            isinstance(vertex, list) and len(vertex) == 3 and all(
                type(value) in (int, float) and isfinite(value) for value in vertex)
            for vertex in body):
            raise ValueError("Original full bicycle body vertices missing")
        bones = rig.get("bone_world_xyz_m", {})
        def xy(name):
            value = bones.get(name)
            if not isinstance(value, list) or len(value) != 3 or not all(
                type(v) in (int, float) and isfinite(v) for v in value):
                raise ValueError(f"Original world bone missing: {name}")
            return value[:2]
        point = center[:2]
        output.append({
            "frame": frame, "time_s": frame / 20,
            "operator_id": str(context["rider_actor_id"]),
            "roadway_occupied": all(_point_inside(vertex[:2], polygon)
                                    for vertex in body),
            "on_right_turn_route": _route_distance(point, route) <= 1.0,
            "machine_centre_xy_m": point,
            "machine_heading_rad": radians(yaw),
            "right_shoulder_xy_m": xy("crl_shoulder__R"),
            "right_elbow_xy_m": xy("crl_foreArm__R"),
            "right_wrist_xy_m": xy("crl_hand__R"),
        })
    return output
