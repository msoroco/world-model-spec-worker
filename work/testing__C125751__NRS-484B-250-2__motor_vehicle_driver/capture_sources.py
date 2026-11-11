"""Original-frame Native source rows for the two C125751 signal cases.

Call record_frame only after all four camera callbacks have joined the current
snapshot. The head-pixel review is a separate post-capture task.
"""
import json
import math

from shapely.geometry import MultiPoint, Polygon


def _number(value, label):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Nonfinite Native " + label)
    return float(value)


def _actor(actor, world_map):
    pose = actor.get_transform()
    vertices = actor.bounding_box.get_world_vertices(pose)
    if len(vertices) < 4:
        raise ValueError("Complete Native body vertices required")
    waypoint = world_map.get_waypoint(actor.get_location(), project_to_road=False)
    if waypoint is None:
        raise ValueError("No Native driving waypoint at original frame")
    velocity = actor.get_velocity()
    body = [[_number(v.x, "body x"), _number(v.y, "body y")] for v in vertices]
    vx, vy, vz = (_number(getattr(velocity, axis), "velocity " + axis) for axis in "xyz")
    return {"actor_id": actor.id,
            "position_xy_m": [_number(pose.location.x, "x"), _number(pose.location.y, "y")],
            "body_vertices_xy_m": body,
            "heading_deg": _number(pose.rotation.yaw, "heading"),
            "velocity_xyz_mps": [vx, vy, vz],
            "speed_mps": math.sqrt(vx*vx + vy*vy + vz*vz),
            "native_road_id": waypoint.road_id, "native_lane_id": waypoint.lane_id,
            "native_junction_id": waypoint.get_junction().id if waypoint.is_junction else None,
            "body_source": "actor.bounding_box.get_world_vertices"}


def _stop_state(actor, polygon):
    angle = math.radians(actor["heading_deg"])
    ahead = (math.cos(angle), math.sin(angle))
    front = max(actor["body_vertices_xy_m"], key=lambda p: p[0]*ahead[0] + p[1]*ahead[1])
    return {"speed_mps": actor["speed_mps"], "front_xy_m": front,
            "body_inside_crossing": MultiPoint(actor["body_vertices_xy_m"]).convex_hull.intersects(polygon),
            "native_road_id": actor["native_road_id"], "native_lane_id": actor["native_lane_id"]}


def _native_state(light):
    state = str(light.get_state()).split(".")[-1]
    if state not in ("Red", "Yellow", "Green", "Off", "Unknown"):
        raise ValueError("Unrecognized Native traffic-light state: " + state)
    return state


def record_frame(frame_map, crossing_stream, signal_stream, stop_stream,
                 snapshot, world_map, ego, other, light, other_light, plan,
                 expected_state, other_expected_state):
    """Append one synchronized original sample after camera frame validation."""
    if (expected_state, other_expected_state) not in (("Green", "Red"), ("Off", "Off")):
        raise ValueError("Exact operative or Off signal pair expected")
    if plan.get("physical_acceptance_claimed") is not False or not plan.get("native_junction_id"):
        raise ValueError("Checked Native junction plan required")
    polygon = Polygon(plan.get("crossing_polygon_xy_m", []))
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Sourced Native crossing polygon required")
    time_s = _number(snapshot.timestamp.elapsed_seconds, "time")
    ego_row, other_row = _actor(ego, world_map), _actor(other, world_map)
    if ego_row["actor_id"] == other_row["actor_id"]:
        raise ValueError("Distinct Native vehicle identities required")
    state, other_state = _native_state(light), _native_state(other_light)
    if state != expected_state or other_state != other_expected_state:
        raise ValueError("Native signal state drift at original frame")
    if type(light.id) is not int or type(other_light.id) is not int or light.id == other_light.id:
        raise ValueError("Two distinct Native signal actor identities required")
    frame = snapshot.frame
    crossing = {"frame": frame, "time_s": time_s, "ego": ego_row, "other": other_row,
                "ego_vertices_m": ego_row["body_vertices_xy_m"]}
    signal = {"frame": frame, "time_s": time_s, "native_signal_id": light.id,
              "state": state, "other_native_signal_id": other_light.id,
              "other_state": other_state}
    stop = {"frame": frame, "time_s": time_s,
            "ego": _stop_state(ego_row, polygon), "other": _stop_state(other_row, polygon)}
    mapped = frame_map.append(frame, time_s)
    for stream, row in ((crossing_stream, crossing), (signal_stream, signal), (stop_stream, stop)):
        stream.write(json.dumps(row, allow_nan=False) + "\n")
    return mapped, crossing, signal, stop


def source_contexts(site, plan, light, other_light):
    """Build sourced geometry/identity contexts, without a head-visibility claim."""
    approaches = plan.get("approaches", {})
    if set(approaches) != {"ego", "other"}:
        raise ValueError("Two checked Native approach plans required")
    for key in ("device_inventory_source", "approach_geometry_source"):
        if not site.get(key):
            raise ValueError("Missing sourced site context: " + key)
    references = site.get("selected_stop_references")
    if not isinstance(references, dict) or set(references) != {"ego", "other"}:
        raise ValueError("Selected source-reviewed stop references required")
    for party, reference in references.items():
        if not isinstance(reference, dict) or reference.get("kind") not in (
                "marked_stop_line", "near_side_crosswalk", "nearest_view_point"):
            raise ValueError("Selected source-reviewed stop reference required: " + party)
        if not reference.get("geometry_source") or not reference.get("reference_review_source"):
            raise ValueError("Stop reference provenance required: " + party)
        segment = reference.get("segment_xy_m")
        if not isinstance(segment, list) or len(segment) != 2 or any(
                not isinstance(p, list) or len(p) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in p)
                for p in segment):
            raise ValueError("Finite stop reference segment required: " + party)
    native_map_name = site.get("native_map_name")
    if (not native_map_name or type(light.id) is not int or type(other_light.id) is not int
            or light.id == other_light.id):
        raise ValueError("Native map and distinct signal identities required")
    ego = approaches["ego"]
    road_geometry = {"intersection_id": plan["native_junction_id"],
        "intersection_polygon_xy_m": plan["crossing_polygon_xy_m"],
        "intersection_polygon_source": plan["crossing_polygon_source"],
        "ego_highway_id": plan["ego_highway_id"],
        "other_highway_id": plan["other_highway_id"],
        "device_inventory_source": site["device_inventory_source"],
        "approach_geometry_source": site["approach_geometry_source"],
        "ego_approach_origin_xy_m": ego["start_xy_m"],
        "other_approach_origin_xy_m": approaches["other"]["start_xy_m"],
        "ego_approach_heading_deg": ego["heading_deg"],
        "other_approach_heading_deg": approaches["other"]["heading_deg"],
        "official_device_status_judgment": "unresolved; requires source review"}
    signal_context = {"intersection_id": plan["native_junction_id"],
        "native_signal_id": light.id, "native_map_id": native_map_name,
        "governed_road_id": ego["road_id"], "governed_lane_id": ego["lane_id"],
        "other_native_signal_id": other_light.id,
        "other_governed_road_id": approaches["other"]["road_id"],
        "other_governed_lane_id": approaches["other"]["lane_id"]}
    stop_context = {"intersection_id": plan["native_junction_id"],
        "selected_references": references}
    return {"road_geometry.json": road_geometry,
            "signal_context.json": signal_context, "stop_context.json": stop_context}
