"""Find and verify a two-way, connected left-turn interaction on a live map.

This produces a candidate request from Native map readback. A local owner must
still inspect original road, actor paths, camera pixels and physical completion.
"""
from __future__ import annotations

import hashlib
import math


def xy(location):
    return (float(location.x), float(location.y))


def direction(waypoint):
    angle = math.radians(float(waypoint.transform.rotation.yaw))
    return (math.cos(angle), math.sin(angle))


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _inbound(waypoint):
    """Return the first junction reached from an upstream driving waypoint."""
    if waypoint.is_junction:
        return None
    upcoming = [item for item in waypoint.next(3.0) if item.is_junction]
    return upcoming[0].get_junction() if upcoming else None


def _retreat(waypoint, distance):
    options = waypoint.previous(distance)
    for candidate in options:
        if not candidate.is_junction and candidate.road_id == waypoint.road_id and candidate.lane_id == waypoint.lane_id:
            return candidate
    return None


def _left_exit(junction, inbound, driving_lane_type):
    incoming = direction(inbound)
    for start, end in junction.get_waypoints(driving_lane_type):
        same_entry = (start.road_id == inbound.road_id and
                      start.lane_id == inbound.lane_id)
        nearby_entry = (math.dist(xy(start.transform.location),
                                  xy(inbound.transform.location)) < 6 and
                        dot(direction(start), incoming) > 0.8)
        if not (same_entry or nearby_entry):
            continue
        outgoing = direction(end)
        if cross(incoming, outgoing) > 0.7 and abs(dot(incoming, outgoing)) < 0.7:
            return end
    return None


def survey(native_map, driving_lane_type):
    """Select only a connected intersection with two opposing inbound lanes.

    The two opposing start waypoints are 100 and 140 m upstream of one entry.
    If the map cannot supply that geometry the function rejects the scene rather
    than substituting a point off road or silently changing the comparison.
    """
    road_text = native_map.to_opendrive()
    if not isinstance(road_text, str) or not road_text:
        raise ValueError("Original Native OpenDRIVE readback absent")
    entries = []
    for waypoint in native_map.generate_waypoints(3.0):
        if waypoint.lane_type != driving_lane_type:
            continue
        junction = _inbound(waypoint)
        if junction is not None:
            entries.append((waypoint, junction))
    for ego, junction in entries:
        exit_waypoint = _left_exit(junction, ego, driving_lane_type)
        ego_start = _retreat(ego, 25.0)
        if exit_waypoint is None or ego_start is None:
            continue
        ego_dir = direction(ego)
        for opposite, other_junction in entries:
            if other_junction.id != junction.id or opposite.id == ego.id or \
                    dot(ego_dir, direction(opposite)) > -0.9:
                continue
            initial = _retreat(opposite, 100.0)
            subsequent = _retreat(opposite, 140.0)
            if initial is None or subsequent is None:
                continue
            center = xy(junction.bounding_box.location)
            extent = junction.bounding_box.extent
            if min(extent.x, extent.y) < 2:
                continue
            start_xy = xy(ego.transform.location)
            end_xy = xy(exit_waypoint.transform.location)
            if math.dist(start_xy, end_xy) < 3:
                continue
            polygon = [[center[0] - extent.x, center[1] - extent.y],
                       [center[0] + extent.x, center[1] - extent.y],
                       [center[0] + extent.x, center[1] + extent.y],
                       [center[0] - extent.x, center[1] + extent.y]]
            record = {"format": "c329654-original-map-survey-v1",
                      "source_sha256": hashlib.sha256(road_text.encode()).hexdigest(),
                      "junction_id": junction.id,
                      "ego_road_lane": [ego.road_id, ego.lane_id],
                      "opposing_road_lane": [opposite.road_id, opposite.lane_id],
                      "conflict_xy_m": list(center),
                      "intersection_polygon_xy_m": polygon,
                      "ego_approach_direction_xy": list(ego_dir),
                      "opposing_approach_direction_xy": list(direction(opposite)),
                      "turn_start_xy_m": list(start_xy), "turn_end_xy_m": list(end_xy),
                      "initial_opponent_upstream_m": 100.0,
                      "subsequent_opponent_upstream_m": 140.0,
                      "physical_geometry_review_required": True}
            return record, {"ego_start": ego_start, "initial_start": initial,
                            "subsequent_start": subsequent, "turn_exit": exit_waypoint}
    raise ValueError("No connected, opposing, left-turn junction with 140 m inbound source")
