"""Authored school pedestrian lane, warning device, child and ego requests."""

from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET


ROAD_ID = 394563
ROAD_START_X_M = -100
ROAD_LENGTH_M = 200
LANE_WIDTH_M = 3.5
LANE_NEAR_SIDE_X_M = 0.0
FEET_PER_METRE = 3.280839895013123
CASES = {"probe_1": 55.0, "probe_2": 40.0}
CAMERAS = {"overview", "approach", "reference_corner", "driver_reference"}
RELEASES = {"signal_stopped", "signal_raised", "signal_removed",
            "flagman_go", "flagman_left", "person_go", "person_left"}


def open_drive():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4",
                  name="C394563-school-warning-road", version="1",
                  north="15", south="-15", east="100", west="-100",
                  vendor="full-train-worker")
    road = ET.SubElement(root, "road", id=str(ROAD_ID), name="C394563_school_lane_approach",
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
    for side, ident in (("left", 1), ("center", 0), ("right", -1)):
        group = ET.SubElement(section, side)
        lane = ET.SubElement(group, "lane", id=str(ident),
                             type="none" if ident == 0 else "driving", level="false")
        if ident:
            ET.SubElement(lane, "width", sOffset="0", a=str(LANE_WIDTH_M), b="0", c="0", d="0")
        ET.SubElement(lane, "roadMark", sOffset="0",
                      type="solid" if ident == 0 else "broken",
                      color="yellow" if ident == 0 else "white", width="0.12")
    ET.SubElement(road, "objects")
    ET.SubElement(road, "signals")
    return ET.tostring(root, encoding="unicode")


def scene_request(case, *, vehicle_blueprint="vehicle.tesla.model3",
                  warning_blueprint="static.prop.warning",
                  child_blueprint="walker.pedestrian.0001"):
    if case not in CASES:
        raise ValueError("Unknown school warning comparison case")
    if not vehicle_blueprint.startswith("vehicle."):
        raise ValueError("Invalid vehicle blueprint")
    if not warning_blueprint.startswith("static.prop."):
        raise ValueError("Invalid warning device prop blueprint")
    if not child_blueprint.startswith("walker.pedestrian."):
        raise ValueError("Invalid child actor blueprint request")
    return {
        "format": "worker-authored-school-warning-request", "case": case,
        "road_opendrive": open_drive(), "road_id": ROAD_ID,
        "vehicle": {"blueprint": vehicle_blueprint, "start_xyz": [-65, -1.75, 0.5],
                    "heading_deg": 0,
                    "requested_stop_center_x_m": LANE_NEAR_SIDE_X_M - CASES[case] / FEET_PER_METRE},
        "school_pedestrian_lane": {"near_side_x_m": LANE_NEAR_SIDE_X_M,
                                   "far_side_x_m": 4.0, "official_status_verified": False},
        "warning": {"role": "signal_device", "blueprint": warning_blueprint,
                    "xyz": [-1, -6, 0], "active_from_frame": 0,
                    "requested_release_event": "signal_removed",
                    "requested_release_frame": 250,
                    "original_warning_state_verified": False},
        "child": {"blueprint": child_blueprint, "start_xyz": [-2, -8, 0.2],
                  "age_status_verified": False, "requested_about_to_cross": True},
        "cameras": [
            {"name": "overview", "xyz": [-18, -13, 24], "yaw": 35, "pitch": -50, "size": [1920, 1080]},
            {"name": "approach", "xyz": [-3, -11, 8], "yaw": 90, "pitch": -20, "size": [1280, 720]},
            {"name": "reference_corner", "xyz": [6, 11, 8], "yaw": 180, "pitch": -20, "size": [1280, 720]},
            {"name": "driver_reference", "xyz": [1, 0, 2], "yaw": 0, "pitch": -8, "size": [1280, 720], "attach_to_vehicle": True},
        ],
        "rate_hz": 20, "duration_s": 30, "planned_frames": 600,
        "physical_success_claimed": False,
    }


def controller_command(case, frame, observed_x_m, observed_speed_mps, warning_active, observed_release):
    if case not in CASES or type(frame) is not int or not 0 <= frame < 600:
        raise ValueError("Invalid warning case or frame")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
           for value in (observed_x_m, observed_speed_mps)) or observed_speed_mps < 0:
        raise ValueError("Missing original Native pose or speed")
    if warning_active not in (True, False) or observed_release not in RELEASES | {None}:
        raise ValueError("Missing sourced warning or release")
    target = LANE_NEAR_SIDE_X_M - CASES[case] / FEET_PER_METRE
    remaining = target - observed_x_m
    if remaining < -1.0 and observed_release is None:
        raise ValueError("Vehicle overshot requested stop before release")
    if observed_release is not None:
        return {"phase": "released", "throttle": 0.20, "brake": 0.0, "steer": 0.0}
    if warning_active and remaining <= max(1.0, observed_speed_mps ** 2 / 4 + 1.0):
        return {"phase": "brake_or_hold", "throttle": 0.0, "brake": 1.0, "steer": 0.0}
    if warning_active:
        return {"phase": "approach", "throttle": 0.20, "brake": 0.0, "steer": 0.0}
    return {"phase": "await_sourced_release", "throttle": 0.0, "brake": 1.0, "steer": 0.0}


def validate_request(request):
    root = ET.fromstring(request["road_opendrive"])
    road = root.find("road")
    if root.tag != "OpenDRIVE" or road is None or road.attrib["id"] != str(ROAD_ID):
        raise ValueError("Authored school road identity missing")
    lanes = road.findall("lanes/laneSection/*/lane")
    if {lane.attrib["id"] for lane in lanes} != {"-1", "0", "1"}:
        raise ValueError("Two-way road lanes missing")
    if {camera["name"] for camera in request.get("cameras", [])} != CAMERAS:
        raise ValueError("Four source camera requests missing")
    if request.get("rate_hz") != 20 or request.get("planned_frames") != 600:
        raise ValueError("30-second capture contract missing")
    if request["warning"]["original_warning_state_verified"] or request["child"]["age_status_verified"]:
        raise ValueError("Authored request cannot assert source verification")
    return {"case": request["case"], "camera_count": 4,
            "planned_frames": 600, "authored_geometry_checked": True,
            "native_warning_and_child_verified": False}


if __name__ == "__main__":
    print(json.dumps({case: validate_request(scene_request(case)) for case in CASES}, indent=2))
