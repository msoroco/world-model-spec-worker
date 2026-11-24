"""Authored two-way tunnel approach and lateral controller requests.

This is a CPU construction request. Installed tunnel prop geometry, map readback,
ray obstruction and actual pixels require an original Native run.
"""

from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET


ROAD_ID = 313130
START_X_M = -100
LENGTH_M = 200
PORTAL_X_M = 0
LANE_WIDTH_M = 3.5
RIGHT_Y_M = -1.75
LEFT_Y_M = 1.75
CASES = {"probe_1": RIGHT_Y_M, "probe_2": LEFT_Y_M}
CAMERAS = {"overview", "ego_front", "portal_side", "opposing_approach"}


def open_drive():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4",
                  name="C313130-two-way-tunnel-approach", version="1",
                  north="15", south="-15", east="100", west="-100",
                  vendor="full-train-worker")
    road = ET.SubElement(root, "road", id=str(ROAD_ID), name="C313130_tunnel_approach",
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
                  tunnel_blueprint="static.prop.tunnel", occluder_blueprint="static.prop.hedge"):
    if case not in CASES:
        raise ValueError("Unknown tunnel comparison case")
    if not vehicle_blueprint.startswith("vehicle."):
        raise ValueError("Invalid vehicle blueprint")
    for name, value in (("tunnel", tunnel_blueprint), ("occluder", occluder_blueprint)):
        if not value.startswith("static.prop."):
            raise ValueError(f"Invalid {name} prop blueprint")
    return {
        "format": "worker-authored-tunnel-approach-request", "case": case,
        "road_opendrive": open_drive(), "road_id": ROAD_ID,
        "vehicle": {"blueprint": vehicle_blueprint, "start_xyz": [-65, RIGHT_Y_M, 0.5],
                    "heading_deg": 0, "requested_approach_y_m": CASES[case]},
        "tunnel": {"blueprint": tunnel_blueprint, "portal_x_m": PORTAL_X_M,
                   "axis": "eastbound", "physical_tunnel_verified": False},
        "occluder": {"blueprint": occluder_blueprint, "xyz": [-10, 5, 0],
                     "obstructed_view_verified": False},
        "cameras": [
            {"name": "overview", "xyz": [-18, -12, 25], "yaw": 35, "pitch": -50, "size": [1920, 1080]},
            {"name": "ego_front", "xyz": [1, 0, 2], "yaw": 0, "pitch": -8, "size": [1280, 720], "attach_to_vehicle": True},
            {"name": "portal_side", "xyz": [-3, -12, 8], "yaw": 90, "pitch": -20, "size": [1280, 720]},
            {"name": "opposing_approach", "xyz": [18, 6, 8], "yaw": 180, "pitch": -20, "size": [1280, 720]},
        ],
        "rate_hz": 20, "duration_s": 30, "planned_frames": 600,
        "one_way_survey_required": True, "physical_success_claimed": False,
    }


def command(case, frame, observed_x_m, observed_y_m, observed_speed_mps):
    if case not in CASES or type(frame) is not int or not 0 <= frame < 600:
        raise ValueError("Invalid tunnel case or frame")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
           for value in (observed_x_m, observed_y_m, observed_speed_mps)) or observed_speed_mps < 0:
        raise ValueError("Missing Native pose or speed")
    target_y = CASES[case]
    # Lateral changes are requested before the 100-foot zone. Physical tracking
    # remains to be checked from the full body pose, not assumed from commands.
    if case == "probe_2" and observed_x_m > -30.48 and observed_y_m < 0.5:
        raise ValueError("Left-side request not attained before 100-foot zone")
    steer = max(-0.3, min(0.3, 0.12 * (target_y - observed_y_m)))
    return {"phase": "approach", "throttle": 0.24 if observed_speed_mps < 5 else 0.0,
            "brake": 0.0, "steer": steer, "target_y_m": target_y}


def validate_request(request):
    root = ET.fromstring(request["road_opendrive"])
    road = root.find("road")
    if root.tag != "OpenDRIVE" or road is None or road.attrib["id"] != str(ROAD_ID):
        raise ValueError("Authored tunnel road identity missing")
    lanes = road.findall("lanes/laneSection/*/lane")
    if {lane.attrib["id"] for lane in lanes} != {"-1", "0", "1"}:
        raise ValueError("Two-way lane construction missing")
    if {item["name"] for item in request.get("cameras", [])} != CAMERAS:
        raise ValueError("Four source camera requests missing")
    if request.get("rate_hz") != 20 or request.get("planned_frames") != 600:
        raise ValueError("30-second capture contract missing")
    if request["tunnel"]["physical_tunnel_verified"] or request["occluder"]["obstructed_view_verified"]:
        raise ValueError("Authored scene cannot assert physical verification")
    return {"case": request["case"], "camera_count": 4, "planned_frames": 600,
            "authored_geometry_checked": True, "native_geometry_verified": False}


if __name__ == "__main__":
    print(json.dumps({case: validate_request(scene_request(case)) for case in CASES}, indent=2))
