"""Source-gated narrow-road parking relationship and lazy Native construction.

Offsets are engineering geometry checks, not legal definitions of highway side.
The actual stop/stand/park activity and any statutory exception require original
actor and context evidence after capture.
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
    Case("side_park", "park", "highway_side", None),
    Case("behind_park", "park", "behind_edge_vehicle", None),
    Case("side_stop", "stop", "highway_side", None),
    Case("side_stand", "stand", "highway_side", None),
    Case("side_conflict", "stop", "highway_side", "necessary_avoid_traffic_conflict"),
    Case("side_law", "stop", "highway_side", "compliance_with_law"),
    Case("side_police", "stop", "highway_side", "police_direction"),
    Case("side_device", "stop", "highway_side", "official_device_direction"),
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _xy(point, name: str) -> tuple[float, float]:
    require(isinstance(point, (list, tuple)) and len(point) == 2 and
            all(type(v) in (int, float) and isfinite(v) for v in point),
            name + " coordinate missing")
    return float(point[0]), float(point[1])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def validate_site(site: Mapping) -> dict:
    """Require surveyed map/edge, two vehicle targets and a realizable route."""
    require(site.get("cell_id") == "C135705", "wrong narrow-road cell")
    require(site.get("highway_source_sha256") and site.get("map_source_sha256") and
            site.get("edge_source_sha256"), "original highway or edge source missing")
    require(site.get("layout") == "narrow_road" and site.get("highway_status") == "source_reviewed",
            "highway/narrow-road status not sourced")
    edge = _xy(site.get("edge_point_xy"), "edge")
    inward = _xy(site.get("roadward_unit_xy"), "roadward normal")
    require(abs(hypot(*inward) - 1) < .001, "roadward normal not unit length")
    tangent = (-inward[1], inward[0])
    curb = _xy(site.get("edge_vehicle_xy"), "edge vehicle")
    side = _xy(site.get("ego_side_xy"), "highway-side target")
    behind = _xy(site.get("ego_behind_xy"), "behind target")
    approach = _xy(site.get("ego_approach_xy"), "approach")
    lateral = lambda p: _dot((p[0] - edge[0], p[1] - edge[1]), inward)
    along = lambda p: _dot((p[0] - curb[0], p[1] - curb[1]), tangent)
    require(0 <= lateral(curb) <= 2.5, "edge vehicle not near surveyed edge")
    require(lateral(side) > lateral(curb) + .5, "side target is not highway side")
    require(abs(lateral(behind) - lateral(curb)) < .5 and abs(along(behind)) > 5,
            "behind target does not isolate longitudinal position")
    require(abs(along(side)) < 5, "side target not alongside edge vehicle")
    route = site.get("approach_route_xy")
    require(isinstance(route, list) and len(route) >= 2 and
            _xy(route[0], "route start") == approach and
            all(_xy(point, "route waypoint") for point in route),
            "sourced approach route missing")
    require(site.get("approach_route_source_sha256") and
            site.get("ego_blueprint_source_sha256") and
            site.get("edge_blueprint_source_sha256"), "route or vehicle blueprint source missing")
    return {"edge_lateral_m": lateral(curb), "side_lateral_m": lateral(side),
            "behind_lateral_m": lateral(behind), "side_along_m": along(side),
            "behind_along_m": along(behind)}


def construct(adapter, site: Mapping, case: Case) -> dict:
    """Spawn the edge vehicle and requested ego approach with owned cleanup."""
    geometry = validate_site(site)
    require(case in CASES, "unknown exact parking case")
    owned = []
    try:
        edge = adapter.spawn_vehicle(site["edge_vehicle_xy"], role="edge_vehicle")
        require(edge is not None, "edge vehicle spawn failed")
        owned.append(edge)
        adapter.hold_vehicle(edge, activity="park")
        ego = adapter.spawn_vehicle(site["ego_approach_xy"], role="ego")
        require(ego is not None, "ego vehicle spawn failed")
        owned.append(ego)
        target = site["ego_side_xy"] if case.endpoint == "highway_side" else site["ego_behind_xy"]
        adapter.set_route(ego, site["approach_route_xy"], target_xy=target)
        adapter.request_halt(ego, target_xy=target, activity=case.activity)
        return {"case_id": case.case_id, "ego": ego, "edge_vehicle": edge,
                "owned": tuple(owned), "requested_endpoint_xy": target,
                "requested_activity": case.activity,
                "exception_probe": case.exception_probe, "site_geometry": geometry,
                "legal_judgment": None}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_original(rows: list[Mapping], site: Mapping, case: Case) -> dict:
    """Measure original actor history; retain activity and exceptions unresolved."""
    validate_site(site)
    require(case in CASES, "unknown exact parking case")
    require(len(rows) == 900, "original 900-frame history missing")
    origin = _xy(site["edge_point_xy"], "edge")
    inward = _xy(site["roadward_unit_xy"], "roadward normal")
    tangent = (-inward[1], inward[0])
    first_frame = rows[0].get("original_frame")
    require(type(first_frame) is int, "original frame identity missing")
    ids = None
    lateral_offsets = []
    longitudinal_offsets = []
    ego_speeds = []
    exception_sources = set()
    for index, row in enumerate(rows):
        require(row.get("original_frame") == first_frame + index and
                type(row.get("time_s")) in (int, float) and
                abs(row["time_s"] - rows[0]["time_s"] - index / 20) <= .005,
                "original frame/time join invalid")
        for field in ("source_sha256", "highway_source_sha256", "map_source_sha256",
                      "edge_source_sha256", "ego_control_source_sha256"):
            require(bool(row.get(field)), "original source missing: " + field)
        require(row["highway_source_sha256"] == site["highway_source_sha256"] and
                row["map_source_sha256"] == site["map_source_sha256"] and
                row["edge_source_sha256"] == site["edge_source_sha256"],
                "original site source changed")
        pair = (row.get("ego_id"), row.get("edge_vehicle_id"))
        require(all(pair) and pair[0] != pair[1], "distinct original vehicles missing")
        if ids is None:
            ids = pair
        require(pair == ids, "original vehicle identity changed")
        ego = _xy(row.get("ego_xy"), "original ego")
        edge = _xy(row.get("edge_vehicle_xy"), "original edge vehicle")
        for name in ("ego_speed_mps", "edge_speed_mps"):
            speed = row.get(name)
            require(type(speed) in (int, float) and isfinite(speed) and speed >= 0,
                    "original speed missing: " + name)
        require(row["edge_speed_mps"] <= .1,
                "edge vehicle not stationary in original history")
        ego_speeds.append(row["ego_speed_mps"])
        lateral_offsets.append(_dot((ego[0] - edge[0], ego[1] - edge[1]), inward))
        longitudinal_offsets.append(_dot((ego[0] - edge[0], ego[1] - edge[1]), tangent))
        ref = row.get("exception_source_sha256")
        if ref:
            exception_sources.add(ref)
    require(max(ego_speeds[-20:]) <= .1, "ego did not complete requested halt")
    terminal_lateral = sum(lateral_offsets[-20:]) / 20
    terminal_longitudinal = sum(longitudinal_offsets[-20:]) / 20
    if case.endpoint == "highway_side":
        require(terminal_lateral > .5 and abs(terminal_longitudinal) < 5,
                "original ego did not occupy highway side")
    else:
        require(abs(terminal_lateral) < .5 and abs(terminal_longitudinal) > 5,
                "original ego did not occupy behind relationship")
    if case.exception_probe:
        require(exception_sources, "original exception context source missing")
    return {
        "case_id": case.case_id,
        "first_original_frame": first_frame, "last_original_frame": first_frame + 899,
        "frame_count": 900, "original_fps": 20,
        "ego_id": ids[0], "edge_vehicle_id": ids[1],
        "terminal_roadward_lateral_difference_m": terminal_lateral,
        "terminal_along_edge_difference_m": terminal_longitudinal,
        "edge_stationary_observed": True, "ego_halt_observed": True,
        "requested_activity": case.activity,
        "exception_source_sha256": sorted(exception_sources),
        "activity_judgment": "unresolved", "exception_judgment": "unresolved",
        "legal_judgment": None,
    }
