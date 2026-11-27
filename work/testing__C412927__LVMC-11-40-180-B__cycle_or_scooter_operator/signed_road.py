"""Source-gated LVMC 11.40.180(B) roadway construction and observation.

Administrative prerequisites are external records. A rendered sign or a CARLA
trace cannot establish the Director's consultations or determination.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import hypot, isfinite
import json
from pathlib import Path


AID = "testing__C412927__LVMC-11-40-180-B__cycle_or_scooter_operator"
DEVICE_KINDS = ("bicycle", "electric_bicycle", "electric_scooter")
SOURCE_ROLES = (
    "municipal_jurisdiction", "native_map", "roadway_boundary",
    "device_specification", "operator_conduct", "sign_inventory",
    "director_sign_order", "city_traffic_engineer_consultation",
    "metropolitan_police_consultation", "director_traffic_flow_determination",
)


@dataclass(frozen=True)
class Case:
    suffix: str
    device_kind: str
    conduct: str
    sign_state: str
    movement: str
    extent: str


CASES = (
    Case("bicycle_disobey", "bicycle", "riding", "posted", "through", "within"),
    Case("bicycle_obey", "bicycle", "riding", "posted", "turn_away", "before"),
    Case("electric_bicycle_disobey", "electric_bicycle", "riding", "posted", "through", "within"),
    Case("electric_scooter_disobey", "electric_scooter", "riding", "posted", "through", "within"),
    Case("bicycle_sign_absent", "bicycle", "riding", "absent", "through", "within"),
    Case("bicycle_outside_extent", "bicycle", "riding", "posted", "through", "outside"),
    Case("bicycle_walking", "bicycle", "walking", "posted", "through", "within"),
)
BY_SUFFIX = {case.suffix: case for case in CASES}


def need(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def number(value: object) -> bool:
    return type(value) in (int, float) and isfinite(value)


def point(value: object) -> bool:
    return isinstance(value, (list, tuple)) and len(value) == 2 and all(number(x) for x in value)


def polygon(vertices: object) -> list:
    need(isinstance(vertices, list) and len(vertices) >= 3 and all(point(x) for x in vertices),
         "reviewed original roadway polygon missing")
    area = sum(vertices[i][0] * vertices[(i + 1) % len(vertices)][1]
               - vertices[(i + 1) % len(vertices)][0] * vertices[i][1]
               for i in range(len(vertices)))
    need(abs(area) > 1e-6, "reviewed original roadway polygon degenerate")
    return vertices


def inside(position: list, vertices: list) -> bool:
    vertices = polygon(vertices)
    signs = []
    for i, start in enumerate(vertices):
        end = vertices[(i + 1) % len(vertices)]
        signs.append((end[0] - start[0]) * (position[1] - start[1])
                     - (end[1] - start[1]) * (position[0] - start[0]))
    return all(s >= -1e-8 for s in signs) or all(s <= 1e-8 for s in signs)


def original_site(packet_path: str | Path, case: Case) -> dict:
    """Reject an unreviewed or incomplete site packet before CARLA import."""
    packet_path = Path(packet_path).resolve()
    site = json.loads(packet_path.read_text(encoding="utf-8"))
    need(site.get("format") == "reviewed-lvmc-signed-road-v1"
         and site.get("source_kind") == "original_reviewed"
         and site.get("diagnostic_fixture") is False
         and site.get("case_id") == AID + "__" + case.suffix
         and site.get("reviewer"), "reviewed original signed roadway site required")
    sources = site.get("sources")
    need(isinstance(sources, dict), "reviewed original source inventory missing")
    for role in SOURCE_ROLES:
        item = sources.get(role)
        need(isinstance(item, dict) and item.get("path") and item.get("sha256"),
             "original source missing: " + role)
        candidate = packet_path.parent / item["path"]
        source = candidate.resolve()
        need(not candidate.is_symlink() and source.is_relative_to(packet_path.parent)
             and source.is_file() and sha256(source.read_bytes()).hexdigest() == item["sha256"]
             and site.get(role + "_source_sha256") == item["sha256"],
             "original source invalid: " + role)
    need(site.get("municipality") == "Las Vegas" and site.get("map_name")
         and site.get("map_opendrive_sha256"), "reviewed city and Native map identity missing")
    road = polygon(site.get("roadway_polygon_xy"))
    route = site.get("ego_route_xy")
    need(isinstance(route, list) and len(route) >= 2 and all(point(p) for p in route)
         and all(inside(p, road) for p in route)
         and hypot(route[-1][0] - route[0][0], route[-1][1] - route[0][1]) >= 5,
         "reviewed original roadway route missing")
    if case.movement == "turn_away":
        need(len(route) >= 3 and abs(route[-1][1] - route[0][1]) >= 1.5,
             "reviewed obeying route must turn away before signed boundary")
    device = site.get("device")
    need(isinstance(device, dict) and device.get("kind") == case.device_kind
         and device.get("source_verified") is True and device.get("blueprint_id")
         and device.get("device_id"), "reviewed covered device qualification missing")
    conduct = site.get("operator_conduct")
    need(isinstance(conduct, dict) and conduct.get("kind") == case.conduct
         and conduct.get("operator_id") and conduct.get("device_id") == device["device_id"],
         "reviewed riding or walking conduct source missing")
    if case.conduct == "walking":
        need(conduct.get("walker_blueprint_id", "").startswith("walker.pedestrian."),
             "reviewed walking operator asset missing")
    sign = site.get("restriction_sign")
    need(isinstance(sign, dict) and bool(sign.get("in_place")) is (case.sign_state == "posted")
         and point(sign.get("position_xy")) and sign.get("sign_id")
         and sign.get("governed_surface") == "roadway"
         and sign.get("categories") == list(DEVICE_KINDS)
         and sign.get("source_sha256") == sources["sign_inventory"]["sha256"],
         "reviewed signed roadway restriction missing")
    bounds = sign.get("station_bounds_m")
    station = site.get("longitudinal_station_m")
    need(isinstance(bounds, list) and len(bounds) == 2 and all(number(x) for x in bounds)
         and bounds[0] < bounds[1] and isinstance(station, dict)
         and all(number(station.get(k)) for k in ("route_start", "route_end"))
         and station["route_start"] < station["route_end"],
         "reviewed sign extent or route station missing")
    if case.extent == "within":
        need(station["route_start"] < bounds[0] < station["route_end"] <= bounds[1],
             "reviewed route does not enter signed extent")
    elif case.extent == "before":
        need(station["route_end"] < bounds[0], "obeying route enters prohibited extent")
    else:
        need(station["route_start"] > bounds[1], "outside route enters signed extent")
    need(site.get("administrative_record") == {
        "director_erected_sign": True,
        "city_traffic_engineer_consulted": True,
        "metropolitan_police_consulted": True,
        "director_determined_traffic_flow_impediment": True,
    }, "reviewed Director order, both consultations and traffic-flow determination required")
    need(site.get("legal_verdict") is None, "legal outcome cannot be supplied by site packet")
    return site


def construct(adapter: object, site: dict, case: Case) -> dict:
    need(case in CASES, "unknown exact signed roadway case")
    route = site["ego_route_xy"]
    device = adapter.spawn_device(route[0], site["device"]["blueprint_id"])
    adapter.set_route(device, route)
    adapter.set_conduct(device, case.conduct, site["operator_conduct"]["operator_id"])
    adapter.set_site(device, site["roadway_polygon_xy"], site["restriction_sign"])
    return {"device": device, "case_id": AID + "__" + case.suffix, "legal_verdict": None}


def measure_original(rows: list[dict], site: dict, case: Case) -> dict:
    need(rows and all(type(row.get("original_frame")) is int and number(row.get("time_s"))
                      and point(row.get("position_xy"))
                      and row.get("device_id") == site["device"]["device_id"]
                      and row.get("operator_id") == site["operator_conduct"]["operator_id"]
                      and row.get("device_source_sha256") == site["device_specification_source_sha256"]
                      for row in rows), "original device, frame or conduct source missing")
    first_frame, first_time = rows[0]["original_frame"], rows[0]["time_s"]
    for index, row in enumerate(rows):
        need(row["original_frame"] == first_frame + index
             and abs(row["time_s"] - first_time - index / 20) < .006,
             "original frame/time join changed")
    return {"case_id": AID + "__" + case.suffix, "frame_count": len(rows),
            "roadway_center_frames": sum(inside(row["position_xy"], site["roadway_polygon_xy"])
                                         for row in rows),
            "device_kind": site["device"]["kind"],
            "conduct_from_source": site["operator_conduct"]["kind"],
            "sign_in_place": site["restriction_sign"]["in_place"],
            "sign_station_bounds_m": site["restriction_sign"]["station_bounds_m"],
            "route_station_survey": site["longitudinal_station_m"],
            "administrative_source_hashes": {
                role: site[role + "_source_sha256"] for role in SOURCE_ROLES[6:]},
            "legal_judgment": None}
