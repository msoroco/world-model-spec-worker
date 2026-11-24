"""Source-gated Native construction and original-frame LVMC 11.12.070(B) audit.

The entering driver's antecedent legal duty is not decided here. Native observations
and jurisdiction/through-highway documents remain separate from legal review.
"""

from __future__ import annotations

import math


ASSIGNMENT = "testing__C179789__LVMC-11-12-070-B__motor_vehicle_driver"
LAW = "LVMC-11-12-070-B"
CASES = {
    "cross_yield": ("cross", "yield_request"),
    "cross_continue": ("cross", "continue_request"),
    "enter_yield": ("enter", "yield_request"),
    "enter_continue": ("enter", "continue_request"),
}
CAMERAS = ("front", "rear", "left", "right")


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_site(site, case_key, map_sha256):
    """Verify reviewed site/route sources before using a map or creating actors."""
    require(case_key in CASES, "unknown exact case")
    require(site.get("law_id") == LAW and site.get("cell_id") == "C179789", "site identity mismatch")
    require(isinstance(map_sha256, str) and len(map_sha256) == 64 and site.get("map_sha256") == map_sha256, "map seal mismatch")
    for field in ("municipal_jurisdiction_source", "through_highway_designation_source",
                  "intersection_geometry_source", "entrance_control_source",
                  "antecedent_review_source"):
        require(site.get(field), f"{field} missing")
    require(site.get("road_kind") == "paved_road" and site.get("control_kind") == "other_vehicle", "frozen cell mismatch")
    require(site.get("intersection_id") and site.get("map_name"), "intersection identity missing")
    box = site.get("conflict_box_xy")
    require(isinstance(box, list) and len(box) == 4 and all(finite_number(v) for v in box)
            and box[0] < box[2] and box[1] < box[3], "reviewed conflict box missing")
    routes = site.get("routes", {})
    for role in ("through", "entering"):
        route = routes.get(role, {})
        require(route.get("road_id") is not None and route.get("lane_id") is not None
                and route.get("direction_source") and route.get("route_source"), f"{role} route source missing")
        waypoints = route.get("waypoints_xyz")
        require(isinstance(waypoints, list) and len(waypoints) >= 3
                and all(isinstance(p, list) and len(p) == 3 and all(finite_number(v) for v in p) for p in waypoints),
                f"{role} Native route waypoints missing")
    require(routes["through"]["road_id"] != routes["entering"]["road_id"], "distinct intersection approaches missing")
    require(site.get("entering_maneuver") == CASES[case_key][0], "enter/cross route mismatch")
    for role in ("through", "entering"):
        points = routes[role]["waypoints_xyz"]
        require(not _inside(box, points[0][:2]) and _inside(box, points[1][:2])
                and not _inside(box, points[-1][:2]), f"{role} route does not traverse reviewed conflict box")
    through = routes["through"]["waypoints_xyz"]
    entering = routes["entering"]["waypoints_xyz"]
    through_dx = through[-1][0] - through[-2][0]
    through_dy = through[-1][1] - through[-2][1]
    entering_dx = entering[-1][0] - entering[-2][0]
    entering_dy = entering[-1][1] - entering[-2][1]
    denominator = math.hypot(through_dx, through_dy) * math.hypot(entering_dx, entering_dy)
    require(denominator > 1.0, "departure route vectors missing")
    alignment = (through_dx * entering_dx + through_dy * entering_dy) / denominator
    if CASES[case_key][0] == "enter":
        require(alignment >= 0.9, "entering route does not merge along through highway")
    else:
        require(abs(alignment) <= 0.4, "crossing route does not cross through highway")
    return routes


def _waypoint(world_map, xyz, expected):
    import carla  # Native-only dependency
    waypoint = world_map.get_waypoint(carla.Location(*xyz), project_to_road=False)
    require(waypoint is not None and waypoint.road_id == expected["road_id"]
            and waypoint.lane_id == expected["lane_id"], "Native lane readback mismatch")
    return waypoint


def construct(world, site, case_key, map_sha256, ego_blueprint="vehicle.tesla.model3",
              other_blueprint="vehicle.audi.tt"):
    """Create both participants on reviewed approach lanes; caller owns cleanup."""
    routes = validate_site(site, case_key, map_sha256)
    world_map = world.get_map()
    require(world_map.name == site["map_name"], "Native map identity mismatch")
    blueprints = world.get_blueprint_library()
    actors = {}
    try:
        for role, blueprint_id in (("through", ego_blueprint), ("entering", other_blueprint)):
            route = routes[role]
            waypoint = _waypoint(world_map, route["waypoints_xyz"][0], route)
            blueprint = blueprints.find(blueprint_id)
            require(blueprint is not None, f"{role} blueprint missing")
            actor = world.try_spawn_actor(blueprint, waypoint.transform)
            require(actor is not None, f"{role} spawn failed")
            actors[role] = actor
    except Exception:
        for actor in actors.values():
            actor.destroy()
        raise
    return {"actors": actors, "routes": routes, "case_id": f"{ASSIGNMENT}__{case_key}",
            "request": CASES[case_key][1], "map_sha256": map_sha256}


