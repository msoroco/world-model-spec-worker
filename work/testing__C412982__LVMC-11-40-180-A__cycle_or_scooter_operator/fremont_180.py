"""Source gated physical plan for LVMC 11.40.180(A).

The street name, municipal extent, device class and signs are original source
facts. This module measures geometry and conduct; it makes no legal verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import hypot, isfinite
import json
from pathlib import Path

AID = "testing__C412982__LVMC-11-40-180-A__cycle_or_scooter_operator"
DEVICE_KINDS = ("bicycle", "electric_bicycle", "electric_scooter")
SOURCE_ROLES = (
    "municipal_jurisdiction", "native_map", "fremont_street_identity",
    "main_street_intersection", "seventh_street_intersection",
    "sidewalk_north_boundary", "sidewalk_south_boundary",
    "sign_inventory", "device_specification", "operator_conduct",
)


@dataclass(frozen=True)
class Case:
    suffix: str
    device_kind: str
    conduct: str
    surface: str
    side: str
    extent: str
    sign_state: str = "posted"


CASES = (
    Case("bicycle_riding_north", "bicycle", "riding", "sidewalk", "north", "between"),
    Case("bicycle_riding_south", "bicycle", "riding", "sidewalk", "south", "between"),
    Case("electric_bicycle_riding_north", "electric_bicycle", "riding", "sidewalk", "north", "between"),
    Case("electric_scooter_riding_north", "electric_scooter", "riding", "sidewalk", "north", "between"),
    Case("bicycle_walking_north", "bicycle", "walking", "sidewalk", "north", "between"),
    Case("bicycle_riding_road", "bicycle", "riding", "road", "north", "between"),
    Case("bicycle_riding_before_main", "bicycle", "riding", "sidewalk", "north", "before_main"),
    Case("bicycle_riding_after_seventh", "bicycle", "riding", "sidewalk", "north", "after_seventh"),
    Case("bicycle_riding_sign_absent", "bicycle", "riding", "sidewalk", "north", "between", "absent"),
)
BY_SUFFIX = {case.suffix: case for case in CASES}


def need(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def number(value: object) -> bool:
    return type(value) in (int, float) and isfinite(value)


def point(value: object) -> bool:
    return isinstance(value, (list, tuple)) and len(value) == 2 and all(number(x) for x in value)


def polygon(value: object) -> list:
    need(isinstance(value, list) and len(value) >= 3 and all(point(p) for p in value),
         "original sidewalk polygon absent")
    area = sum(value[i][0] * value[(i + 1) % len(value)][1]
               - value[(i + 1) % len(value)][0] * value[i][1]
               for i in range(len(value))) / 2
    need(abs(area) > 1e-6, "original sidewalk polygon has no area")
    return value


def inside(point_xy: list, boundary: list) -> bool:
    """Convex polygon membership for original body and surveyed site geometry."""
    vertices = polygon(boundary)
    signs = []
    for index, start in enumerate(vertices):
        end = vertices[(index + 1) % len(vertices)]
        signs.append((end[0] - start[0]) * (point_xy[1] - start[1])
                     - (end[1] - start[1]) * (point_xy[0] - start[0]))
    return all(x >= -1e-8 for x in signs) or all(x <= 1e-8 for x in signs)


def original_site(packet_path: str | Path, case: Case) -> dict:
    """Reject a diagnostic or unreviewed packet before CARLA import or motion."""
    packet_path = Path(packet_path).resolve()
    site = json.loads(packet_path.read_text(encoding="utf-8"))
    need(site.get("format") == "reviewed-fremont-sidewalk-v1"
         and site.get("source_kind") == "original_reviewed"
         and site.get("diagnostic_fixture") is False
         and site.get("case_id") == AID + "__" + case.suffix
         and site.get("reviewer"), "reviewed original Fremont site required")
    sources = site.get("sources")
    need(isinstance(sources, dict), "original source inventory missing")
    for role in SOURCE_ROLES:
        entry = sources.get(role)
        need(isinstance(entry, dict) and entry.get("path") and entry.get("sha256"),
             "original source missing: " + role)
        candidate = packet_path.parent / entry["path"]
        source = candidate.resolve()
        need(not candidate.is_symlink() and source.is_relative_to(packet_path.parent)
             and source.is_file() and sha256(source.read_bytes()).hexdigest() == entry["sha256"]
             and site.get(role + "_source_sha256") == entry["sha256"],
             "original source invalid: " + role)
    need(site.get("municipality") == "Las Vegas" and site.get("street") == "Fremont Street"
         and site.get("from_cross_street") == "Main Street"
         and site.get("to_cross_street") == "Seventh Street",
         "reviewed Fremont Main-to-Seventh identity missing")
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
    station = site.get("longitudinal_station_m")
    need(isinstance(station, dict) and all(number(station.get(k)) for k in
         ("main", "seventh", "route_start", "route_end"))
         and station["main"] < station["seventh"],
         "original Main-to-Seventh station survey missing")
    lo, hi = station["route_start"], station["route_end"]
    need(lo <= hi, "original station route direction invalid")
    if case.extent == "between":
        need(station["main"] < lo < hi < station["seventh"],
             "reviewed route not strictly between Main and Seventh")
    elif case.extent == "before_main":
        need(hi < station["main"], "reviewed route not before Main")
    else:
        need(lo > station["seventh"], "reviewed route not after Seventh")
    polygon_for_route = (site["road_polygon_xy"] if case.surface == "road"
                         else site["sidewalk_polygons_xy"][case.side])
    need(all(inside(p, polygon_for_route) for p in route),
         "original route does not occupy selected surface")
    device = site.get("device")
    need(isinstance(device, dict) and device.get("kind") == case.device_kind
         and device.get("source_verified") is True and device.get("blueprint_id")
         and device.get("device_id"), "original covered device qualification missing")
    conduct = site.get("operator_conduct")
    need(isinstance(conduct, dict) and conduct.get("kind") == case.conduct
         and conduct.get("operator_id") and conduct.get("device_id") == device["device_id"],
         "original riding versus walking source missing")
    if case.conduct == "walking":
        need(conduct.get("walker_blueprint_id", "").startswith("walker.pedestrian."),
             "original pedestrian asset for walking device missing")
    signs = site.get("sign_inventory")
    need(isinstance(signs, list), "original area sign inventory missing")
    need(bool(signs) is (case.sign_state == "posted"),
         "original sign inventory differs from selected posting branch")
    for sign in signs:
        need(sign.get("sign_id") and point(sign.get("position_xy"))
             and sign.get("original_content_source_sha256") ==
             sources["sign_inventory"]["sha256"]
             and sign.get("categories") == list(DEVICE_KINDS),
             "original sign content and three covered categories missing")
    need(site.get("sign_coverage_judgment") is None
         and site.get("legal_verdict") is None,
         "area sign coverage and legal effect must stay unresolved")
    return site


def construct(adapter: object, site: dict, case: Case) -> dict:
    """Make real adapter calls; route and conduct remain reviewed originals."""
    need(case in CASES, "unknown exact Fremont case")
    route = site["ego_route_xy"]
    device = adapter.spawn_device(route[0], site["device"]["blueprint_id"])
    adapter.set_route(device, route)
    adapter.set_conduct(device, case.conduct, site["operator_conduct"]["operator_id"])
    adapter.set_site(device, site["sidewalk_polygons_xy"], site["road_polygon_xy"],
                     site["sign_inventory"])
    return {"device": device, "case_id": AID + "__" + case.suffix,
            "legal_verdict": None}


def measure_original(rows: list[dict], site: dict, case: Case) -> dict:
    """Retain full frame history and physical counts, without a legal cutoff."""
    need(rows and all(type(row.get("original_frame")) is int and
                      number(row.get("time_s")) and point(row.get("position_xy")) and
                      row.get("device_id") == site["device"]["device_id"] and
                      row.get("operator_id") == site["operator_conduct"]["operator_id"] and
                      row.get("device_source_sha256") == site["device_specification_source_sha256"]
                      for row in rows), "original frame, device or conduct source missing")
    first_frame, first_time = rows[0]["original_frame"], rows[0]["time_s"]
    for index, row in enumerate(rows):
        need(row["original_frame"] == first_frame + index
             and abs(row["time_s"] - first_time - index / 20) < .006,
             "original frame/time join changed")
    surface = site["sidewalk_polygons_xy"][case.side]
    return {"case_id": AID + "__" + case.suffix,
            "frame_count": len(rows),
            "sidewalk_center_frames": sum(inside(row["position_xy"], surface) for row in rows),
            "road_center_frames": sum(inside(row["position_xy"], site["road_polygon_xy"])
                                      for row in rows),
            "device_kind": site["device"]["kind"],
            "conduct_from_source": site["operator_conduct"]["kind"],
            "municipal_station_survey": site["longitudinal_station_m"],
            "signs_observed": site["sign_inventory"],
            "sign_coverage_judgment": None,
            "legal_judgment": None}
