"""Authored moving emergency-vehicle road and two controlled approach requests."""

import json
import math
import xml.etree.ElementTree as ET

CAMERAS = {"overview", "ego_front", "emergency_side", "passing_gap"}
CASES = {"probe_1": {"requested_ego_speed_mps": 5.0, "requested_surface_gap_m": 2.4},
         "probe_2": {"requested_ego_speed_mps": 8.0, "requested_surface_gap_m": 0.8}}


def open_drive():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", name="C405647-moving-emergency", version="1",
                  north="10", south="-10", east="120", west="-120", vendor="full-train-worker")
    road = ET.SubElement(root, "road", id="405647", name="moving_emergency_approach", length="240", junction="-1")
    ET.SubElement(road, "link")
    geometry = ET.SubElement(ET.SubElement(road, "planView"), "geometry", s="0", x="-120", y="0", hdg="0", length="240")
    ET.SubElement(geometry, "line")
    ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation", s="0", a="0", b="0", c="0", d="0")
    lanes = ET.SubElement(road, "lanes")
    ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
    section = ET.SubElement(lanes, "laneSection", s="0")
    for side, index in (("left", 1), ("center", 0), ("right", -1)):
        lane = ET.SubElement(ET.SubElement(section, side), "lane", id=str(index),
                             type="none" if index == 0 else "driving", level="false")
        if index:
            ET.SubElement(lane, "width", sOffset="0", a="3.5", b="0", c="0", d="0")
        ET.SubElement(lane, "roadMark", sOffset="0", type="solid" if index == 0 else "broken",
                      color="yellow" if index == 0 else "white", width="0.12")
    ET.SubElement(road, "objects")
    ET.SubElement(road, "signals")
    return ET.tostring(root, encoding="unicode")


def scene_request(case, *, ego_blueprint="vehicle.tesla.model3", emergency_blueprint="vehicle.dodge.charger_police"):
    if case not in CASES:
        raise ValueError("Unknown emergency comparison case")
    if not ego_blueprint.startswith("vehicle.") or not emergency_blueprint.startswith("vehicle."):
        raise ValueError("Vehicle blueprint request invalid")
    return {"format": "worker-authored-moving-emergency-request", "case": case,
            "road_opendrive": open_drive(), "road_id": 405647,
            "ego": {"blueprint": ego_blueprint, "start_xyz": [-75, -1.75, 0.5], "heading_deg": 0,
                    **CASES[case]},
            "emergency": {"blueprint": emergency_blueprint, "start_xyz": [-15, -1.75, 0.5],
                          "heading_deg": 0, "requested_speed_mps": 1.5,
                          "requested_flashing_lights": True, "authorization_verified": False,
                          "lamp_compliance_verified": False},
            "officer_direction": "none_requested", "officer_source_verified": False,
            "cameras": [
                {"name": "overview", "xyz": [-20, -13, 24], "yaw": 30, "pitch": -50, "size": [1920, 1080]},
                {"name": "ego_front", "xyz": [1, 0, 2], "yaw": 0, "pitch": -8, "size": [1280, 720], "attach_to_ego": True},
                {"name": "emergency_side", "xyz": [-12, -11, 7], "yaw": 90, "pitch": -15, "size": [1280, 720]},
                {"name": "passing_gap", "xyz": [8, 10, 8], "yaw": 180, "pitch": -25, "size": [1280, 720]}],
            "rate_hz": 20, "duration_s": 30, "planned_frames": 600,
            "physical_success_claimed": False}


def controller_command(case, frame, observed_speed_mps, observed_x_m, emergency_visible, lamps_visible):
    if case not in CASES or type(frame) is not int or not 0 <= frame < 600:
        raise ValueError("Invalid emergency case or frame")
    for name, value in (("speed", observed_speed_mps), ("position", observed_x_m)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("Missing original Native " + name)
    if observed_speed_mps < 0 or emergency_visible not in (True, False) or lamps_visible not in (True, False):
        raise ValueError("Invalid observed motion or indication")
    target = CASES[case]["requested_ego_speed_mps"]
    if emergency_visible and lamps_visible and observed_speed_mps > target + 0.5:
        return {"phase": "approach_decelerate", "throttle": 0.0, "brake": min(1.0, (observed_speed_mps - target) / 3), "steer": 0.0}
    if observed_speed_mps < target - 0.5:
        return {"phase": "approach_accelerate", "throttle": 0.25, "brake": 0.0, "steer": 0.0}
    return {"phase": "approach_hold", "throttle": 0.08, "brake": 0.0, "steer": 0.0}


def validate_request(request):
    root = ET.fromstring(request["road_opendrive"])
    road = root.find("road")
    if root.tag != "OpenDRIVE" or road is None or road.attrib["id"] != "405647":
        raise ValueError("Authored emergency road identity missing")
    if {lane.attrib["id"] for lane in road.findall("lanes/laneSection/*/lane")} != {"-1", "0", "1"}:
        raise ValueError("Two-way road lanes missing")
    if {camera["name"] for camera in request.get("cameras", [])} != CAMERAS:
        raise ValueError("Four source camera requests missing")
    if request.get("rate_hz") != 20 or request.get("planned_frames") != 600:
        raise ValueError("30-second capture contract missing")
    if request["emergency"]["authorization_verified"] or request["emergency"]["lamp_compliance_verified"]:
        raise ValueError("Authored request cannot assert source verification")
    return {"case": request["case"], "camera_count": 4, "planned_frames": 600,
            "authored_geometry_checked": True, "native_emergency_qualification_verified": False}


if __name__ == "__main__":
    print(json.dumps({case: validate_request(scene_request(case)) for case in CASES}, indent=2))
