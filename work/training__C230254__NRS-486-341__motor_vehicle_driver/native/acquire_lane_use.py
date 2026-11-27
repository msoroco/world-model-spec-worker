"""Sample original CARLA actor and map geometry for the saved lane-use finalizer.

The caller invokes ``sample`` after each synchronous world tick and writes its
return value once to lane-use-source.jsonl. This module never infers a legal
classification or a full-use threshold from a blueprint name or a distance.
"""

from __future__ import annotations

import json
import math
from pathlib import Path


def _xy(point):
    return float(point.x), float(point.y)


def _rotate(x, y, yaw_deg):
    angle = math.radians(yaw_deg)
    return x * math.cos(angle) - y * math.sin(angle), x * math.sin(angle) + y * math.cos(angle)


def actor_footprint(actor):
    """Project all four original CARLA bounding-box corners to world XY."""
    transform = actor.get_transform()
    box = actor.bounding_box
    extent = box.extent
    center = box.location
    if min(extent.x, extent.y) <= 0:
        raise ValueError("actor bounding box has no road-plane area")
    points = []
    for dx, dy in ((-extent.x, -extent.y), (extent.x, -extent.y),
                   (extent.x, extent.y), (-extent.x, extent.y)):
        bx, by = _rotate(dx, dy, box.rotation.yaw)
        ax, ay = _rotate(center.x + bx, center.y + by, transform.rotation.yaw)
        points.append([transform.location.x + ax, transform.location.y + ay])
    return points


def lane_polygon(world_map, motorcycle, *, half_length_m=15.0):
    """Take a local lane strip from the motorcycle's original mapped waypoint.

    The finite strip is a measurement window, not a legal definition of a lane.
    Record the waypoint identifiers and width so saved processing can review it.
    """
    waypoint = world_map.get_waypoint(motorcycle.get_transform().location,
                                      project_to_road=False)
    if waypoint is None or waypoint.lane_width <= 0:
        raise ValueError("protected actor has no source mapped traffic lane")
    origin = waypoint.transform.location
    forward = waypoint.transform.get_forward_vector()
    right = waypoint.transform.get_right_vector()
    norm_f = math.hypot(forward.x, forward.y)
    norm_r = math.hypot(right.x, right.y)
    if min(norm_f, norm_r) <= 0:
        raise ValueError("mapped lane basis is invalid")
    fx, fy = forward.x / norm_f, forward.y / norm_f
    rx, ry = right.x / norm_r, right.y / norm_r
    half_width = waypoint.lane_width / 2
    points = []
    for along, across in ((-half_length_m, -half_width),
                          (half_length_m, -half_width),
                          (half_length_m, half_width),
                          (-half_length_m, half_width)):
        points.append([origin.x + along * fx + across * rx,
                       origin.y + along * fy + across * ry])
    return points, {
        "road_id": waypoint.road_id,
        "section_id": waypoint.section_id,
        "lane_id": waypoint.lane_id,
        "lane_width_m": waypoint.lane_width,
        "waypoint_x_m": origin.x,
        "waypoint_y_m": origin.y,
        "strip_half_length_m": half_length_m,
    }


def sample(world_map, ego, motorcycle, *, frame, time_s, source_refs,
           native_frame=None):
    """Return one source-shaped row after a synchronized Native tick."""
    if ego.id == motorcycle.id:
        raise ValueError("subject and protected actor must be distinct")
    if not isinstance(source_refs, dict) or not all(source_refs.get(k) for k in
                                                     ("actor_trace", "actor_bounds", "lane_map")):
        raise ValueError("original Native source references are missing")
    lane, waypoint = lane_polygon(world_map, motorcycle)
    return {
        "frame": frame,
        "video_frame": frame,
        "native_frame": native_frame if native_frame is not None else frame,
        "time_s": time_s,
        "source_kind": "original_native_actor_and_map_geometry",
        "ego_actor_id": ego.id,
        "motorcycle_actor_id": motorcycle.id,
        "lane_polygon": lane,
        "motorcycle_footprint": actor_footprint(motorcycle),
        "ego_footprint": actor_footprint(ego),
        "mapped_lane": waypoint,
        "source_refs": source_refs,
    }


def append_source(path, row):
    """Append a newly sampled row; existing original rows remain immutable."""
    with Path(path).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, allow_nan=False, sort_keys=True) + "\n")
