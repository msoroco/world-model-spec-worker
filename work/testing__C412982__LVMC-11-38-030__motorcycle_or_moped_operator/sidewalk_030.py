"""Original-source geometry and conduct for LVMC 11.38.030.

Municipal jurisdiction and vehicle classification require reviewed original sources.
This module records physical facts only; it cannot decide a legal violation.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import hypot, isfinite
import json
from pathlib import Path

AID = "testing__C412982__LVMC-11-38-030__motorcycle_or_moped_operator"
LAW = "LVMC-11-38-030"
SOURCE_ROLES = ("municipal_boundary", "native_map", "sidewalk_boundary",
                "sidewalk_pedestrian_purpose", "device_specification",
                "operator_conduct")


@dataclass(frozen=True)
class Case:
    suffix: str
    device_kind: str
    conduct: str
    surface: str
    side: str
    municipality: str


CASES = (
    Case("motorcycle_riding_sidewalk_north", "motorcycle", "riding", "sidewalk", "north", "Las Vegas"),
    Case("motorcycle_riding_sidewalk_south", "motorcycle", "riding", "sidewalk", "south", "Las Vegas"),
    Case("motor_scooter_riding_sidewalk", "motor_scooter", "riding", "sidewalk", "north", "Las Vegas"),
    Case("motorcycle_riding_road", "motorcycle", "riding", "road", "north", "Las Vegas"),
    Case("motorcycle_walking_sidewalk", "motorcycle", "walking", "sidewalk", "north", "Las Vegas"),
    Case("motorcycle_riding_outside_city", "motorcycle", "riding", "sidewalk", "north", "North Las Vegas"),
)
BY_SUFFIX = {case.suffix: case for case in CASES}


def need(value, message):
    if not value:
        raise ValueError(message)


def point(value):
    return (isinstance(value, (list, tuple)) and len(value) == 2 and
            all(type(x) in (int, float) and isfinite(x) for x in value))


def polygon(value):
    need(isinstance(value, list) and len(value) >= 3 and all(point(x) for x in value),
         "original sidewalk polygon absent")
    area = sum(value[i][0] * value[(i + 1) % len(value)][1] -
               value[(i + 1) % len(value)][0] * value[i][1]
               for i in range(len(value))) / 2
    need(abs(area) > 1e-6, "original sidewalk polygon has no area")
    return value


def inside(point_xy, boundary):
    vertices = polygon(boundary)
    signs = []
    for i, start in enumerate(vertices):
        end = vertices[(i + 1) % len(vertices)]
        signs.append((end[0] - start[0]) * (point_xy[1] - start[1]) -
                     (end[1] - start[1]) * (point_xy[0] - start[0]))
    return all(x >= -1e-8 for x in signs) or all(x <= 1e-8 for x in signs)


def overlaps(first, second):
    """Convex polygon intersection, including crossed edges and containment."""
    first, second = polygon(first), polygon(second)
    if any(inside(p, second) for p in first) or any(inside(p, first) for p in second):
        return True

    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def on_segment(a, b, p):
        return (min(a[0], b[0]) - 1e-8 <= p[0] <= max(a[0], b[0]) + 1e-8 and
                min(a[1], b[1]) - 1e-8 <= p[1] <= max(a[1], b[1]) + 1e-8)

    for i, a in enumerate(first):
        b = first[(i + 1) % len(first)]
        for j, c in enumerate(second):
            d = second[(j + 1) % len(second)]
            ab_c, ab_d = cross(a, b, c), cross(a, b, d)
            cd_a, cd_b = cross(c, d, a), cross(c, d, b)
            if ab_c * ab_d < 0 and cd_a * cd_b < 0:
                return True
            if ((abs(ab_c) <= 1e-8 and on_segment(a, b, c)) or
                    (abs(ab_d) <= 1e-8 and on_segment(a, b, d)) or
                    (abs(cd_a) <= 1e-8 and on_segment(c, d, a)) or
                    (abs(cd_b) <= 1e-8 and on_segment(c, d, b))):
                return True
    return False


def original_site(packet_path, case):
    """Reject fixture or unreviewed site before CARLA import."""
    packet_path = Path(packet_path).resolve()
    site = json.loads(packet_path.read_text(encoding="utf-8"))
    need(site.get("format") == "reviewed-lvmc-sidewalk-v1" and
         site.get("source_kind") == "original_reviewed" and
         site.get("diagnostic_fixture") is False and site.get("reviewer") and
         site.get("case_id") == AID + "__" + case.suffix,
         "reviewed original City sidewalk source required")
    sources = site.get("sources")
    need(isinstance(sources, dict), "original source inventory absent")
    for role in SOURCE_ROLES:
        entry = sources.get(role)
        need(isinstance(entry, dict) and entry.get("path") and entry.get("sha256"),
             "original source missing: " + role)
        relative = Path(entry["path"])
        path = packet_path.parent / relative
        resolved = path.resolve()
        need(not relative.is_absolute() and not path.is_symlink() and
             resolved.is_relative_to(packet_path.parent) and resolved.is_file() and
             sha256(resolved.read_bytes()).hexdigest() == entry["sha256"] and
             site.get(role + "_source_sha256") == entry["sha256"],
             "original source invalid: " + role)
    need(site.get("municipality") == case.municipality,
         "reviewed municipality differs from selected case")
    need(site.get("map_name") and site.get("map_opendrive_sha256"),
         "original map identity missing")
    need(site.get("sidewalk_pedestrian_purpose") is True,
         "reviewed pedestrian sidewalk purpose missing")
    for side in ("north", "south"):
        polygon(site.get("sidewalk_polygons_xy", {}).get(side))
    polygon(site.get("road_polygon_xy"))
    route = site.get("ego_route_xy")
    need(isinstance(route, list) and len(route) >= 2 and all(point(p) for p in route),
         "reviewed original ego route missing")
    need(hypot(route[-1][0] - route[0][0], route[-1][1] - route[0][1]) >= 5,
         "reviewed route too short to establish travel")
    surface = site["road_polygon_xy"] if case.surface == "road" else site["sidewalk_polygons_xy"][case.side]
    need(all(inside(p, surface) for p in route),
         "original route does not occupy selected surface")
    device = site.get("device")
    need(isinstance(device, dict) and device.get("kind") == case.device_kind and
         device.get("source_verified") is True and device.get("blueprint_id") and
         device.get("device_id"), "original device qualification missing")
    conduct = site.get("operator_conduct")
    need(isinstance(conduct, dict) and conduct.get("kind") == case.conduct and
         conduct.get("operator_id") and conduct.get("device_id") == device["device_id"],
         "original mounted riding versus walking source missing")
    if case.conduct == "walking":
        need(conduct.get("walker_blueprint_id", "").startswith("walker.pedestrian."),
             "original pedestrian asset for walking device missing")
    need(site.get("legal_verdict") is None, "source packet cannot prescribe legal verdict")
    return site


def construct(adapter, site, case):
    need(case in CASES, "unknown exact City sidewalk case")
    route = site["ego_route_xy"]
    ego = adapter.spawn_device(route[0], site["device"]["blueprint_id"])
    adapter.set_route(ego, route)
    adapter.set_conduct(ego, case.conduct, site["operator_conduct"]["operator_id"])
    adapter.set_site(ego, site["sidewalk_polygons_xy"], site["road_polygon_xy"],
                     site["municipality"])
    return {"device": ego, "case_id": AID + "__" + case.suffix, "legal_verdict": None}


def measure_original(rows, site, case):
    need(rows and all(type(row.get("original_frame")) is int and
                      type(row.get("time_s")) in (int, float) and
                      point(row.get("position_xy")) and
                      isinstance(row.get("body_polygon_xy"), list) and
                      len(row["body_polygon_xy"]) >= 3 and
                      row.get("mounted_riding_source") is (case.conduct == "riding") and
                      row.get("municipality_source_sha256") == site["municipal_boundary_source_sha256"] and
                      row.get("operator_source_sha256") == site["operator_conduct_source_sha256"] and
                      row.get("device_id") == site["device"]["device_id"] and
                      row.get("operator_id") == site["operator_conduct"]["operator_id"] and
                      row.get("device_source_sha256") == site["device_specification_source_sha256"]
                      for row in rows), "original frame, device or conduct source missing")
    first_frame, first_time = rows[0]["original_frame"], rows[0]["time_s"]
    for i, row in enumerate(rows):
        need(row["original_frame"] == first_frame + i and
             abs(row["time_s"] - first_time - i / 20) < .006,
             "original frame/time join changed")
    sidewalk = site["sidewalk_polygons_xy"][case.side]
    return {"case_id": AID + "__" + case.suffix,
            "frame_count": len(rows),
            "sidewalk_center_frames": sum(inside(row["position_xy"], sidewalk) for row in rows),
            "road_center_frames": sum(inside(row["position_xy"], site["road_polygon_xy"]) for row in rows),
            "sidewalk_body_overlap_frames": sum(overlaps(row["body_polygon_xy"], sidewalk) for row in rows),
            "road_body_overlap_frames": sum(overlaps(row["body_polygon_xy"], site["road_polygon_xy"]) for row in rows),
            "device_kind": site["device"]["kind"],
            "conduct_from_source": site["operator_conduct"]["kind"],
            "municipality_from_source": site["municipality"],
            "legal_judgment": None}
