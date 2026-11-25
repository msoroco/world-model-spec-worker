"""Authored adjacent-intersection crossing scene and pedestrian motion request."""

import json
import math
import xml.etree.ElementTree as ET

CASES = {"marked_crosswalk": 40.0, "unmarked_midblock": 60.0}
CAMERAS = {"overview", "pedestrian_eye", "marking_side", "device_pair"}


def open_drive():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", name="C109166-adjacent-controls",
                  version="1", north="20", south="-20", east="120", west="-20", vendor="full-train-worker")
    road = ET.SubElement(root, "road", id="109166", name="between_adjacent_intersections",
                         length="140", junction="-1")
    link = ET.SubElement(road, "link")
    ET.SubElement(link, "predecessor", elementType="junction", elementId="1")
    ET.SubElement(link, "successor", elementType="junction", elementId="2")
    geometry = ET.SubElement(ET.SubElement(road, "planView"), "geometry", s="0", x="-20", y="0",
                             hdg="0", length="140")
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
    objects = ET.SubElement(road, "objects")
    ET.SubElement(objects, "object", id="40", name="marked_crosswalk", type="crosswalk",
                  s="60", t="0", zOffset="0", hdg="0", pitch="0", roll="0", length="4", width="10", height="0")
    signals = ET.SubElement(road, "signals")
    for ident, station in (("1", "20"), ("2", "120")):
        ET.SubElement(signals, "signal", id=ident, name="official_traffic_control_" + ident,
                      s=station, t="-5", zOffset="0", hOffset="0", roll="0", pitch="0",
                      orientation="+", dynamic="yes", country="US", type="1000001", subtype="0",
                      value="0", unit="", height="3", width="1")
    for ident in ("1", "2"):
        ET.SubElement(root, "junction", id=ident, name="intersection_" + ident)
    return ET.tostring(root, encoding="unicode")


def scene_request(case, *, pedestrian_blueprint="walker.pedestrian.0001"):
    if case not in CASES:
        raise ValueError("Unknown pedestrian crossing case")
    if not pedestrian_blueprint.startswith("walker.pedestrian."):
        raise ValueError("Invalid pedestrian blueprint")
    x = CASES[case]
    return {"format": "worker-authored-adjacent-intersection-request", "case": case,
            "road_opendrive": open_drive(),
            "pedestrian": {"blueprint": pedestrian_blueprint, "start_xyz": [x, -10, 0.2],
                           "requested_roadway_entry_y_m": -4, "requested_finish_y_m": 10,
                           "requested_crossing_speed_mps": 2.0},
            "intersections": [{"x_m": 0, "official_device_requested_operating": True},
                              {"x_m": 100, "official_device_requested_operating": True}],
            "marked_crosswalk": {"center_x_m": 40, "width_x_m": 4,
                                 "official_status_verified": False},
            "native_adjacency_verified": False, "native_devices_operating_verified": False,
            "cameras": [
                {"name": "overview", "xyz": [50, -18, 25], "yaw": 90, "pitch": -50, "size": [1920, 1080]},
                {"name": "pedestrian_eye", "xyz": [0, 0, 1.7], "yaw": 90, "pitch": 0, "size": [1280, 720], "attach_to_pedestrian": True},
                {"name": "marking_side", "xyz": [40, 12, 8], "yaw": 180, "pitch": -20, "size": [1280, 720]},
                {"name": "device_pair", "xyz": [50, 15, 25], "yaw": 180, "pitch": -50, "size": [1280, 720]}],
            "rate_hz": 20, "duration_s": 30, "planned_frames": 600,
            "physical_success_claimed": False}


def walker_command(case, frame, observed_xyz, observed_device_pair_operating):
    if case not in CASES or type(frame) is not int or not 0 <= frame < 600:
        raise ValueError("Invalid crossing case or frame")
    if not isinstance(observed_xyz, (tuple, list)) or len(observed_xyz) != 3 or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in observed_xyz):
        raise ValueError("Original pedestrian pose missing")
    if observed_device_pair_operating not in (True, False):
        raise ValueError("Official device operating observation missing")
    if frame < 200:
        return {"phase": "approach_wait", "direction_xyz": [0, 0, 0], "speed_mps": 0}
    if observed_xyz[1] < 10:
        return {"phase": "cross", "direction_xyz": [0, 1, 0], "speed_mps": 2}
    return {"phase": "finished", "direction_xyz": [0, 0, 0], "speed_mps": 0}


def validate_request(request):
    root = ET.fromstring(request["road_opendrive"])
    if root.tag != "OpenDRIVE" or {j.attrib["id"] for j in root.findall("junction")} != {"1", "2"}:
        raise ValueError("Two adjacent intersection requests missing")
    if len(root.findall("road/signals/signal")) != 2 or len(root.findall("road/objects/object")) != 1:
        raise ValueError("Device pair or marking request missing")
    if {c["name"] for c in request.get("cameras", [])} != CAMERAS:
        raise ValueError("Four source camera requests missing")
    if request.get("planned_frames") != 600 or request.get("rate_hz") != 20:
        raise ValueError("30-second capture contract missing")
    if request["native_adjacency_verified"] or request["native_devices_operating_verified"] or request["marked_crosswalk"]["official_status_verified"]:
        raise ValueError("Authored request cannot assert Native verification")
    return {"case": request["case"], "camera_count": 4, "planned_frames": 600,
            "authored_geometry_checked": True, "native_adjacency_and_operation_verified": False}


if __name__ == "__main__":
    print(json.dumps({case: validate_request(scene_request(case)) for case in CASES}, indent=2))
