"""Authored alley parking scene and 30-second hold controller request.

The hour-long parking history is a separate original source ledger. This scene
cannot by itself establish the statutory rolling-hour duration.
"""

from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET


ROAD_ID = 375341
ROAD_START_X_M = -60
ROAD_LENGTH_M = 120
LANE_WIDTH_M = 4.0
CASES = {"probe_1": 1500, "probe_2": 2100}
CAMERAS = {"overview", "approach", "reference_corner", "driver_reference"}


def open_drive():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4",
                  name="C375341-alley-parking-request", version="1",
                  north="10", south="-10", east="60", west="-60",
                  vendor="full-train-worker")
    road = ET.SubElement(root, "road", id=str(ROAD_ID), name="C375341_alley",
                         length=str(ROAD_LENGTH_M), junction="-1")
    ET.SubElement(road, "link")
    geometry = ET.SubElement(ET.SubElement(road, "planView"), "geometry",
                             s="0", x=str(ROAD_START_X_M), y="0", hdg="0",
                             length=str(ROAD_LENGTH_M))
    ET.SubElement(geometry, "line")
    ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation",
                  s="0", a="0", b="0", c="0", d="0")
    lanes = ET.SubElement(road, "lanes")
    ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
    section = ET.SubElement(lanes, "laneSection", s="0")
    right = ET.SubElement(section, "right")
    lane = ET.SubElement(right, "lane", id="-1", type="driving", level="false")
    ET.SubElement(lane, "width", sOffset="0", a=str(LANE_WIDTH_M), b="0", c="0", d="0")
    ET.SubElement(lane, "roadMark", sOffset="0", type="none", color="white", width="0")
    ET.SubElement(road, "objects")
    ET.SubElement(road, "signals")
    return ET.tostring(root, encoding="unicode")


def scene_request(case, *, vehicle_blueprint="vehicle.tesla.model3",
                  wall_blueprint="static.prop.wall", curb_blueprint="static.prop.curb"):
    if case not in CASES:
        raise ValueError("Unknown alley parking case")
    if not vehicle_blueprint.startswith("vehicle."):
        raise ValueError("Invalid vehicle blueprint")
    if not wall_blueprint.startswith("static.prop.") or not curb_blueprint.startswith("static.prop."):
        raise ValueError("Invalid alley prop blueprint")
    return {
        "format": "worker-authored-alley-parking-request", "case": case,
        "road_opendrive": open_drive(), "road_id": ROAD_ID,
        "vehicle": {"blueprint": vehicle_blueprint, "park_xyz": [0, -2, 0.5],
                    "heading_deg": 0, "requested_brake": 1.0},
        "alley": {"entrance_x_m": -40, "surveyed_alley_status": False,
                   "wall_blueprint": wall_blueprint, "curb_blueprint": curb_blueprint,
                   "wall_requests_xyz": [[-20, 5, 0], [20, 5, 0]],
                   "curb_requests_xyz": [[-20, -5, 0], [20, -5, 0]]},
        "cameras": [
            {"name": "overview", "xyz": [-15, -12, 20], "yaw": 35, "pitch": -50, "size": [1920, 1080]},
            {"name": "approach", "xyz": [1, 0, 2], "yaw": 0, "pitch": -8, "size": [1280, 720], "attach_to_vehicle": True},
            {"name": "reference_corner", "xyz": [-42, -8, 7], "yaw": 0, "pitch": -20, "size": [1280, 720]},
            {"name": "driver_reference", "xyz": [4, 8, 7], "yaw": 180, "pitch": -20, "size": [1280, 720]},
        ],
        "rate_hz": 20, "duration_s": 30, "planned_frames": 600,
        "separate_original_hour_ledger_required": True,
        "requested_total_parked_seconds_in_hour": CASES[case],
        "physical_success_claimed": False,
    }


def hold_command(case, frame, observed_speed_mps):
    if case not in CASES or type(frame) is not int or not 0 <= frame < 600:
        raise ValueError("Invalid alley case or frame")
    if isinstance(observed_speed_mps, bool) or not isinstance(observed_speed_mps, (int, float)) or not math.isfinite(observed_speed_mps) or observed_speed_mps < 0:
        raise ValueError("Missing original Native speed")
    return {"phase": "parked_hold", "throttle": 0.0, "brake": 1.0, "steer": 0.0,
            "observed_stopped": observed_speed_mps <= 0.10}


def validate_request(request):
    root = ET.fromstring(request["road_opendrive"])
    road = root.find("road")
    if root.tag != "OpenDRIVE" or road is None or road.attrib["id"] != str(ROAD_ID):
        raise ValueError("Authored alley road identity missing")
    lanes = road.findall("lanes/laneSection/right/lane")
    if len(lanes) != 1 or lanes[0].attrib["id"] != "-1":
        raise ValueError("Authored alley driving lane missing")
    if {camera["name"] for camera in request.get("cameras", [])} != CAMERAS:
        raise ValueError("Four source camera requests missing")
    if request.get("rate_hz") != 20 or request.get("planned_frames") != 600:
        raise ValueError("30-second capture contract missing")
    if request["alley"]["surveyed_alley_status"] or not request.get("separate_original_hour_ledger_required"):
        raise ValueError("Authored scene cannot assert alley or hour proof")
    return {"case": request["case"], "planned_frames": 600,
            "camera_count": 4, "authored_geometry_checked": True,
            "native_alley_status_verified": False}


if __name__ == "__main__":
    print(json.dumps({case: validate_request(scene_request(case)) for case in CASES}, indent=2))
