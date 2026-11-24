"""Authored one-way freight curb zone and material activity requests."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET


ROAD_ID = 386328
START_X_M = -60
LENGTH_M = 120
LANE_WIDTH_M = 4.0
CASES = {"probe_1": "pickup_loading", "probe_2": "none_requested"}
CAMERAS = {"overview", "ego_front", "zone_sign", "loading_side"}


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
    ET.SubElement(road, "objects")
    ET.SubElement(road, "signals")
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
    return {
        "format": "worker-authored-freight-curb-zone-request", "case": case,
        "road_opendrive": open_drive(), "road_id": ROAD_ID,
        "vehicle": {"blueprint": vehicle_blueprint, "park_xyz": [0, -2.3, 0.5],
                    "heading_deg": 0, "requested_brake": 1.0},
        "zone": {"kind": "freight_curb_loading", "curb_segment_x_m": [-10, 12],
                 "right_curb_y_m": -4.0, "marking_native_verified": False},
        "sign": {"blueprint": sign_blueprint, "xyz": [-10, -5.5, 0],
                 "requested_effective_hours_local": [480, 1020],
                 "actual_text_and_hours_verified": False},
        "material": {"blueprint": material_blueprint, "source_and_destination_xyz":
                     [[0, -2.5, 0.5], [0, -6, 0.5]],
                     "requested_activity": CASES[case],
                     "physical_activity_verified": False},
        "cameras": [
            {"name": "overview", "xyz": [-18, -12, 20], "yaw": 35, "pitch": -45, "size": [1920, 1080]},
            {"name": "ego_front", "xyz": [1, 0, 2], "yaw": 0, "pitch": -8, "size": [1280, 720], "attach_to_vehicle": True},
            {"name": "zone_sign", "xyz": [-13, -8, 7], "yaw": 35, "pitch": -22, "size": [1280, 720]},
            {"name": "loading_side", "xyz": [5, -10, 7], "yaw": 90, "pitch": -25, "size": [1280, 720]},
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
    if {camera["name"] for camera in request.get("cameras", [])} != CAMERAS:
        raise ValueError("Four source camera requests missing")
    if request.get("rate_hz") != 20 or request.get("planned_frames") != 600:
        raise ValueError("30-second capture contract missing")
    if request["zone"]["marking_native_verified"] or request["sign"]["actual_text_and_hours_verified"]:
        raise ValueError("Authored scene cannot assert original zone/sign verification")
    return {"case": request["case"], "planned_frames": 600,
            "camera_count": 4, "authored_geometry_checked": True,
            "original_sign_and_material_activity_verified": False}


if __name__ == "__main__":
    print(json.dumps({case: validate_request(scene_request(case)) for case in CASES}, indent=2))
