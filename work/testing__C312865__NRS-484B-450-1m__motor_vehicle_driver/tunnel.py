"""Source-gated tunnel destination and original body-footprint measurement.

All distances are engineering observations. This module makes no legal finding
about traffic necessity, law compliance, police directions or device authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    case_id: str
    activity: str
    endpoint: str
    exception_probe: str | None


CASES = (
    Case("outside_stop", "stop", "outside_before_portal", None),
    Case("inside_stop", "stop", "inside_tunnel", None),
    Case("inside_stand", "stand", "inside_tunnel", None),
    Case("inside_park", "park", "inside_tunnel", None),
    Case("inside_conflict", "stop", "inside_tunnel", "necessary_avoid_traffic_conflict"),
    Case("inside_law", "stop", "inside_tunnel", "compliance_with_law"),
    Case("inside_police", "stop", "inside_tunnel", "police_direction"),
    Case("inside_device", "stop", "inside_tunnel", "official_device_direction"),
)


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def xy(value, label: str) -> tuple[float, float]:
    require(isinstance(value, (list, tuple)) and len(value) == 2 and
            all(type(v) in (int, float) and isfinite(v) for v in value),
            label + " coordinate missing")
    return float(value[0]), float(value[1])


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def inside_polygon(point, polygon) -> bool:
    """Boundary-inclusive point test against a reviewed tunnel footprint."""
    point = xy(point, "body vertex")
    ring = [xy(vertex, "tunnel boundary") for vertex in polygon]
    require(len(ring) >= 3, "tunnel boundary needs at least three vertices")
    x, y = point
    inside = False
    for a, b in zip(ring, ring[1:] + ring[:1]):
        cross = _cross(a, b, point)
        if abs(cross) <= 1e-8 and min(a[0], b[0]) - 1e-8 <= x <= max(a[0], b[0]) + 1e-8 and min(a[1], b[1]) - 1e-8 <= y <= max(a[1], b[1]) + 1e-8:
            return True
        if (a[1] > y) != (b[1] > y):
            intersect_x = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if intersect_x > x:
                inside = not inside
    return inside


def validate_site(site: Mapping) -> dict:
    require(site.get("cell_id") == "C312865" and site.get("layout") == "tunnel",
            "wrong reviewed tunnel cell")
    require(site.get("highway_status") == "source_reviewed_public_vehicular_use",
            "highway dedication and public vehicular use not reviewed")
    for key in ("map_source_sha256", "highway_source_sha256", "tunnel_source_sha256",
                "portal_source_sha256", "route_source_sha256", "ego_blueprint_source_sha256",
                "other_blueprint_source_sha256"):
        digest = site.get(key)
        require(isinstance(digest, str) and len(digest) == 64 and
                all(c in "0123456789abcdef" for c in digest),
                "reviewed source missing: " + key)
    polygon = site.get("tunnel_polygon_xy")
    require(isinstance(polygon, list) and len(polygon) >= 4,
            "reviewed tunnel interior boundary missing")
    ring = [xy(vertex, "tunnel boundary") for vertex in polygon]
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:] + ring[:1])) / 2
    require(abs(area) > 1, "tunnel boundary has no area")
    approach = xy(site.get("ego_approach_xy"), "ego approach")
    outside = xy(site.get("outside_target_xy"), "outside target")
    interior = xy(site.get("inside_target_xy"), "inside target")
    other = xy(site.get("other_vehicle_xy"), "other vehicle")
    route = site.get("approach_route_xy")
    require(isinstance(route, list) and len(route) >= 2 and
            xy(route[0], "route origin") == approach and
            all(xy(point, "route waypoint") for point in route),
            "source-reviewed approach route missing")
    other_route = site.get("other_vehicle_route_xy")
    require(isinstance(other_route, list) and len(other_route) >= 2 and
            xy(other_route[0], "other route origin") == other and
            all(xy(point, "other route waypoint") for point in other_route),
            "source-reviewed other-vehicle route missing")
    require(not inside_polygon(approach, ring) and not inside_polygon(outside, ring)
            and inside_polygon(interior, ring),
            "approach, outside and inside destinations do not isolate tunnel boundary")
    require(hypot(interior[0] - outside[0], interior[1] - outside[1]) > 5,
            "outside and inside destinations not separated")
    require(inside_polygon(other, ring), "other vehicle must be in reviewed tunnel")
    return {"tunnel_area_m2": abs(area), "approach_xy": approach,
            "outside_xy": outside, "inside_xy": interior, "other_xy": other}


def construct(adapter, site: Mapping, case: Case) -> dict:
    geometry = validate_site(site)
    require(case in CASES, "unknown exact tunnel case")
    owned = []
    try:
        other = adapter.spawn_vehicle(site["other_vehicle_xy"], role="other_vehicle")
        require(other is not None, "other vehicle spawn failed")
        owned.append(other)
        adapter.configure_other_vehicle(other, case.exception_probe,
                                        site["other_vehicle_route_xy"])
        ego = adapter.spawn_vehicle(site["ego_approach_xy"], role="ego")
        require(ego is not None, "ego vehicle spawn failed")
        owned.append(ego)
        target = site["inside_target_xy"] if case.endpoint == "inside_tunnel" else site["outside_target_xy"]
        adapter.set_route(ego, site["approach_route_xy"], target_xy=target)
        adapter.request_halt(ego, target_xy=target, activity=case.activity)
        return {"case_id": case.case_id, "owned": tuple(owned), "ego": ego,
                "other_vehicle": other, "requested_endpoint_xy": target,
                "requested_activity": case.activity, "exception_probe": case.exception_probe,
                "site_geometry": geometry, "legal_judgment": None}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_original(rows: list[Mapping], site: Mapping, case: Case) -> dict:
    validate_site(site)
    require(case in CASES and len(rows) == 900, "complete exact 900-frame tunnel history required")
    first_frame = rows[0].get("original_frame")
    first_time = rows[0].get("time_s")
    require(type(first_frame) is int and type(first_time) in (int, float),
            "original frame/time origin missing")
    identities = None
    inside_samples, speeds, exception_sources = [], [], set()
    for index, row in enumerate(rows):
        require(row.get("original_frame") == first_frame + index and
                type(row.get("time_s")) in (int, float) and isfinite(row["time_s"]) and
                abs(row["time_s"] - first_time - index / 20) <= .005,
                "original frame/time join invalid")
        for key in ("source_sha256", "map_source_sha256", "highway_source_sha256",
                    "tunnel_source_sha256", "portal_source_sha256", "ego_control_source_sha256"):
            require(bool(row.get(key)), "original source missing: " + key)
        for key in ("map_source_sha256", "highway_source_sha256",
                    "tunnel_source_sha256", "portal_source_sha256"):
            require(row[key] == site[key], "original site source changed: " + key)
        ids = (row.get("ego_id"), row.get("other_vehicle_id"))
        require(all(ids) and ids[0] != ids[1], "distinct original vehicles missing")
        if identities is None:
            identities = ids
        require(ids == identities, "original vehicle identity changed")
        vertices = row.get("ego_body_vertices_xy")
        require(isinstance(vertices, list) and len(vertices) >= 4,
                "original ego body footprint missing")
        inside_samples.append(all(inside_polygon(vertex, site["tunnel_polygon_xy"])
                                  for vertex in vertices))
        speed = row.get("ego_speed_mps")
        require(type(speed) in (int, float) and isfinite(speed) and speed >= 0,
                "original ego speed missing")
        speeds.append(speed)
        require(type(row.get("other_vehicle_speed_mps")) in (int, float) and
                isfinite(row["other_vehicle_speed_mps"]) and
                row["other_vehicle_speed_mps"] >= 0,
                "original other-vehicle motion missing")
        require(row.get("other_vehicle_purpose") in ("travel", "obstacle", "unknown"),
                "original other-vehicle purpose context missing")
        source = row.get("exception_source_sha256")
        if source:
            exception_sources.add(source)
    require(max(speeds[-20:]) <= .1, "requested tunnel halt did not complete")
    return {"case_id": case.case_id, "original_frames": len(rows),
            "terminal_body_inside_tunnel": all(inside_samples[-20:]),
            "terminal_body_outside_tunnel": not any(inside_samples[-20:]),
            "terminal_speed_mps": sum(speeds[-20:]) / 20,
            "original_exception_source_sha256": sorted(exception_sources),
            "requested_activity": case.activity,
            "observed_activity": rows[-1].get("activity_readback", "unresolved"),
            "traffic_conflict_necessity": "unresolved",
            "lawful_direction": "unresolved", "legal_judgment": "unresolved"}