def control_tick(actor, target_xyz, requested_mps, allow_go=True):
    """Bounded waypoint steering and speed feedback from actual Native state."""
    require(len(target_xyz) == 3 and all(finite_number(v) for v in target_xyz), "target waypoint missing")
    require(finite_number(requested_mps) and 0 <= requested_mps <= 25, "requested speed invalid")
    velocity = actor.get_velocity()
    transform = actor.get_transform()
    location = transform.location
    forward = transform.get_forward_vector()
    require(all(finite_number(v) for v in (velocity.x, velocity.y, velocity.z, location.x,
                                           location.y, forward.x, forward.y)), "Native actor state missing")
    speed = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
    dx, dy = target_xyz[0] - location.x, target_xyz[1] - location.y
    distance = math.hypot(dx, dy)
    require(distance > 0.5, "waypoint target too close")
    cross = (forward.x * dy - forward.y * dx) / distance
    dot = (forward.x * dx + forward.y * dy) / distance
    require(dot > -0.1, "route target behind actor")
    steer = max(-0.6, min(0.6, 0.9 * cross))
    target_speed = requested_mps if allow_go else 0.0
    error = target_speed - speed
    throttle = max(0.0, min(0.65, 0.22 + 0.08 * error)) if error > 0.2 else 0.0
    brake = max(0.0, min(0.85, 0.10 + 0.12 * -error)) if error < -0.2 else 0.0
    import carla
    actor.apply_control(carla.VehicleControl(throttle=throttle, brake=brake, steer=steer))
    return {"observed_speed_mps": speed, "requested_speed_mps": target_speed,
            "throttle": throttle, "brake": brake, "steer": steer}


def _inside(box, xy):
    return box[0] <= xy[0] <= box[2] and box[1] <= xy[1] <= box[3]


def measure(site, case_key, map_sha256, frames):
    """Describe original 20 Hz pair motion and precedence without a legal label."""
    validate_site(site, case_key, map_sha256)
    require(isinstance(frames, list) and len(frames) >= 400, "original 20 Hz history incomplete")
    box = site["conflict_box_xy"]
    first_inside = {"through": None, "entering": None}
    samples = []
    actor_ids = {}
    previous_native_frame = None
    for i, frame in enumerate(frames):
        require(frame.get("frame_index") == i and frame.get("native_frame") is not None, "original frame identity gap")
        require(type(frame["native_frame"]) is int and
                (previous_native_frame is None or frame["native_frame"] == previous_native_frame + 1),
                "Native frame nonconsecutive")
        previous_native_frame = frame["native_frame"]
        require(finite_number(frame.get("time_s")) and abs(frame["time_s"] - i / 20) <= 0.002, "original 20 Hz time join failed")
        require(frame.get("map_sha256") == map_sha256 and frame.get("intersection_id") == site["intersection_id"], "Native source identity mismatch")
        row = {"frame_index": i, "native_frame": frame["native_frame"],
               "time_s": frame["time_s"]}
        for role in ("through", "entering"):
            actor = frame.get(role, {})
            xy = actor.get("center_xy")
            require(actor.get("alive") is True and actor.get("actor_id") is not None
                    and isinstance(xy, list) and len(xy) == 2 and all(finite_number(v) for v in xy)
                    and finite_number(actor.get("speed_mps")) and actor["speed_mps"] >= 0,
                    f"{role} original actor source missing")
            if role in actor_ids:
                require(actor["actor_id"] == actor_ids[role], f"{role} actor identity changed")
            else:
                actor_ids[role] = actor["actor_id"]
            inside = _inside(box, xy)
            row[role] = {"center_xy": xy, "speed_mps": actor["speed_mps"], "inside_conflict": inside}
            if inside and first_inside[role] is None:
                first_inside[role] = i
        samples.append(row)
    require(actor_ids["through"] != actor_ids["entering"], "same actor used for both roles")
    require(all(v is not None for v in first_inside.values()), "two-vehicle intersection traversal missing")
    require(first_inside["entering"] > 0 and first_inside["through"] > 0, "pre-entry history missing")
    pre = samples[:first_inside["entering"]]
    entering_min = min(x["entering"]["speed_mps"] for x in pre)
    near = samples[max(0, first_inside["entering"] - 40):first_inside["entering"]]
    through_min = min(x["through"]["speed_mps"] for x in near)
    return {"case_id": f"{ASSIGNMENT}__{case_key}", "law_id": LAW,
            "map_sha256": map_sha256, "intersection_id": site["intersection_id"],
            "entering_maneuver": CASES[case_key][0], "through_request": CASES[case_key][1],
            "first_conflict_frame": first_inside, "entering_preentry_min_speed_mps": entering_min,
            "through_preentry_min_speed_mps": through_min, "original_frame_count": len(frames),
            "original_samples": samples, "antecedent_legal_review": "unresolved",
            "right_of_way_legal_review": "unresolved"}


def compare(reports, case_keys):
    require(len(case_keys) == 2 and len(reports) == 2, "comparison pair missing")
    require(case_keys in (["cross_yield", "cross_continue"], ["enter_yield", "enter_continue"]), "comparison variables invalid")
    for report, key in zip(reports, case_keys):
        require(report.get("case_id") == f"{ASSIGNMENT}__{key}" and report.get("original_frame_count", 0) >= 400
                and report.get("original_samples"), "comparison original evidence missing")
    require(reports[0]["map_sha256"] == reports[1]["map_sha256"]
            and reports[0]["intersection_id"] == reports[1]["intersection_id"]
            and reports[0]["entering_maneuver"] == reports[1]["entering_maneuver"],
            "comparison fixed site or maneuver changed")
    return {"case_ids": [r["case_id"] for r in reports],
            "through_preentry_min_speed_mps": [r["through_preentry_min_speed_mps"] for r in reports],
            "legal_review": "unresolved"}
