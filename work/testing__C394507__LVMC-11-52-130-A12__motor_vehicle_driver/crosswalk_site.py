"""Reviewed-site checks and bounded Native construction for LVMC 11.52.130(A)(12).

The site packet is operator supplied. Geometry and source seals are checked here;
this module does not decide whether a halt or an exception is lawful.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT_ID = "testing__C394507__LVMC-11-52-130-A12__motor_vehicle_driver"
SOURCE_NAMES = (
    "jurisdiction", "crosswalk_marking", "crosswalk_extent", "vehicle_identity",
    "responsible_person", "destination_purpose", "service_activity",
    "traffic_conflict", "law_compliance", "police_direction",
    "traffic_device_direction", "vehicle_route", "road_geometry",
)
CASE_CONTROLS = {
    "destination_inside_20ft": (5.9, "destination_stop", "none", True),
    "destination_exact_20ft": (6.096, "destination_stop", "none", True),
    "destination_outside_20ft": (6.3, "destination_stop", "none", True),
    "destination_stand_inside": (5.9, "destination_stand", "none", True),
    "destination_park_inside": (5.9, "destination_park", "none", True),
    "necessary_traffic_conflict": (5.9, "necessary_halt", "traffic_conflict", True),
    "police_direction": (5.9, "directed_halt", "police_direction", True),
    "device_direction": (5.9, "directed_halt", "device_direction", True),
    "unmarked_crossing": (5.9, "destination_stop", "none", False),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def point(value):
    return (isinstance(value, list) and len(value) == 2 and
            all(type(number) in (int, float) and math.isfinite(number) for number in value))


def load_site(site_path, expected_sha256, case_id):
    site_path = Path(site_path).resolve()
    require(site_path.is_file() and sha(site_path) == expected_sha256,
            "reviewed original site bytes changed")
    site = json.loads(site_path.read_text(encoding="utf-8"))
    require(site.get("source_kind") == "reviewed_original_native_crosswalk_site" and
            site.get("assignment_id") == ASSIGNMENT_ID and
            case_id in site.get("case_ids", []), "reviewed site identity mismatch")
    controls = CASE_CONTROLS.get(case_id.removeprefix(ASSIGNMENT_ID + "__"))
    require(case_id.startswith(ASSIGNMENT_ID + "__") and controls is not None,
            "unknown exact crosswalk case")
    require(set(site.get("source_records", {})) >= set(SOURCE_NAMES),
            "independent original source records missing")
    for name in SOURCE_NAMES:
        record = site["source_records"][name]
        relative = Path(record.get("path", ""))
        require(not relative.is_absolute() and ".." not in relative.parts and
                relative.name and record.get("sha256") == site.get(name + "_source_sha256"),
                "reviewed source identity missing: " + name)
        source_path = (site_path.parent / relative).resolve()
        require(source_path.is_file() and sha(source_path) == record["sha256"],
                "reviewed original source changed: " + name)
    require(site.get("crosswalk_marked") is controls[3],
            "marked-crosswalk case control changed")
    require(site.get("requested_activity") == controls[1] and
            site.get("requested_exception") == controls[2],
            "activity or exception control changed")
    require(site.get("cell_id") == "C394507" and
            site.get("actor") == "motor_vehicle_driver" and
            site.get("driver_id") and site.get("vehicle_id"),
            "jurisdiction or actor context missing")
    route = site.get("vehicle_route_xy_m")
    require(isinstance(route, list) and len(route) >= 2 and all(point(p) for p in route),
            "source-reviewed vehicle route missing")
    require(math.dist(route[0], route[-1]) > 1, "degenerate vehicle route")
    crossing = site.get("crossing_polygon_xy_m")
    require(isinstance(crossing, list) and len(crossing) >= 3 and
            all(point(p) for p in crossing), "source-reviewed crossing polygon missing")
    require(site.get("map_sha256") and len(site["map_sha256"]) == 64,
            "reviewed OpenDRIVE hash missing")
    require(abs(float(site.get("requested_body_clearance_m", -1)) - controls[0]) < 1e-8,
            "numeric engineering target changed")
    return site


def check_live_readback(operator, world, site):
    for name in ("map_bytes", "site_readback", "spawn_vehicle", "set_vehicle_route",
                 "set_crosswalk", "set_activity", "set_exception_context", "control",
                 "observe", "cameras", "start_pipeline_capture", "capture_pipeline_tick",
                 "close_pipeline_capture"):
        require(callable(getattr(operator, name, None)), "Native operator method missing: " + name)
    require(hashlib.sha256(operator.map_bytes(world)).hexdigest() == site["map_sha256"],
            "loaded Native map differs from reviewed site")
    readback = operator.site_readback(world, site)
    for name in ("crosswalk_marked", "crossing_polygon_xy_m", "road_id", "lane_id",
                 "jurisdiction_id", "vehicle_route_xy_m"):
        require(readback.get(name) == site.get(name),
                "Native site geometry/context differs: " + name)


def construct(operator, site):
    """Make the requested crossing, route, activity and exception actors explicit."""
    vehicle = operator.spawn_vehicle(site["vehicle_route_xy_m"][0])
    require(vehicle is not None, "Native vehicle spawn failed")
    try:
        operator.set_crosswalk(site["crossing_polygon_xy_m"], site["crosswalk_marked"])
        operator.set_vehicle_route(vehicle, site["vehicle_route_xy_m"],
                                   site["requested_body_clearance_m"])
        operator.set_activity(vehicle, site["requested_activity"])
        operator.set_exception_context(site["requested_exception"], site)
        return vehicle
    except Exception:
        operator.destroy(vehicle)
        raise
