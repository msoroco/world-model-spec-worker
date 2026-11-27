"""Construct exact heavy vehicle speed probes from reviewed school-crossing-zone source packets.

The packet is an input to local execution, never a substitute for an original
school survey. The adapter owns CARLA calls and returns their readback.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from school_timing import derive

ASSIGNMENT = "testing__C255456__NRS-484B-363-2__heavy_vehicle_driver"
ROOT = Path(__file__).resolve().parent
SOURCES = (
    "zone_designation", "zone_boundaries", "school_property", "property_nonadjacency",
    "crosswalk_geometry", "pupil_walking_route", "heavy_route",
    "heavy_blueprint", "driver_identity", "children_locations", "civil_date_time",
    "school_calendar", "operation_hours", "class_hours", "beacon_designation",
    "beacon_operability", "beacon_lamp_configuration", "beacon_lamp_history",
    "sign_active_period",
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_case(case_id):
    require(isinstance(case_id, str) and case_id.startswith(ASSIGNMENT + "__"),
            "exact heavy-vehicle-driver case ID required")
    plan = json.loads((ROOT / "case-plan.json").read_text())
    matches = [case for case in plan["cases"] if case["case_id"] == case_id]
    require(len(matches) == 1, "unknown exact heavy-vehicle-driver case")
    return matches[0]


def _finite_pair(value, name):
    require(isinstance(value, list) and len(value) == 2 and
            all(type(number) in (float, int) and math.isfinite(number) for number in value),
            "reviewed coordinate missing: " + name)


def _inside_polygon(point, polygon):
    x, y = point
    inside = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        ax, ay = a
        bx, by = b
        cross = (x - ax) * (by - ay) - (y - ay) * (bx - ax)
        if abs(cross) <= 1e-8 and min(ax, bx) - 1e-8 <= x <= max(ax, bx) + 1e-8 and min(ay, by) - 1e-8 <= y <= max(ay, by) + 1e-8:
            return True
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            inside = not inside
    return inside


def _segments_cross(a, b, c, d):
    def orient(p, q, r):
        return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    return orient(a,b,c)*orient(a,b,d) <= 0 and orient(c,d,a)*orient(c,d,b) <= 0


def _route_crosses_polygon(route, polygon):
    return any(_inside_polygon(point, polygon) for point in route) or any(
        _segments_cross(a,b,c,d)
        for a,b in zip(route, route[1:])
        for c,d in zip(polygon, polygon[1:]+polygon[:1])
    )


def validate_site(path, case_id):
    path = Path(path).resolve()
    case = load_case(case_id)
    packet = json.loads(path.read_text())
    require(packet.get("case_id") == case_id, "reviewed source packet case mismatch")
    require(packet.get("source_kind") == "reviewed_original_school_crossing_zone_site",
            "reviewed original school-crossing-zone site required")
    require(isinstance(packet.get("map_sha256"), str) and len(packet["map_sha256"]) == 64,
            "reviewed Native map hash required")
    records = packet.get("source_records")
    require(isinstance(records, dict) and set(records) == set(SOURCES),
            "reviewed school-crossing-zone source inventory incomplete")
    for name in SOURCES:
        record = records[name]
        require(isinstance(record, dict) and isinstance(record.get("path"), str),
                "reviewed source record missing: " + name)
        source = (path.parent / record["path"]).resolve()
        require(path.parent in source.parents and source.is_file(),
                "reviewed source outside packet or absent: " + name)
        digest = sha(source)
        require(digest == record.get("sha256") == packet.get(name + "_source_sha256"),
                "reviewed source hash differs: " + name)
    zone = packet.get("zone_polygon_xy_m")
    route = packet.get("route_xy_m")
    children = packet.get("children_xy_m")
    require(isinstance(zone, list) and len(zone) >= 3, "school-crossing-zone polygon required")
    require(isinstance(route, list) and len(route) >= 2, "supported route geometry required")
    require(isinstance(children, list), "children inventory required")
    for name, coordinates in (("zone", zone), ("route", route), ("child", children)):
        for point in coordinates:
            _finite_pair(point, name)
    require(isinstance(packet.get("heavy_blueprint"), str) and
            packet["heavy_blueprint"].startswith("vehicle.") and
            isinstance(packet.get("driver_id"), str) and packet["driver_id"],
            "original heavy vehicle and driver identity required")
    require(packet.get("heavy_route_id") and packet.get("school_property_id"),
            "supported heavy route and school property required")
    require(packet.get("street_nonadjacent_to_school_property") is True,
            "crossing-zone street nonadjacency requires reviewed source")
    require(packet.get("crosswalk_id") and packet.get("designated_pupil_route_id"),
            "crosswalk and designated pupil walking route require reviewed sources")
    crosswalk = packet.get("crosswalk_polygon_xy_m")
    pupil_route = packet.get("pupil_route_xy_m")
    require(isinstance(crosswalk, list) and len(crosswalk) >= 3,
            "reviewed crossing-zone crosswalk polygon required")
    require(isinstance(pupil_route, list) and len(pupil_route) >= 2,
            "reviewed designated pupil walking route required")
    for name, coordinates in (("crosswalk", crosswalk), ("pupil route", pupil_route)):
        for point in coordinates:
            _finite_pair(point, name)
    require(all(_inside_polygon(point, zone) for point in crosswalk),
            "reviewed crosswalk lies outside designated crossing-zone extent")
    require(_route_crosses_polygon(pupil_route, crosswalk),
            "designated pupil walking route does not cross reviewed crosswalk")
    require(_route_crosses_polygon(route, crosswalk),
            "heavy vehicle route does not traverse reviewed crossing-zone crosswalk")
    require(isinstance(packet.get("school_in_session_today"), bool),
            "independent school calendar fact required")
    require(isinstance(packet.get("operational_beacon_designation"), bool),
            "independent beacon designation fact required")
    facts = derive(packet.get("timing_packet"), records)
    require(packet["school_in_session_today"] == facts["school_in_session_today"] and
            packet["operational_beacon_designation"] == facts["operational_beacon_designation"] and
            packet["beacon_yellow_lamp_count"] == packet["timing_packet"]["beacon_yellow_lamp_count"] and
            packet["beacon_alternating_capable"] == packet["timing_packet"]["beacon_alternating_capable"],
            "independent clock/device facts differ from reviewed site")
    require(facts["school_in_session_today"] == (case["session_request"] == "session"),
            "requested session branch differs from original calendar")
    require(packet.get("time_window_label") == case["time_request"] and
            packet.get("beacon_or_sign_state") == case["beacon_or_sign_request"],
            "requested clock/device branch differs from source packet")
    time_request = case["time_request"]
    require((time_request == "active" and not facts["outside_operation_half_hour"]) or
            (time_request == "class_hours" and facts["during_class"] and
             not facts["outside_operation_half_hour"]) or
            (time_request == "after_half_hour" and facts["near_after_operation_boundary"]) or
            (time_request == "before_half_hour" and facts["near_before_next_start_boundary"]),
            "requested half-hour/class branch lacks independent clock proof")
    lamp_count = packet.get("beacon_yellow_lamp_count")
    require(type(lamp_count) is int and lamp_count >= 0,
            "beacon yellow lamp configuration required")
    require(isinstance(packet.get("beacon_alternating_capable"), bool),
            "beacon alternating capability required")
    if case["beacon_or_sign_request"].startswith("operational_"):
        require(packet["operational_beacon_designation"] and lamp_count >= 2 and
                packet["beacon_alternating_capable"],
                "operational alternating-yellow beacon source absent")
    elif case["beacon_or_sign_request"].startswith("nonbeacon_"):
        require(not packet["operational_beacon_designation"],
                "nonbeacon case has operational beacon designation")
    device = case["beacon_or_sign_request"]
    if device == "operational_flashing":
        require(facts["alternating_flash_observed"], "alternating yellow flash not observed")
    elif device == "operational_not_flashing":
        require(not facts["alternating_flash_observed"], "beacon no-flash control differs")
    elif device == "one_yellow_light":
        require(lamp_count == 1 and not facts["beacon_definition_supported"],
                "one-light beacon control differs")
    elif device == "nonalternating_yellow":
        require(lamp_count >= 2 and not facts["beacon_definition_supported"],
                "nonalternating beacon control differs")
    elif device in ("nonbeacon_sign_on", "nonbeacon_sign_off"):
        require(facts["sign_limit_active"] == (device == "nonbeacon_sign_on"),
                "nonbeacon sign instruction differs")
    packet["_source_sha256"] = sha(path)
    return packet


def construct(adapter, site_path, case_id):
    """Build scene and verify the adapter's physical creation/readback calls."""
    site = validate_site(site_path, case_id)
    case = load_case(case_id)
    speed_mps = case["speed_target_mph"] / 2.2369362921
    require(0 < speed_mps < 30, "heavy vehicle speed target out of supported range")
    scene = adapter.build_school_crossing_zone(site, case)
    require(isinstance(scene, dict) and scene.get("map_sha256") == site["map_sha256"] and
            scene.get("zone_polygon_xy_m") == site["zone_polygon_xy_m"] and
            scene.get("route_xy_m") == site["route_xy_m"] and
            scene.get("crosswalk_polygon_xy_m") == site["crosswalk_polygon_xy_m"] and
            scene.get("pupil_route_xy_m") == site["pupil_route_xy_m"],
            "original zone and route readback differs")
    require(scene.get("vehicle_blueprint") ==
            (site["heavy_blueprint"] if case["vehicle_request"] == "heavy_motor_vehicle" else site.get("car_blueprint")),
            "requested vehicle construction/readback differs")
    require(scene.get("driver_id") == site["driver_id"], "driver readback differs")
    require(scene.get("children_xy_m") ==
            (site["children_xy_m"] if case["children_request"] == "children" else []),
            "children creation/readback differs")
    require(scene.get("inside_designated_zone") is (case["zone_request"] == "inside") and
            scene.get("school_in_session_today") is site["school_in_session_today"] and
            scene.get("time_window_label") == case["time_request"] and
            scene.get("beacon_or_sign_state") == case["beacon_or_sign_request"],
            "original school-crossing-zone intervention readback differs")
    require(scene.get("beacon_yellow_lamp_count") == site["beacon_yellow_lamp_count"] and
            scene.get("beacon_alternating_capable") is site["beacon_alternating_capable"],
            "beacon configuration readback differs")
    controller = adapter.configure_speed_controller(scene, speed_mps, case)
    require(isinstance(controller, dict) and
            type(controller.get("target_mps")) in (float, int) and
            abs(controller["target_mps"] - speed_mps) <= .000001 and
            controller.get("vehicle_id") == scene.get("vehicle_id"),
            "heavy vehicle speed controller readback differs")
    return {"assignment_id": ASSIGNMENT, "case_id": case_id,
            "site_sha256": site["_source_sha256"], "map_sha256": site["map_sha256"],
            "vehicle_id": scene["vehicle_id"], "target_speed_mps": speed_mps,
            "target_speed_mph": case["speed_target_mph"],
            "source_limited": "speed target and readback do not prove achieved motion or legal applicability"}
