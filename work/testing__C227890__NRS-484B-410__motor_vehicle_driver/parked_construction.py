"""Source-gated geometry and controller targets for an original parked departure.

The returned commands are requests. The Native operator must read back actual
actors, motion, map identity and parking context before any result is measured.
"""
from __future__ import annotations

import math

ASSIGNMENT = "testing__C227890__NRS-484B-410__motor_vehicle_driver"
VARIANTS = frozenset((
    "rear_wait", "rear_intrude", "rear_clear", "opposing_wait",
    "opposing_intrude", "opposing_nonconflict",
))


def _point(value, label):
    if not isinstance(value, list) or len(value) != 2 or any(
            type(v) not in (int, float) or not math.isfinite(v) for v in value):
        raise ValueError("reviewed " + label + " point missing")
    return [float(value[0]), float(value[1])]


def _polygon(value, label):
    if not isinstance(value, list) or len(value) < 3:
        raise ValueError("reviewed " + label + " polygon missing")
    return [_point(row, label) for row in value]


def _inside(point, polygon):
    x, y = point
    enclosed = False
    for i, (x1, y1) in enumerate(polygon):
        x2, y2 = polygon[(i + 1) % len(polygon)]
        if (y1 > y) != (y2 > y):
            crossing = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < crossing:
                enclosed = not enclosed
    return enclosed


def _source(source, label):
    if not isinstance(source, dict) or not isinstance(source.get("path"), str):
        raise ValueError("reviewed " + label + " source missing")
    digest = source.get("sha256", "")
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("reviewed " + label + " source hash missing")


def build_plan(site, case_id, *, direction=1):
    """Build both approach orientations from a reviewed original highway site."""
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("wrong parked-departure assignment")
    variant = case_id.removeprefix(ASSIGNMENT + "__")
    if variant not in VARIANTS or type(direction) is not int or direction not in (-1, 1):
        raise ValueError("unknown parked-departure variant or direction")
    if (site.get("case_id") != case_id or
            site.get("source_kind") != "reviewed_original_native_site" or
            site.get("public_highway_status") is not True or
            site.get("public_dedication_reviewed") is not True or
            site.get("public_vehicular_use_reviewed") is not True or
            site.get("parking_permitted_at_capture_time") is not True):
        raise ValueError("public highway or permitted parking source review missing")
    sources = site.get("reviewed_sources")
    if not isinstance(sources, dict):
        raise ValueError("reviewed site sources missing")
    for label in ("map", "highway_boundary", "dedication", "public_use",
                  "parking_permission", "vehicle_blueprint", "approach_route"):
        _source(sources.get(label), label)
    highway = _polygon(site.get("highway_polygon_xy_m"), "highway")
    bay = _polygon(site.get("parking_bay_polygon_xy_m"), "parking bay")
    suffix = "" if direction == 1 else "_fallback"
    ego_parked = _point(site.get("parked_vehicle_center" + suffix + "_xy_m"), "parked vehicle")
    ego_entry = _point(site.get("ego_departure_entry" + suffix + "_xy_m"), "departure entry")
    ego_exit = _point(site.get("ego_departure_exit" + suffix + "_xy_m"), "departure exit")
    if any(not _inside(point, highway) for point in (ego_parked, ego_entry, ego_exit)):
        raise ValueError("departure does not stay in reviewed highway")
    if not _inside(ego_parked, bay):
        raise ValueError("initial parked vehicle is outside reviewed permitted bay")
    if math.dist(ego_parked, ego_entry) < 1 or math.dist(ego_entry, ego_exit) < 8:
        raise ValueError("surveyed departure path too short to test movement")
    route_key = "rear_approach_route_xy_m" if variant.startswith("rear") else "opposing_approach_route_xy_m"
    route = site.get(route_key)
    if not isinstance(route, list) or len(route) < 2:
        raise ValueError("reviewed other vehicle route missing")
    route = [_point(value, "other vehicle route") for value in route]
    if any(not _inside(point, highway) for point in route):
        raise ValueError("other vehicle route leaves reviewed highway")
    if math.dist(route[0], route[-1]) < 25:
        raise ValueError("other vehicle approach is too short")
    if variant == "opposing_nonconflict":
        if site.get("nonconflicting_opposing_route_reviewed") is not True:
            raise ValueError("nonconflicting opposing route not source reviewed")
    request = {
        "rear_wait": ("rear", "wait_until_other_passes"),
        "rear_intrude": ("rear", "depart_before_other_passes"),
        "rear_clear": ("rear", "depart_when_no_vehicle_approaching"),
        "opposing_wait": ("opposing", "wait_until_other_clears_crossing"),
        "opposing_intrude": ("opposing", "depart_before_other_clears_crossing"),
        "opposing_nonconflict": ("opposing", "depart_on_nonintersecting_routes"),
    }[variant]
    return {
        "assignment_id": ASSIGNMENT, "case_id": case_id, "variant": variant,
        "direction": direction, "reviewed_sources": sources,
        "candidate_location": "primary" if direction == 1 else "alternate_same_permitted_bay",
        "ego_initial_parked_center_xy_m": ego_parked,
        "ego_departure_route_xy_m": [ego_parked, ego_entry, ego_exit],
        "other_approach_route_xy_m": route,
        "other_approach_kind": request[0], "controller_request": request[1],
        "operator_actions": [
            "spawn ordinary motor vehicle in source-reviewed permitted parking bay",
            "hold originally parked vehicle with no passenger or goods exchange",
            "spawn and drive source-reviewed other vehicle route and read actual classification",
            "control driver departure according to variant request",
            "read back actual same-tick trajectories, control and original camera pixels",
        ],
        "capture": {"rate_hz": 20, "frames": 900, "duration_s": 45,
                    "cameras": ["overview", "approach", "reference_corner", "driver_reference"]},
        "physical_outcome": "pending_original_native_readback",
        "legal_conclusion": "unreviewed",
    }
