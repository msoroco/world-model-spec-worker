"""Original-frame Native body capture for the selected median junction.

The caller must join all four camera callbacks to snapshot.frame before this
row is recorded. FrameMap owns the adjacent video_frames.jsonl identity.
"""
import json
import math


def _number(value, label):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("Nonfinite Native " + label)
    return value


def _actor(actor, world_map):
    pose = actor.get_transform()
    vertices = actor.bounding_box.get_world_vertices(pose)
    if len(vertices) < 4:
        raise ValueError("Complete Native body vertices required")
    waypoint = world_map.get_waypoint(actor.get_location(), project_to_road=False)
    if waypoint is None:
        raise ValueError("No Native driving waypoint at original frame")
    velocity = actor.get_velocity()
    return {
        "actor_id": actor.id,
        "position_xy_m": [_number(pose.location.x, "x"), _number(pose.location.y, "y")],
        "body_vertices_xy_m": [[_number(v.x, "body x"), _number(v.y, "body y")]
                               for v in vertices],
        "heading_deg": _number(pose.rotation.yaw, "yaw"),
        "velocity_xyz_mps": [_number(velocity.x, "velocity x"),
                             _number(velocity.y, "velocity y"),
                             _number(velocity.z, "velocity z")],
        "native_road_id": waypoint.road_id,
        "native_lane_id": waypoint.lane_id,
        "native_junction_id": waypoint.get_junction().id if waypoint.is_junction else None,
        "body_source": "actor.bounding_box.get_world_vertices",
    }


def record_crossing_sample(frame_map, stream, snapshot, world_map, ego, other, plan):
    """Write one complete source sample after camera frames match this tick."""
    if plan.get("physical_acceptance_claimed") is not False or not plan.get("native_junction_id"):
        raise ValueError("Checked Native pair plan required")
    time_s = _number(snapshot.timestamp.elapsed_seconds, "time")
    ego_row, other_row = _actor(ego, world_map), _actor(other, world_map)
    if ego_row["actor_id"] == other_row["actor_id"]:
        raise ValueError("Distinct Native actor identities required")
    mapped = frame_map.append(snapshot.frame, time_s)
    row = {"frame": snapshot.frame, "time_s": time_s, "ego": ego_row,
           "other": other_row, "ego_vertices_m": ego_row["body_vertices_xy_m"]}
    stream.write(json.dumps(row, allow_nan=False) + "\n")
    return mapped, row


def road_geometry(site, plan):
    """Bind reviewed site claims to the checked Native approach geometry."""
    if site.get("device_inventory_source") in (None, ""):
        raise ValueError("Reviewed device inventory source required")
    review = site.get("device_review")
    if not isinstance(review, dict) or review.get("official_device_controls_crossing") is not False:
        raise ValueError("Reviewed uncontrolled crossing device result required")
    approaches = plan["approaches"]
    return {
        "intersection_id": plan["native_junction_id"],
        "intersection_polygon_xy_m": plan["crossing_polygon_xy_m"],
        "intersection_polygon_source": plan["crossing_polygon_source"],
        "ego_highway_id": plan["ego_highway_id"],
        "other_highway_id": plan["other_highway_id"],
        "device_inventory_source": site["device_inventory_source"],
        "official_device_controls_crossing": False,
        "device_review": review,
        "approach_geometry_source": plan["approach_geometry_source"],
        "ego_approach_origin_xy_m": approaches["ego"]["start_xy_m"],
        "other_approach_origin_xy_m": approaches["other"]["start_xy_m"],
        "ego_approach_heading_deg": approaches["ego"]["heading_deg"],
        "other_approach_heading_deg": approaches["other"]["heading_deg"],
        "physical_acceptance_claimed": False,
    }
