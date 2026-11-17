"""CPU-testable Native actor construction for truck-and-trailer alternatives.

The caller supplies reviewed tractor and trailer blueprints, world transforms for
the tractors, and trailer transforms relative to their tractors. A successful
spawn is only a construction attempt; Native attachment, motion, vehicle class
and legal width must still be reviewed from the original capture.
"""

from contextlib import contextmanager
import math


MIN_WIDTH_M = 80 * 0.0254


def _unit_tangent(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("Sourced lane tangent required")
    x, y = (float(v) for v in value)
    length = math.hypot(x, y)
    if not math.isfinite(length) or length <= 0:
        raise ValueError("Finite nonzero lane tangent required")
    return x / length, y / length


def _bounds(actor, tangent):
    box = actor.bounding_box
    corners = box.get_world_vertices(actor.get_transform())
    if len(corners) < 4:
        raise ValueError("Native component body vertices missing")
    tx, ty = tangent
    along, lateral = [], []
    for point in corners:
        x, y = float(point.x), float(point.y)
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Nonfinite Native component vertex")
        along.append(x * tx + y * ty)
        lateral.append(-x * ty + y * tx)
    return min(along), max(along), min(lateral), max(lateral)


def combination_envelope(tractor, trailer, lane_forward_xy, *, max_hitch_gap_m=5.0):
    """Measure the two component body bounds, including trailer width and rear."""
    tangent = _unit_tangent(lane_forward_xy)
    a, b = _bounds(tractor, tangent), _bounds(trailer, tangent)
    hitch_gap = a[0] - b[1]
    if not 0 <= hitch_gap <= max_hitch_gap_m:
        raise ValueError("Trailer does not follow tractor at the planned hitch")
    width = max(a[3], b[3]) - min(a[2], b[2])
    if not math.isfinite(width) or width <= 0:
        raise ValueError("Combined overall width invalid")
    return {"front_m": max(a[1], b[1]), "rear_m": min(a[0], b[0]),
            "overall_width_m": width, "hitch_gap_m": hitch_gap,
            "component_intervals_m": {"tractor": [a[0], a[1]],
                                      "trailer": [b[0], b[1]]},
            "classification": "unverified_native_components"}


def combination_source_row(groups, waypoints, lane_forward_xy, road_id, lane_id,
                           frame, time_s):
    """Retain each original component body and its combined projected width.

    Called after a Native tick. The row has the same ego/lead shape as the
    single-truck history, while retaining component identities for source audit.
    A positive geometry observation does not settle legal vehicle class.
    """
    tangent = _unit_tangent(lane_forward_xy)
    if type(frame) is not int or frame < 0 or not math.isfinite(time_s):
        raise ValueError("Valid original combination frame and time required")
    row = {"frame": frame, "time_s": float(time_s)}
    for role in ("ego", "lead"):
        actors = groups.get(role, {})
        lanes = waypoints.get(role, {})
        if set(actors) != {"tractor", "trailer"} or set(lanes) != {"tractor", "trailer"}:
            raise ValueError("Missing original combination component: " + role)
        vertices = []
        components = {}
        for part in ("tractor", "trailer"):
            actor, lane = actors[part], lanes[part]
            if lane is None or (lane.road_id, lane.lane_id) != (road_id, lane_id):
                raise ValueError("Original combination component lane mismatch: " + role)
            body = actor.bounding_box.get_world_vertices(actor.get_transform())
            if len(body) < 4:
                raise ValueError("Missing original combination body: " + role)
            points = []
            for vertex in body:
                point = [float(vertex.x), float(vertex.y)]
                if not all(map(math.isfinite, point)):
                    raise ValueError("Nonfinite original combination body")
                points.append(point)
            vertices.extend(points)
            velocity = actor.get_velocity()
            velocity_mps = [float(velocity.x), float(velocity.y), float(velocity.z)]
            if not all(map(math.isfinite, velocity_mps)):
                raise ValueError("Nonfinite original combination velocity: " + role)
            components[part] = {"actor_id": actor.id, "blueprint_id": actor.type_id,
                                "road_id": lane.road_id, "lane_id": lane.lane_id,
                                "body_vertices_xy_m": points,
                                "velocity_mps": velocity_mps}
        envelope = combination_envelope(actors["tractor"], actors["trailer"], tangent)
        row[role] = {"actor_id": actors["tractor"].id,
                     "blueprint_id": actors["tractor"].type_id,
                     "road_id": road_id, "lane_id": lane_id,
                     "overall_width_m": envelope["overall_width_m"],
                     "overall_width_source": "original Native tractor and trailer body vertices",
                     "body_vertices_xy_m": vertices, "components": components,
                     "velocity_mps": components["tractor"]["velocity_mps"],
                     "is_truck_or_combination": True,
                     "legal_vehicle_class_verified": False,
                     "native_attachment_verified": False}
    return row


def audit_combination_source_row(row, lane_forward_xy, road_id, lane_id):
    """Independently recompute combination width and gap from retained bodies."""
    tx, ty = _unit_tangent(lane_forward_xy)
    spans = {}
    for role in ("ego", "lead"):
        group = row.get(role, {})
        parts = group.get("components", {})
        if set(parts) != {"tractor", "trailer"}:
            raise ValueError("Missing saved combination component: " + role)
        merged = []
        for part in ("tractor", "trailer"):
            component = parts[part]
            if (component.get("road_id"), component.get("lane_id")) != (road_id, lane_id):
                raise ValueError("Saved combination component lane mismatch: " + role)
            points = component.get("body_vertices_xy_m")
            velocity = component.get("velocity_mps")
            if not isinstance(velocity, list) or len(velocity) != 3 or not all(
                isinstance(value, (int, float)) and math.isfinite(value)
                for value in velocity
            ):
                raise ValueError("Missing saved combination velocity: " + role + "/" + part)
            if not isinstance(points, list) or len(points) < 4:
                raise ValueError("Missing saved combination body: " + role)
            for point in points:
                if not isinstance(point, list) or len(point) != 2 or not all(
                    isinstance(v, (int, float)) and math.isfinite(v) for v in point
                ):
                    raise ValueError("Invalid saved combination vertex")
            merged.extend(points)
        if group.get("body_vertices_xy_m") != merged:
            raise ValueError("Combined body differs from saved components: " + role)
        if (group.get("actor_id") != parts["tractor"].get("actor_id") or
                group.get("blueprint_id") != parts["tractor"].get("blueprint_id") or
                group.get("velocity_mps") != parts["tractor"]["velocity_mps"]):
            raise ValueError("Combined tractor identity or velocity differs from saved component: " + role)
        along = [x * tx + y * ty for x, y in merged]
        lateral = [-x * ty + y * tx for x, y in merged]
        width = max(lateral) - min(lateral)
        if not math.isclose(group.get("overall_width_m", float("nan")), width,
                            rel_tol=0, abs_tol=1e-6):
            raise ValueError("Combined width differs from saved components: " + role)
        spans[role] = {"rear_m": min(along), "front_m": max(along),
                       "overall_width_m": width}
    gap = spans["lead"]["rear_m"] - spans["ego"]["front_m"]
    return {"longitudinal_body_gap_m": gap, "participants": spans,
            "legal_vehicle_class_verified": False}


def capture_combination_history(world, groups, control_step, *, road_id, lane_id,
                                lane_forward_xy, frames=600, rate_hz=20,
                                min_width_m=MIN_WIDTH_M, require_motion=True):
    """Tick and retain original component bodies for a prospective exact case.

    ``control_step`` applies the caller's reviewed tractor controls before each
    tick. The trailer is attached by ``spawn_combination_pair``. This function
    records Native readback; it never treats requested controls as observed motion.
    """
    tangent = _unit_tangent(lane_forward_xy)
    if type(frames) is not int or frames < 2 or type(rate_hz) is not int or rate_hz <= 0:
        raise ValueError("Valid finite-frame capture schedule required")
    if not callable(control_step) or not math.isfinite(min_width_m) or min_width_m <= 0:
        raise ValueError("Control callback and width boundary required")
    rows = []
    for index in range(frames):
        control_step(index, groups)
        frame = world.tick()
        if type(frame) is not int or (rows and frame != rows[-1]["frame"] + 1):
            raise ValueError("Original combination frames are not contiguous")
        waypoints = {}
        for role in ("ego", "lead"):
            waypoints[role] = {}
            for part in ("tractor", "trailer"):
                actor = groups[role][part]
                waypoints[role][part] = world.get_map().get_waypoint(
                    actor.get_location(), project_to_road=False)
        row = combination_source_row(groups, waypoints, tangent, road_id, lane_id,
                                     frame, index / rate_hz)
        measured = audit_combination_source_row(row, tangent, road_id, lane_id)
        if measured["longitudinal_body_gap_m"] < 0:
            raise ValueError("Original combination bodies overlap")
        if any(measured["participants"][role]["overall_width_m"] < min_width_m
               for role in ("ego", "lead")):
            raise ValueError("Original combination below 80-inch width")
        rows.append(row)
    if require_motion:
        tx, ty = tangent
        for role in ("ego", "lead"):
            for part in ("tractor", "trailer"):
                def center_along(row):
                    vertices = row[role]["components"][part]["body_vertices_xy_m"]
                    return sum(x * tx + y * ty for x, y in vertices) / len(vertices)
                if center_along(rows[-1]) <= center_along(rows[0]):
                    raise ValueError("Original combination component motion absent: "
                                     + role + "/" + part)
    return rows


@contextmanager
def spawn_combination_pair(world, blueprints, transforms, attachment_type,
                           *, road_id, lane_id, lane_forward_xy,
                           min_width_m=MIN_WIDTH_M, expected_body_gap_m=None,
                           gap_tolerance_m=0.5, position_lead=None):
    """Spawn two tractor/trailer groups and check the original body gap.

    ``blueprints`` and ``transforms`` each map ego/lead to tractor/trailer.
    Trailer transforms are relative to their tractors. ``attachment_type`` is
    supplied by the local CARLA adapter, avoiding a CPU-time CARLA import.
    """
    tangent = _unit_tangent(lane_forward_xy)
    if not math.isfinite(min_width_m) or min_width_m <= 0:
        raise ValueError("Valid width boundary required")
    if expected_body_gap_m is not None:
        if not math.isfinite(expected_body_gap_m) or expected_body_gap_m < 0:
            raise ValueError("Valid expected body gap required")
        if not math.isfinite(gap_tolerance_m) or gap_tolerance_m < 0:
            raise ValueError("Valid body gap tolerance required")
    if position_lead is not None and (expected_body_gap_m is None or not callable(position_lead)):
        raise ValueError("Lead placement requires a target gap and callback")
    if not blueprints or not transforms or attachment_type is None:
        raise ValueError("Reviewed combination components and attachment required")
    owned, groups = [], {}
    try:
        for role in ("ego", "lead"):
            if set(blueprints.get(role, {})) != {"tractor", "trailer"} or set(transforms.get(role, {})) != {"tractor", "trailer"}:
                raise ValueError("Both tractor and trailer required for " + role)
            tractor = world.try_spawn_actor(blueprints[role]["tractor"], transforms[role]["tractor"])
            if tractor is None:
                raise ValueError("Native tractor spawn failed: " + role)
            owned.append(tractor)
            trailer = world.try_spawn_actor(blueprints[role]["trailer"], transforms[role]["trailer"],
                                            attach_to=tractor, attachment_type=attachment_type)
            if trailer is None:
                raise ValueError("Native trailer attachment failed: " + role)
            owned.append(trailer)
            groups[role] = {"tractor": tractor, "trailer": trailer}
        world.tick()
        if position_lead is not None:
            initial_ego = combination_envelope(groups["ego"]["tractor"],
                                               groups["ego"]["trailer"], tangent)
            initial_lead = combination_envelope(groups["lead"]["tractor"],
                                                groups["lead"]["trailer"], tangent)
            initial_gap = initial_lead["rear_m"] - initial_ego["front_m"]
            if initial_gap < 0:
                raise ValueError("Combination staging bodies overlap")
            position_lead(groups["lead"], expected_body_gap_m - initial_gap, tangent)
            world.tick()
        envelopes = {}
        for role, actors in groups.items():
            for actor in actors.values():
                waypoint = world.get_map().get_waypoint(actor.get_location(), project_to_road=False)
                if waypoint is None or (waypoint.road_id, waypoint.lane_id) != (road_id, lane_id):
                    raise ValueError("Combination component outside selected lane: " + role)
            envelope = combination_envelope(actors["tractor"], actors["trailer"], tangent)
            if envelope["overall_width_m"] < min_width_m:
                raise ValueError("Combined vehicle below 80-inch width: " + role)
            envelopes[role] = envelope
        gap = envelopes["lead"]["rear_m"] - envelopes["ego"]["front_m"]
        if gap < 0:
            raise ValueError("Combination bodies overlap or order is reversed")
        if expected_body_gap_m is not None and abs(gap - expected_body_gap_m) > gap_tolerance_m:
            raise ValueError("Native combination body gap differs from selected target")
        yield {"actors": groups, "envelopes": envelopes,
               "initial_longitudinal_body_gap_m": gap,
               "expected_body_gap_m": expected_body_gap_m,
               "native_attachment_verified": False,
               "legal_vehicle_class_verified": False,
               "physical_motion": "unverified"}
    finally:
        for actor in reversed(owned):
            actor.destroy()
