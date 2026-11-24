"""Authored two-direction road and paired vehicle meeting requests."""

import json
import xml.etree.ElementTree as ET

CAMERAS = {"overview", "ego_front", "meeting_side", "pavement_top"}
FRACTIONS = {"0.45": 0.45, "0.55": 0.55}


def open_drive():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", name="C111294-opposite-meeting",
                  version="1", north="10", south="-10", east="100", west="-100", vendor="full-train-worker")
    road = ET.SubElement(root, "road", id="111294", name="two_direction_paved_road", length="200", junction="-1")
    ET.SubElement(road, "link")
    geometry = ET.SubElement(ET.SubElement(road, "planView"), "geometry", s="0", x="-100", y="0", hdg="0", length="200")
    ET.SubElement(geometry, "line")
    ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation", s="0", a="0", b="0", c="0", d="0")
    lanes = ET.SubElement(road, "lanes")
    ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
    section = ET.SubElement(lanes, "laneSection", s="0")
    for side, ident in (("left", 1), ("center", 0), ("right", -1)):
        lane = ET.SubElement(ET.SubElement(section, side), "lane", id=str(ident),
                             type="none" if ident == 0 else "driving", level="false")
        if ident:
            ET.SubElement(lane, "width", sOffset="0", a="4", b="0", c="0", d="0")
        ET.SubElement(lane, "roadMark", sOffset="0", type="solid", color="yellow" if ident == 0 else "white", width="0.12")
    ET.SubElement(road, "objects")
    ET.SubElement(road, "signals")
    return ET.tostring(root, encoding="unicode")


def scene_request(case, *, vehicle_blueprint="vehicle.tesla.model3"):
    if case not in FRACTIONS:
        raise ValueError("Unknown meeting comparison case")
    if not vehicle_blueprint.startswith("vehicle."):
        raise ValueError("Invalid vehicle blueprint")
    center_y = 1 - 2 * FRACTIONS[case]
    return {"format": "worker-authored-opposite-meeting-request", "case": case,
            "road_opendrive": open_drive(), "road_id": 111294,
            "paved_bounds_y_m": [-4, 4], "paved_center_y_m": 0,
            "ego": {"blueprint": vehicle_blueprint, "start_xyz": [-60, center_y, 0.5],
                    "heading_deg": 0, "requested_speed_mps": 5,
                    "requested_right_half_body_fraction": FRACTIONS[case]},
            "oncoming": {"blueprint": vehicle_blueprint, "start_xyz": [60, 2.5, 0.5],
                           "heading_deg": 180, "requested_speed_mps": 5},
            "cameras": [
                {"name": "overview", "xyz": [0, -13, 24], "yaw": 35, "pitch": -50, "size": [1920, 1080]},
                {"name": "ego_front", "xyz": [1, 0, 2], "yaw": 0, "pitch": -8, "size": [1280, 720], "attach_to_ego": True},
                {"name": "meeting_side", "xyz": [0, -12, 8], "yaw": 90, "pitch": -20, "size": [1280, 720]},
                {"name": "pavement_top", "xyz": [0, 0, 25], "yaw": 0, "pitch": -90, "size": [1280, 720]}],
            "rate_hz": 20, "duration_s": 30, "planned_frames": 600,
            "native_road_verified": False, "physical_success_claimed": False}


def validate_request(request):
    root = ET.fromstring(request["road_opendrive"])
    road = root.find("road")
    if root.tag != "OpenDRIVE" or road is None or road.attrib["id"] != "111294":
        raise ValueError("Authored road identity missing")
    if {lane.attrib["id"] for lane in road.findall("lanes/laneSection/*/lane")} != {"-1", "0", "1"}:
        raise ValueError("One lane per direction missing")
    if {camera["name"] for camera in request.get("cameras", [])} != CAMERAS:
        raise ValueError("Four source camera requests missing")
    if request.get("planned_frames") != 600 or request.get("rate_hz") != 20:
        raise ValueError("30-second capture contract missing")
    if request["native_road_verified"]:
        raise ValueError("Authored request cannot assert Native road verification")
    return {"case": request["case"], "camera_count": 4, "planned_frames": 600,
            "authored_geometry_checked": True, "native_road_verified": False}


if __name__ == "__main__":
    print(json.dumps({case: validate_request(scene_request(case)) for case in FRACTIONS}, indent=2))
