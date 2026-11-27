"""Authored one-way freight curb zone and material activity requests."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET


ROAD_ID = 386328
START_X_M = -60
LENGTH_M = 120
LANE_WIDTH_M = 4.0
CASES = {
    "probe_1": {"material": "pickup_loading", "passenger": "none_requested", "waiting": False, "effective": True},
    "probe_2": {"material": "none_requested", "passenger": "none_requested", "waiting": False, "effective": True},
    "probe_3": {"material": "none_requested", "passenger": "none_requested", "waiting": False, "effective": False},
    "probe_4": {"material": "none_requested", "passenger": "loading", "waiting": False, "effective": True},
    "probe_5": {"material": "none_requested", "passenger": "loading", "waiting": True, "effective": True},
}
CAMERAS = {"overview", "approach", "reference_corner", "driver_reference"}


def open_drive():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4",
                  name="C386328-one-way-freight-zone", version="1",
                  north="10", south="-10", east="60", west="-60",
                  vendor="full-train-worker")
    road = ET.SubElement(root, "road", id=str(ROAD_ID), name="C386328_one_way_curb",
                         length=str(LENGTH_M), junction="-1")
    ET.SubElement(road, "link")
    geometry = ET.SubElement(ET.SubElement(road, "planView"), "geometry",
                             s="0", x=str(START_X_M), y="0", hdg="0", length=str(LENGTH_M))
    ET.SubElement(geometry, "line")
    ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation",
                  s="0", a="0", b="0", c="0", d="0")
    lanes = ET.SubElement(road, "lanes")
    ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
    section = ET.SubElement(lanes, "laneSection", s="0")
    right = ET.SubElement(section, "right")
    lane = ET.SubElement(right, "lane", id="-1", type="driving", level="false")
    ET.SubElement(lane, "width", sOffset="0", a=str(LANE_WIDTH_M), b="0", c="0", d="0")
    ET.SubElement(lane, "roadMark", sOffset="0", type="broken", color="white", width="0.12")
    objects = ET.SubElement(road, "objects")
    ET.SubElement(objects, "object", id="freight-zone-curb-386328", s="50", t="-4.1",
                  name="marked_freight_curb_loading_zone", type="curb", orientation="none",
                  zOffset="0", length="22", width="0.2", height="0.15", hdg="0",
                  pitch="0", roll="0")
    signals = ET.SubElement(road, "signals")
    ET.SubElement(signals, "signal", id="freight-loading-sign-386328", s="50", t="-4.2",
                  name="FREIGHT LOADING 08:00-17:00 America/Los_Angeles", dynamic="no",
                  orientation="+", zOffset="0", country="US", type="freight-loading",
                  subtype="0", value="0", unit="", height="0.8", width="0.8")
    return ET.tostring(root, encoding="unicode")


def scene_request(case, *, vehicle_blueprint="vehicle.tesla.model3",
                  sign_blueprint="static.prop.sign",
                  material_blueprint="static.prop.box01"):
    if case not in CASES:
        raise ValueError("Unknown freight-zone comparison case")
    if not vehicle_blueprint.startswith("vehicle."):
        raise ValueError("Invalid vehicle blueprint")
    if not sign_blueprint.startswith("static.prop.") or not material_blueprint.startswith("static.prop."):
        raise ValueError("Invalid sign or material prop blueprint")
    intent = CASES[case]
    return {
        "format": "worker-authored-freight-curb-zone-request", "case": case,
        "road_opendrive": open_drive(), "road_id": ROAD_ID,
        "vehicle": {"blueprint": vehicle_blueprint, "park_xyz": [0, -2.3, 0.5],
                    "heading_deg": 0, "requested_brake": 1.0},
        "zone": {"kind": "freight_curb_loading", "object_id": "freight-zone-curb-386328",
                 "sign_id": "freight-loading-sign-386328", "curb_segment_x_m": [-10, 12],
                 "right_curb_y_m": -4.0, "marking_native_verified": False},
        "sign": {"blueprint": sign_blueprint, "xyz": [-10, -5.5, 0],
                 "requested_effective_hours_local": [480, 1020],
                 "actual_text_and_hours_verified": False},
        "civil_time": {"requested_minute_local": 720 if intent["effective"] else 1100,
                       "original_clock_source_required": True},
        "material": {"blueprint": material_blueprint, "source_and_destination_xyz":
                     [[0, -2.5, 0.5], [0, -6, 0.5]],
                     "requested_activity": intent["material"],
                     "physical_activity_verified": False},
        "passenger": {"requested_activity": intent["passenger"],
                       "source_review_required": True},
        "material_transport_vehicle": {
            "requested_waiting_to_enter": intent["waiting"],
            "blueprint": "vehicle.carlamotors.carlacola",
            "requested_xyz": [-16, -2.3, 0.5],
            "source_class_and_interference_review_required": True},
        "cameras": [
            {"name": "overview", "xyz": [-18, -12, 20], "yaw": 35, "pitch": -45, "size": [1920, 1080]},
            {"name": "approach", "xyz": [-13, -8, 7], "yaw": 35, "pitch": -22, "size": [1280, 720]},
            {"name": "reference_corner", "xyz": [5, -10, 7], "yaw": 90, "pitch": -25, "size": [1280, 720]},
            {"name": "driver_reference", "xyz": [1, 0, 2], "yaw": 0, "pitch": -8,
             "size": [1280, 720], "attach_to_vehicle": True},
        ],
        "rate_hz": 20, "duration_s": 30, "planned_frames": 600,
        "civil_time_source_required": True, "physical_success_claimed": False,
    }


def validate_request(request):
    root = ET.fromstring(request["road_opendrive"])
    road = root.find("road")
    if root.tag != "OpenDRIVE" or road is None or road.attrib["id"] != str(ROAD_ID):
        raise ValueError("Authored one-way road identity missing")
    lanes = road.findall("lanes/laneSection/*/lane")
    if len(lanes) != 1 or lanes[0].attrib["id"] != "-1":
        raise ValueError("One-way driving lane request missing")
    zone = road.find("objects/object")
    sign = road.find("signals/signal")
    if zone is None or zone.get("id") != request["zone"]["object_id"]:
        raise ValueError("Authored freight curb marking missing")
    if sign is None or sign.get("id") != request["zone"]["sign_id"] or not all(
            x in sign.get("name", "") for x in ("08:00", "17:00", "America/Los_Angeles")):
        raise ValueError("Authored freight sign and hours missing")
    if {camera["name"] for camera in request.get("cameras", [])} != CAMERAS:
        raise ValueError("Four source camera requests missing")
    if request.get("rate_hz") != 20 or request.get("planned_frames") != 600:
        raise ValueError("30-second capture contract missing")
    if request["zone"]["marking_native_verified"] or request["sign"]["actual_text_and_hours_verified"]:
        raise ValueError("Authored scene cannot assert original zone/sign verification")
    if request["civil_time"]["requested_minute_local"] not in (720, 1100):
        raise ValueError("Civil-time contrast request missing")
    if request["passenger"]["requested_activity"] not in ("loading", "none_requested"):
        raise ValueError("Passenger activity request missing")
    if request["material_transport_vehicle"]["source_class_and_interference_review_required"] is not True:
        raise ValueError("Original materials-vehicle class and interference review missing")
    return {"case": request["case"], "planned_frames": 600,
            "camera_count": 4, "authored_geometry_checked": True,
            "original_sign_and_material_activity_verified": False}


if __name__ == "__main__":
    print(json.dumps({case: validate_request(scene_request(case)) for case in CASES}, indent=2))
