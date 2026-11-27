"""Acquire same-tick railway sight rays from an original CARLA world.

The caller supplies a reviewed original at-grade rail survey and original
rail-vehicle actors. A named synthetic rail or static sight flag is rejected.
"""

from __future__ import annotations

from math import hypot, isfinite

from rail_sight import FOUR_HUNDRED_FEET_M


def _xyz(location):
    values = [float(location.x), float(location.y), float(location.z)]
    if not all(isfinite(v) for v in values):
        raise ValueError("nonfinite Native world location")
    return values


def _probe(world, eye, endpoint, observer=None, target=None):
    hits = []
    for hit in world.cast_ray(eye, endpoint):
        point = hit.location
        if (observer is not None and observer.bounding_box.contains(
                point, observer.get_transform())):
            continue
        if (target is not None and target.bounding_box.contains(
                point, target.get_transform())):
            continue
        if point.distance(eye) < .05 or point.distance(endpoint) < .02:
            continue
        hits.append({"label": str(hit.label), "location_m": _xyz(point)})
    return {"observer_m": _xyz(eye), "target_m": _xyz(endpoint),
            "blockers": hits, "clear": not hits,
            "method": "original_world_cast_ray_same_native_tick"}


def observe(world, ego, rail_vehicles, review, location_factory, frame):
    if not isinstance(frame, int) or frame < 0:
        raise ValueError("original Native frame required")
    if (review.get("review_status") != "independently_reviewed"
            or review.get("provenance_kind") != "original_native"
            or review.get("crossing_kind") != "at_grade"
            or not review.get("source_sha256") or not review.get("railway_identity")):
        raise ValueError("independently reviewed original grade railway source required")
    crossing = review.get("crossing_xyz_m")
    rail_axis = review.get("rail_unit_direction_xy")
    if not isinstance(crossing, list) or len(crossing) != 3 or not isinstance(rail_axis, list) or len(rail_axis) != 2:
        raise ValueError("original rail survey geometry missing")
    ux, uy = map(float, rail_axis)
    if abs(hypot(ux, uy)-1) > 1e-6:
        raise ValueError("original rail axis is not unit length")
    if len(rail_vehicles) != 2 or {r["side"] for r in rail_vehicles} != {"left", "right"}:
        raise ValueError("original rail traffic in both directions required")
    eye = ego.get_transform().transform(location_factory(z=1.4))
    result = {"frame": frame, "ego_actor_id": ego.id, "observer_m": _xyz(eye),
              "review_source_sha256": review["source_sha256"],
              "directions": {}, "crossing": None}
    crossing_target = location_factory(x=crossing[0], y=crossing[1], z=crossing[2]+1.4)
    result["crossing"] = _probe(world, eye, crossing_target, observer=ego)
    for side, sign in (("left", -1), ("right", 1)):
        actor = next(r["actor"] for r in rail_vehicles if r["side"] == side)
        if not actor.is_alive or not actor.type_id.startswith("vehicle."):
            raise ValueError("original active railway vehicle actor required")
        center = actor.get_transform().location
        along = (center.x-crossing[0])*ux + (center.y-crossing[1])*uy
        if sign*along <= 0 or abs(along) > FOUR_HUNDRED_FEET_M:
            raise ValueError("rail traffic actor outside signed 400-foot source extent")
        rays = []
        clear_distance = 0.0
        for distance in list(range(1, 122)) + [FOUR_HUNDRED_FEET_M]:
            endpoint = location_factory(x=crossing[0]+sign*distance*ux,
                                        y=crossing[1]+sign*distance*uy,
                                        z=crossing[2]+1.4)
            ray = _probe(world, eye, endpoint, observer=ego)
            ray["rail_distance_m"] = distance
            rays.append(ray)
            if not ray["clear"]:
                break
            clear_distance = float(distance)
        body = actor.bounding_box
        pose = actor.get_transform()
        vertices = list(body.get_world_vertices(pose))
        if len(vertices) != 8:
            raise ValueError("original rail vehicle body vertices missing")
        body_rays = [_probe(world, eye, vertex, observer=ego, target=actor)
                     for vertex in vertices]
        result["directions"][side] = {
            "actor_id": actor.id, "actor_type_id": actor.type_id,
            "actor_position_m": _xyz(center), "clear_distance_m": clear_distance,
            "rail_rays": rays, "body_rays": body_rays,
            "rail_vehicle_visible_proxy": any(ray["clear"] for ray in body_rays)}
    return result
