"""Source-gated motorcycle/moped lane-use construction and original geometry.

Lateral intrusion is a physical measurement, not a legal cutoff for full use.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    case_id: str
    protected_kind: str
    ego_path: str
    protected_driven: bool


CASES = (
    Case("motorcycle_adjacent_clear", "motorcycle", "adjacent", True),
    Case("motorcycle_edge_encroach", "motorcycle", "edge", True),
    Case("motorcycle_deep_encroach", "motorcycle", "deep", True),
    Case("moped_edge_encroach", "moped", "edge", True),
    Case("motorcycle_stationary_edge", "motorcycle", "edge", False),
)


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def xy(value, name: str) -> tuple[float, float]:
    require(isinstance(value, (list, tuple)) and len(value) == 2 and
            all(type(x) in (int, float) and isfinite(x) for x in value),
            name + " coordinate missing")
    return float(value[0]), float(value[1])


def dot(a, b) -> float:
    return a[0] * b[0] + a[1] * b[1]


def lateral(site: Mapping, point) -> float:
    center = xy(site["protected_lane_center_xy"], "protected lane center")
    normal = xy(site["lane_lateral_unit_xy"], "lane normal")
    p = xy(point, "actor position")
    return dot((p[0] - center[0], p[1] - center[1]), normal)


def validate_site(site: Mapping) -> dict:
    require(site.get("cell_id") == "C147339" and site.get("layout") == "one_way_multilane",
            "wrong protected-lane cell")
    for field in ("map_source_sha256", "lane_source_sha256", "highway_source_sha256",
                  "public_maintenance_source_sha256", "public_vehicle_access_source_sha256",
                  "ego_blueprint_source_sha256", "motorcycle_class_source_sha256",
                  "moped_class_source_sha256", "motorcycle_exclusion_review_sha256"):
        require(bool(site.get(field)), "original source missing: " + field)
    require(site.get("same_one_way_direction") is True and
            site.get("lane_ids", {}).get("protected") and
            site.get("lane_ids", {}).get("adjacent") and
            site["lane_ids"]["protected"] != site["lane_ids"]["adjacent"],
            "two distinct one-way lanes missing")
    width = site.get("protected_lane_width_m")
    ego_width = site.get("ego_width_m")
    protected_width = site.get("protected_width_m")
    require(all(type(value) in (int, float) and isfinite(value) and value > 0
                for value in (width, ego_width, protected_width)) and
            width > protected_width and width > ego_width,
            "sourced lane/vehicle widths missing")
    normal = xy(site.get("lane_lateral_unit_xy"), "lane normal")
    require(abs(hypot(*normal) - 1) < .001, "lane normal not unit length")
    routes = site.get("ego_routes", {})
    intrusion = {}
    for name in ("adjacent", "edge", "deep"):
        route = routes.get(name, {})
        points = route.get("waypoints_xy")
        require(route.get("source_sha256") and isinstance(points, list) and len(points) >= 2,
                "sourced ego route missing: " + name)
        for point in points:
            xy(point, "ego route waypoint")
        target_lateral = abs(lateral(site, points[-1]))
        intrusion[name] = max(0.0, width / 2 + ego_width / 2 - target_lateral)
    require(intrusion["adjacent"] == 0 and
            0 < intrusion["edge"] < intrusion["deep"],
            "ego routes do not isolate lane intrusion")
    protected_route = site.get("protected_route", {})
    points = protected_route.get("waypoints_xy")
    require(protected_route.get("source_sha256") and isinstance(points, list) and len(points) >= 2,
            "sourced protected route missing")
    require(all(abs(lateral(site, point)) <= (width - protected_width) / 2
                for point in points), "protected route leaves occupied lane")
    return {"planned_intrusion_m": intrusion, "protected_lane_half_width_m": width / 2}


def construct(adapter, site: Mapping, case: Case) -> dict:
    """Create separately identified road users and request source-defined paths."""
    geometry = validate_site(site)
    require(case in CASES, "unknown exact lane-use case")
    owned = []
    try:
        protected = adapter.spawn_vehicle(site["protected_route"]["waypoints_xy"][0],
                                          role="protected", kind=case.protected_kind)
        require(protected is not None, "protected vehicle spawn failed")
        owned.append(protected)
        ego_route = site["ego_routes"][case.ego_path]["waypoints_xy"]
        ego = adapter.spawn_vehicle(ego_route[0], role="ego", kind="motor_vehicle")
        require(ego is not None, "ego motor vehicle spawn failed")
        owned.append(ego)
        adapter.set_route(protected, site["protected_route"]["waypoints_xy"],
                          target_speed_mps=6 if case.protected_driven else 0)
        adapter.set_route(ego, ego_route, target_speed_mps=7)
        return {"case_id": case.case_id, "ego": ego, "protected": protected,
                "owned": tuple(owned), "requested_protected_kind": case.protected_kind,
                "requested_protected_driven": case.protected_driven,
                "planned_intrusion_m": geometry["planned_intrusion_m"][case.ego_path],
                "full_use_judgment": "unresolved"}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_original(rows: list[Mapping], site: Mapping, case: Case) -> dict:
    """Measure body intrusion in original synchronized actor rows."""
    validate_site(site)
    require(case in CASES and len(rows) == 900, "exact case or original 900-frame history missing")
    first = rows[0].get("original_frame")
    require(type(first) is int, "original frame identity missing")
    ids = None
    intrusions = []
    protected_speeds = []
    center_distances = []
    for i, row in enumerate(rows):
        require(row.get("original_frame") == first + i and
                type(row.get("time_s")) in (int, float) and
                abs(row["time_s"] - rows[0]["time_s"] - i / 20) <= .005,
                "original frame/time join invalid")
        for name in ("source_sha256", "ego_pose_sha256", "protected_pose_sha256"):
            require(bool(row.get(name)), "original actor source missing: " + name)
        for name in ("map_source_sha256", "lane_source_sha256", "highway_source_sha256"):
            require(row.get(name) == site[name], "original site source changed: " + name)
        pair = (row.get("ego_id"), row.get("protected_id"))
        require(all(pair) and pair[0] != pair[1], "distinct original vehicles missing")
        if ids is None:
            ids = pair
        require(pair == ids, "original actor identity changed")
        require(row.get("protected_kind") == case.protected_kind and
                row.get("ego_kind") == "motor_vehicle", "original vehicle classification changed")
        speed = row.get("protected_speed_mps")
        require(type(speed) in (int, float) and isfinite(speed) and speed >= 0,
                "original protected motion missing")
        protected_speeds.append(speed)
        ego = xy(row.get("ego_xy"), "original ego")
        protected = xy(row.get("protected_xy"), "original protected vehicle")
        center_distances.append(hypot(ego[0] - protected[0], ego[1] - protected[1]))
        intrusions.append(max(0.0, site["protected_lane_width_m"] / 2 +
                              site["ego_width_m"] / 2 - abs(lateral(site, ego))))
        require(abs(lateral(site, protected)) <=
                (site["protected_lane_width_m"] - site["protected_width_m"]) / 2,
                "protected vehicle left occupied lane")
    require((max(protected_speeds) > .1) == case.protected_driven,
            "original protected motion differs from case")
    terminal_intrusion = sum(intrusions[-20:]) / 20
    if case.ego_path == "adjacent":
        require(terminal_intrusion == 0, "original adjacent case intrudes into lane")
    else:
        require(terminal_intrusion > 0, "original ego did not enter occupied lane")
    return {"case_id": case.case_id, "frame_count": 900,
            "first_original_frame": first, "last_original_frame": first + 899,
            "protected_kind": case.protected_kind,
            "protected_driven_observed": max(protected_speeds) > .1,
            "maximum_ego_body_intrusion_m": max(intrusions),
            "terminal_mean_ego_body_intrusion_m": terminal_intrusion,
            "minimum_vehicle_center_distance_m": min(center_distances),
            "full_use_judgment": "unresolved", "legal_judgment": None}
