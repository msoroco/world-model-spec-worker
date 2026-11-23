"""Source-bound survey and original-frame checks for NRS 484B.307(3)(a).

No CARLA import occurs at module import. A CARLA signal state alone cannot prove
that the circular aspect and arrow are illuminated simultaneously; original
aspect observations and a source-sealed physical head survey are required.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


class EvidenceError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise EvidenceError(message)


def read_source(root, ref):
    base = Path(root).resolve()
    path = (base / ref["path"]).resolve()
    require(path.is_relative_to(base) and path.is_file(), "missing or escaping original source")
    require(hashlib.sha256(path.read_bytes()).hexdigest() == ref["sha256"], "original source hash mismatch")
    return path


def inside(point, polygon):
    x, y = map(float, point)
    hit = False
    for i, (a, b) in enumerate(polygon):
        c, d = polygon[(i + 1) % len(polygon)]
        cross = (x - a) * (d - b) - (y - b) * (c - a)
        if abs(cross) < 1e-8 and min(a, c) <= x <= max(a, c) and min(b, d) <= y <= max(b, d):
            return True
        if (b > y) != (d > y) and x < a + (y - b) * (c - a) / (d - b):
            hit = not hit
    return hit


def check_site(site, root):
    require(site["cell_id"] == "C111125" and site["actor"] == "motor_vehicle_driver", "wrong cell or actor")
    refs = site["original_sources"]
    paths = {r["path"] for r in refs}
    for key in ("map_source_path", "route_source_path", "signal_survey_path", "crosswalk_source_path", "movement_permission_source_path"):
        require(site[key] in paths, "unbound site source: " + key)
    for ref in refs:
        read_source(root, ref)
    require(site["official_head_id"] and site["ego_approach_id"], "official head/approach absent")
    require(site["facing_relation"] is True, "head does not face ego")
    require(site["arrow_direction"] in ("left", "right"), "arrow direction unknown")
    require(site["ego_movement"] == "straight", "assigned straight movement changed")
    require(site["straight_permission_review"] == "source_review_pending", "unsupported permission verdict")
    route = site["ego_route_xy"]
    require(len(route) >= 3, "short route")
    require(all(len(p) == 2 and all(math.isfinite(float(v)) for v in p) for p in route), "nonfinite route")
    x0, y0 = route[0]
    x1, y1 = route[-1]
    dx, dy = x1-x0, y1-y0
    length = math.hypot(dx, dy)
    require(length > 1, "short straight route")
    require(all(abs((x-x0)*dy-(y-y0)*dx)/length <= site["straight_tolerance_m"] for x, y in route), "route bends")
    for key in ("intersection_polygon_xy", "adjacent_crosswalk_polygon_xy"):
        poly = site[key]
        require(len(poly) >= 3 and all(len(p) == 2 for p in poly), "invalid survey polygon")
    require(any(inside(p, site["intersection_polygon_xy"]) for p in route[1:-1]), "route misses intersection")
    return True


def measure_original(site, root, event_ref, event_root=None):
    check_site(site, root)
    rows = json.loads(read_source(event_root or root, event_ref).read_text())
    require(isinstance(rows, list) and len(rows) >= 3, "original event history absent")
    previous_frame = -1
    exhibition = None
    result = []
    for row in rows:
        frame = row["frame"]
        require(isinstance(frame, int) and frame > previous_frame, "nonmonotonic frame")
        previous_frame = frame
        require(row["official_head_id"] == site["official_head_id"], "signal head changed")
        require(row["facing_approach_id"] == site["ego_approach_id"], "signal approach changed")
        require(row["aspect_observation_source"], "missing original signal aspect observation")
        aspects = row["lit_aspects"]
        dual = sorted(aspects) == sorted(["circular_green", "green_" + site["arrow_direction"] + "_arrow"])
        participants = []
        for user in row["other_users"]:
            require(user["kind"] in ("pedestrian", "motor_vehicle") and user["id"], "other user identity/kind absent")
            require(user.get("lawful_use_source"), "lawful-use source absent")
            region = "intersection" if inside(user["xy"], site["intersection_polygon_xy"]) else "adjacent_crosswalk" if inside(user["xy"], site["adjacent_crosswalk_polygon_xy"]) else "outside"
            participants.append({"id": user["id"], "kind": user["kind"], "region": region, "lawful_use_source": user["lawful_use_source"]})
        observed = {"frame": frame, "dual_green": dual, "ego_in_intersection": inside(row["ego_xy"], site["intersection_polygon_xy"]), "other_users": participants}
        if dual and exhibition is None:
            exhibition = observed
        result.append(observed)
    require(exhibition is not None, "no simultaneous circular green and arrow")
    require(not result[0]["ego_in_intersection"] and any(r["ego_in_intersection"] for r in result), "ego crossing not observed")
    return {"exhibition": exhibition, "records": result, "original_sources": site["original_sources"] + [event_ref], "permission_verdict": None, "right_of_way_verdict": None}


def construct_native(site, root, world, carla, ego_blueprint, other_blueprint=None, other_kind=None):
    """Create actors on a surveyed route; caller owns successful actors."""
    check_site(site, root)
    require(world.get_map().name == site["native_map_name"], "Native map mismatch")
    heads = {str(a.id): a for a in world.get_actors().filter("traffic.traffic_light*")}
    require(str(site["official_head_id"]) in heads, "surveyed head absent")
    require(heads[str(site["official_head_id"])].get_state().name == "Green", "head not green on readback")
    def transform(point):
        return carla.Transform(carla.Location(x=float(point[0]), y=float(point[1]), z=float(site["spawn_z_m"])), carla.Rotation(yaw=float(site["approach_yaw_deg"])))
    ego = world.try_spawn_actor(ego_blueprint, transform(site["ego_route_xy"][0]))
    require(ego is not None, "ego spawn failed")
    actors = [ego]
    try:
        if other_kind is not None:
            require(other_kind in ("pedestrian", "motor_vehicle") and other_blueprint is not None, "other actor configuration absent")
            other = world.try_spawn_actor(other_blueprint, transform(site["other_user_spawn_xy"]))
            require(other is not None, "other user spawn failed")
            actors.append(other)
        return {"actors": actors, "ego_route_xy": site["ego_route_xy"], "official_head_id": site["official_head_id"], "arrow_direction": site["arrow_direction"], "dual_aspect_proven": False}
    except Exception:
        for actor in reversed(actors):
            actor.destroy()
        raise
