"""Source-gated access-aisle construction and original body-footprint audit.

Measured polygon overlap and activity history are physical/context evidence.
They do not decide the legal meaning of parking or aisle designation.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    case_id: str
    target: str
    requested_activity: str


CASES = (
    Case("aisle_full_park", "aisle_full", "park"),
    Case("aisle_partial_park", "aisle_partial", "park"),
    Case("adjacent_space_park", "adjacent_space", "park"),
    Case("aisle_loading_stop", "aisle_full", "loading_stop"),
    Case("aisle_travel", "aisle_full", "travel"),
)


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def point(value, name: str) -> tuple[float, float]:
    require(isinstance(value, (list, tuple)) and len(value) == 2 and
            all(type(x) in (int, float) and isfinite(x) for x in value),
            name + " coordinate missing")
    return float(value[0]), float(value[1])


def area(poly) -> float:
    return abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] -
                   poly[(i + 1) % len(poly)][0] * poly[i][1]
                   for i in range(len(poly)))) / 2


def convex(poly, name: str) -> list[tuple[float, float]]:
    require(isinstance(poly, list) and len(poly) >= 3, name + " polygon missing")
    points = [point(v, name) for v in poly]
    signs = []
    for i in range(len(points)):
        a, b, c = points[i], points[(i + 1) % len(points)], points[(i + 2) % len(points)]
        cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if abs(cross) > 1e-8:
            signs.append(cross > 0)
    require(area(points) > 0 and signs and len(set(signs)) == 1,
            name + " polygon must be convex")
    if not signs[0]:
        points.reverse()
    return points


def intersection_area(subject, clip) -> float:
    """Convex Sutherland-Hodgman clipping in original map coordinates."""
    output = convex(subject, "vehicle footprint")
    boundary = convex(clip, "access aisle")
    for i, a in enumerate(boundary):
        b = boundary[(i + 1) % len(boundary)]
        def side(p):
            return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
        previous = output
        output = []
        if not previous:
            break
        for j, current in enumerate(previous):
            prior = previous[j - 1]
            sc, sp = side(current), side(prior)
            if (sc >= 0) != (sp >= 0):
                fraction = sp / (sp - sc)
                output.append((prior[0] + fraction * (current[0] - prior[0]),
                               prior[1] + fraction * (current[1] - prior[1])))
            if sc >= 0:
                output.append(current)
    return area(output) if len(output) >= 3 else 0.0


def validate_site(site: Mapping) -> dict:
    require(site.get("cell_id") == "C150072" and site.get("actor") == "motor_vehicle_driver",
            "wrong access-aisle cell")
    for field in ("jurisdiction_source_sha256", "map_source_sha256", "aisle_marking_source_sha256",
                  "adjacent_designated_space_source_sha256", "accessible_route_source_sha256",
                  "ingress_egress_design_source_sha256", "vehicle_blueprint_source_sha256"):
        require(bool(site.get(field)), "original access-aisle source missing: " + field)
    if site.get("designation_relies_on_135a"):
        require(all(site.get(field) for field in
                    ("access_symbol_source_sha256", "fine_wording_source_sha256",
                     "sign_bottom_height_source_sha256")),
                "11.52.135(A) sign/designation source missing")
    aisle = convex(site.get("aisle_polygon_xy"), "access aisle")
    adjacent = convex(site.get("adjacent_space_polygon_xy"), "adjacent designated space")
    require(intersection_area(aisle, adjacent) == 0,
            "aisle and adjacent designated space overlap")
    route = site.get("approach_route_xy")
    require(site.get("approach_route_source_sha256") and isinstance(route, list) and
            len(route) >= 2, "one-way parking approach missing")
    for waypoint in route:
        point(waypoint, "approach waypoint")
    footprints = site.get("target_footprints", {})
    actual = {}
    for target in ("aisle_full", "aisle_partial", "adjacent_space"):
        packet = footprints.get(target, {})
        require(packet.get("source_sha256"), "target footprint source missing: " + target)
        footprint = convex(packet.get("polygon_xy"), target)
        actual[target] = intersection_area(footprint, aisle)
    require(actual["aisle_full"] > actual["aisle_partial"] > 0 and
            actual["adjacent_space"] == 0,
            "target footprints do not isolate aisle placement")
    return {"planned_aisle_overlap_m2": actual}


def construct(adapter, site: Mapping, case: Case) -> dict:
    """Request a sourced approach and activity; preserve later physical review."""
    geometry = validate_site(site)
    require(case in CASES, "unknown exact access-aisle case")
    owned = []
    try:
        ego = adapter.spawn_vehicle(site["approach_route_xy"][0], role="ego")
        require(ego is not None, "ego vehicle spawn failed")
        owned.append(ego)
        target = site["target_footprints"][case.target]["polygon_xy"]
        adapter.set_parking_route(ego, site["approach_route_xy"], target_footprint=target)
        adapter.request_activity(ego, case.requested_activity)
        return {"case_id": case.case_id, "ego": ego, "owned": tuple(owned),
                "target_footprint": target, "requested_activity": case.requested_activity,
                "planned_aisle_overlap_m2": geometry["planned_aisle_overlap_m2"][case.target],
                "legal_judgment": None}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def measure_original(rows: list[Mapping], site: Mapping, case: Case) -> dict:
    """Recompute aisle overlap from 900 original vehicle-body polygons."""
    validate_site(site)
    require(case in CASES and len(rows) == 900, "exact case or original 900 frames missing")
    first = rows[0].get("original_frame")
    require(type(first) is int, "original frame identity missing")
    identity = None
    overlaps = []
    speeds = []
    activity_sources = set()
    for i, row in enumerate(rows):
        require(row.get("original_frame") == first + i and
                type(row.get("time_s")) in (int, float) and
                abs(row["time_s"] - rows[0]["time_s"] - i / 20) <= .005,
                "original frame/time join invalid")
        for name in ("source_sha256", "body_geometry_source_sha256", "control_source_sha256",
                     "activity_source_sha256"):
            require(bool(row.get(name)), "original source missing: " + name)
        require(row.get("map_source_sha256") == site["map_source_sha256"] and
                row.get("aisle_marking_source_sha256") == site["aisle_marking_source_sha256"],
                "original aisle site source changed")
        ego_id = row.get("ego_id")
        require(bool(ego_id), "original ego identity missing")
        if identity is None:
            identity = ego_id
        require(ego_id == identity, "original ego identity changed")
        speed = row.get("ego_speed_mps")
        require(type(speed) in (int, float) and isfinite(speed) and speed >= 0,
                "original ego speed missing")
        speeds.append(speed)
        require(row.get("observed_activity") in ("approach", "park", "loading_stop", "travel"),
                "original activity readback missing")
        activity_sources.add(row["activity_source_sha256"])
        overlaps.append(intersection_area(row.get("vehicle_body_polygon_xy"),
                                          site["aisle_polygon_xy"]))
    terminal = sum(overlaps[-20:]) / 20
    require(all(row["observed_activity"] == case.requested_activity for row in rows[-20:]),
            "observed terminal activity differs from case")
    if case.target == "adjacent_space":
        require(terminal == 0, "adjacent-space case overlaps access aisle")
    else:
        require(terminal > 0, "original vehicle did not occupy access aisle")
    if case.requested_activity != "travel":
        require(max(speeds[-20:]) <= .1, "original vehicle did not remain stopped")
    else:
        require(max(speeds) > .1, "original travel activity absent")
    return {"case_id": case.case_id, "frame_count": 900,
            "first_original_frame": first, "last_original_frame": first + 899,
            "maximum_aisle_body_overlap_m2": max(overlaps),
            "terminal_mean_aisle_body_overlap_m2": terminal,
            "terminal_max_speed_mps": max(speeds[-20:]),
            "observed_activity": case.requested_activity,
            "activity_source_sha256": sorted(activity_sources),
            "parking_judgment": "unresolved", "legal_judgment": None}
