"""Construct exact bus speed probes from reviewed school-zone source packets.

The packet is an input to local execution, never a substitute for an original
school survey. The adapter owns CARLA calls and returns their readback.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ASSIGNMENT = "testing__C262661__NRS-484B-363-1__bus_driver"
ROOT = Path(__file__).resolve().parent
SOURCES = (
    "zone_designation", "zone_boundaries", "school_property", "bus_route",
    "bus_blueprint", "driver_identity", "children_locations", "civil_date_time",
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
            "exact bus-driver case ID required")
    plan = json.loads((ROOT / "case-plan.json").read_text())
    matches = [case for case in plan["cases"] if case["case_id"] == case_id]
    require(len(matches) == 1, "unknown exact bus-driver case")
    return matches[0]


def _finite_pair(value, name):
    require(isinstance(value, list) and len(value) == 2 and
            all(type(number) in (float, int) and math.isfinite(number) for number in value),
            "reviewed coordinate missing: " + name)


def validate_site(path, case_id):
    path = Path(path).resolve()
    case = load_case(case_id)
    packet = json.loads(path.read_text())
    require(packet.get("case_id") == case_id, "reviewed source packet case mismatch")
    require(packet.get("source_kind") == "reviewed_original_school_zone_site",
            "reviewed original school-zone site required")
    require(isinstance(packet.get("map_sha256"), str) and len(packet["map_sha256"]) == 64,
            "reviewed Native map hash required")
    records = packet.get("source_records")
    require(isinstance(records, dict) and set(records) == set(SOURCES),
            "reviewed school-zone source inventory incomplete")
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
    require(isinstance(zone, list) and len(zone) >= 3, "school-zone polygon required")
    require(isinstance(route, list) and len(route) >= 2, "supported route geometry required")
    require(isinstance(children, list), "children inventory required")
    for name, coordinates in (("zone", zone), ("route", route), ("child", children)):
        for point in coordinates:
            _finite_pair(point, name)
    require(isinstance(packet.get("bus_blueprint"), str) and
            packet["bus_blueprint"].startswith("vehicle.") and
            isinstance(packet.get("driver_id"), str) and packet["driver_id"],
            "original bus and driver identity required")
    require(packet.get("bus_route_id") and packet.get("school_property_id"),
            "supported bus route and adjacent school property required")
    require(isinstance(packet.get("school_in_session_today"), bool),
            "independent school calendar fact required")
    require(isinstance(packet.get("operational_beacon_designation"), bool),
            "independent beacon designation fact required")
    require(packet["school_in_session_today"] == (case["session_request"] == "session"),
            "requested session branch differs from original calendar")
    require(packet.get("time_window_label") == case["time_request"] and
            packet.get("beacon_or_sign_state") == case["beacon_or_sign_request"],
            "requested clock/device branch differs from source packet")
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
    packet["_source_sha256"] = sha(path)
    return packet


def construct(adapter, site_path, case_id):
    """Build scene and verify the adapter's physical creation/readback calls."""
    site = validate_site(site_path, case_id)
    case = load_case(case_id)
    speed_mps = case["speed_target_mph"] / 2.2369362921
    require(0 < speed_mps < 30, "bus speed target out of supported range")
    scene = adapter.build_school_zone(site, case)
    require(isinstance(scene, dict) and scene.get("map_sha256") == site["map_sha256"] and
            scene.get("zone_polygon_xy_m") == site["zone_polygon_xy_m"] and
            scene.get("route_xy_m") == site["route_xy_m"],
            "original zone and route readback differs")
    require(scene.get("vehicle_blueprint") ==
            (site["bus_blueprint"] if case["vehicle_request"] == "motor_bus" else site.get("car_blueprint")),
            "requested vehicle construction/readback differs")
    require(scene.get("driver_id") == site["driver_id"], "driver readback differs")
    require(scene.get("children_xy_m") ==
            (site["children_xy_m"] if case["children_request"] == "children" else []),
            "children creation/readback differs")
    require(scene.get("inside_designated_zone") is (case["zone_request"] == "inside") and
            scene.get("school_in_session_today") is site["school_in_session_today"] and
            scene.get("time_window_label") == case["time_request"] and
            scene.get("beacon_or_sign_state") == case["beacon_or_sign_request"],
            "original school-zone intervention readback differs")
    require(scene.get("beacon_yellow_lamp_count") == site["beacon_yellow_lamp_count"] and
            scene.get("beacon_alternating_capable") is site["beacon_alternating_capable"],
            "beacon configuration readback differs")
    controller = adapter.configure_speed_controller(scene, speed_mps, case)
    require(isinstance(controller, dict) and
            type(controller.get("target_mps")) in (float, int) and
            abs(controller["target_mps"] - speed_mps) <= .000001 and
            controller.get("vehicle_id") == scene.get("vehicle_id"),
            "bus speed controller readback differs")
    return {"assignment_id": ASSIGNMENT, "case_id": case_id,
            "site_sha256": site["_source_sha256"], "map_sha256": site["map_sha256"],
            "vehicle_id": scene["vehicle_id"], "target_speed_mps": speed_mps,
            "target_speed_mph": case["speed_target_mph"],
            "source_limited": "speed target and readback do not prove achieved motion or legal applicability"}
