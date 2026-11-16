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


@contextmanager
def spawn_combination_pair(world, blueprints, transforms, attachment_type,
                           *, road_id, lane_id, lane_forward_xy,
                           min_width_m=MIN_WIDTH_M):
    """Spawn two tractor/trailer groups and check the original body gap.

    ``blueprints`` and ``transforms`` each map ego/lead to tractor/trailer.
    Trailer transforms are relative to their tractors. ``attachment_type`` is
    supplied by the local CARLA adapter, avoiding a CPU-time CARLA import.
    """
    tangent = _unit_tangent(lane_forward_xy)
    if not math.isfinite(min_width_m) or min_width_m <= 0:
        raise ValueError("Valid width boundary required")
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
        yield {"actors": groups, "envelopes": envelopes,
               "initial_longitudinal_body_gap_m": gap,
               "native_attachment_verified": False,
               "legal_vehicle_class_verified": False,
               "physical_motion": "unverified"}
    finally:
        for actor in reversed(owned):
            actor.destroy()
