"""Authored divided-road geometry with median opening and adjoining dividing section."""

import json
import xml.etree.ElementTree as ET

CAMERAS = {"overview", "approach", "reference_corner", "driver_reference"}
CASE_PARAMETERS = {
    "opening_left": ("left_turn", 5.0, "right_hand"),
    "section_left": ("left_turn", 18.0, "right_hand"),
    "crossover_established": ("left_turn", 18.0, "right_hand"),
    "crossover_unestablished": ("left_turn", 18.0, "right_hand"),
    "roadway_right": ("left_turn", 5.0, "right_hand"),
    "roadway_opposite": ("left_turn", 5.0, "opposite"),
}


def open_drive():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", name="C80903-divided-highway",
                  version="1", north="20", south="-20", east="70", west="-70", vendor="full-train-worker")
    for number, y, direction in ((809031, -5, "eastbound"), (809032, 5, "westbound")):
        road = ET.SubElement(root, "road", id=str(number), name=direction, length="140", junction="-1")
        ET.SubElement(road, "link")
        geometry = ET.SubElement(ET.SubElement(road, "planView"), "geometry", s="0", x="-70" if direction == "eastbound" else "70", y=str(y),
                                 hdg="0" if direction == "eastbound" else "3.141592653589793", length="140")
        ET.SubElement(geometry, "line")
        ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation", s="0", a="0", b="0", c="0", d="0")
        lanes = ET.SubElement(road, "lanes")
        ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
        section = ET.SubElement(lanes, "laneSection", s="0")
        ET.SubElement(ET.SubElement(section, "center"), "lane", id="0", type="none", level="false")
        lane = ET.SubElement(ET.SubElement(section, "right"), "lane", id="-1", type="driving", level="false")
        ET.SubElement(lane, "width", sOffset="0", a="3.5", b="0", c="0", d="0")
        ET.SubElement(road, "objects")
        ET.SubElement(road, "signals")
    return ET.tostring(root, encoding="unicode")


def scene_request(case, *, ego_blueprint="vehicle.tesla.model3"):
    if case not in CASE_PARAMETERS:
        raise ValueError("Unknown divided-road comparison case")
    if not ego_blueprint.startswith("vehicle."):
        raise ValueError("Invalid ego vehicle blueprint")
    turn_mode, station, roadway = CASE_PARAMETERS[case]
    return {"format": "worker-authored-divided-road-turn-request", "case": case,
            "road_opendrive": open_drive(), "ego": {"blueprint": ego_blueprint,
            "start_xyz": [-30, -5 if roadway == "right_hand" else 5, 0.5],
            "requested_crossing_x_m": station, "requested_turn_mode": turn_mode,
            "requested_initial_roadway": roadway},
            "median": {"y_bounds_m": [-2, 2], "physical_opening_x_m": [0, 10],
                       "barrier_segments_x_m": [[-70, 0], [25, 70]],
                       "continuous_dividing_section_x_m": [10, 25],
                       "public_authority_established": None, "physical_collision_verified": False},
            "cameras": [
                {"name": "overview", "xyz": [8, -18, 25], "yaw": 100, "pitch": -50, "size": [1920, 1080]},
                {"name": "approach", "xyz": [1, 0, 2], "yaw": 0, "pitch": -8, "size": [1280, 720], "attach_to_ego": True},
                {"name": "reference_corner", "xyz": [15, -13, 9], "yaw": 90, "pitch": -20, "size": [1280, 720]},
                {"name": "driver_reference", "xyz": [4, 13, 9], "yaw": 180, "pitch": -20, "size": [1280, 720]}],
            "rate_hz": 20, "duration_s": 30, "planned_frames": 600,
            "physical_success_claimed": False}


def validate_request(request):
    root = ET.fromstring(request["road_opendrive"])
    if root.tag != "OpenDRIVE" or {r.attrib["id"] for r in root.findall("road")} != {"809031", "809032"}:
        raise ValueError("Two divided roadways missing")
    if any({lane.attrib["id"] for lane in road.findall("lanes/laneSection/*/lane")} != {"0", "-1"}
           for road in root.findall("road")):
        raise ValueError("Directional driving lanes missing")
    if {camera["name"] for camera in request.get("cameras", [])} != CAMERAS:
        raise ValueError("Four source camera requests missing")
    if request.get("rate_hz") != 20 or request.get("planned_frames") != 600:
        raise ValueError("30-second capture contract missing")
    if request["median"]["public_authority_established"] is not None or request["median"]["physical_collision_verified"]:
        raise ValueError("Authored request cannot assert source verification")
    return {"case": request["case"], "camera_count": 4, "planned_frames": 600,
            "authored_geometry_checked": True, "native_roadway_and_median_verified": False}


if __name__ == "__main__":
    print(json.dumps({case: validate_request(scene_request(case)) for case in CASE_PARAMETERS}, indent=2))
