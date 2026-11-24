"""Authored one-way two-lane marked-crosswalk pass/no-pass requests."""

import xml.etree.ElementTree as ET

CASES = {"false", "true"}
CAMERAS = {"overview", "ego_front", "crosswalk_side", "lead_rear"}


def road_xml():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", name="C146108-crosswalk-pass",
                  version="1", north="10", south="-10", east="80", west="-80", vendor="full-train-worker")
    road = ET.SubElement(root, "road", id="146108", name="one_way_two_lane", length="160", junction="-1")
    ET.SubElement(road, "link")
    geom = ET.SubElement(ET.SubElement(road, "planView"), "geometry", s="0", x="-80", y="0", hdg="0", length="160")
    ET.SubElement(geom, "line")
    ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation", s="0", a="0", b="0", c="0", d="0")
    lanes = ET.SubElement(road, "lanes")
    ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
    section = ET.SubElement(lanes, "laneSection", s="0")
    ET.SubElement(section, "left")
    center = ET.SubElement(section, "center")
    ET.SubElement(center, "lane", id="0", type="none", level="false")
    right = ET.SubElement(section, "right")
    for ident in (-1, -2):
        lane = ET.SubElement(right, "lane", id=str(ident), type="driving", level="false")
        ET.SubElement(lane, "width", sOffset="0", a="3.5", b="0", c="0", d="0")
    objects = ET.SubElement(road, "objects")
    ET.SubElement(objects, "object", id="marked-crosswalk-146108", s="78", t="-3.5",
                  name="marked_crosswalk", type="crosswalk", orientation="none",
                  zOffset="0", length="4", width="7", hdg="0", pitch="0", roll="0")
    ET.SubElement(road, "signals")
    return ET.tostring(root, encoding="unicode")


def request(case):
    if case not in CASES:
        raise ValueError("Unknown pass policy")
    return {"format": "worker-authored-crosswalk-pass-request", "case": case,
            "road_opendrive": road_xml(), "crosswalk_x_m": [-2, 2],
            "lead": {"blueprint": "vehicle.tesla.model3", "center_xy_m": [-6, -1.75],
                     "body_length_m": 4.5, "requested_stopped_for_pedestrian": True},
            "pedestrian": {"blueprint": "walker.pedestrian.0001", "start_xy_m": [0, -8],
                           "crossing_x_m": 0, "requested_crossing_interval_frames": [120, 220]},
            "ego": {"blueprint": "vehicle.tesla.model3", "start_xy_m": [-40, -1.75],
                    "heading_deg": 0, "body_length_m": 4.5},
            "controller": {"policy": "pass_adjacent_lane" if case == "true" else "hold_behind_lead",
                           "adjacent_lane_y_m": -5.25, "hold_center_x_m": -13},
            "cameras": [{"name": "overview", "xyz": [-5, -10, 20], "pitch": -45, "size": [1920, 1080]},
                        {"name": "ego_front", "xyz": [1, 0, 2], "pitch": -8,
                         "attach_to_ego": True, "size": [1280, 720]},
                        {"name": "crosswalk_side", "xyz": [3, -12, 8], "pitch": -25, "size": [1280, 720]},
                        {"name": "lead_rear", "xyz": [-12, -8, 6], "pitch": -15, "size": [1280, 720]}],
            "rate_hz": 20, "duration_s": 30, "planned_frames": 600,
            "native_road_verified": False, "physical_success_claimed": False}


def validate(value):
    root = ET.fromstring(value["road_opendrive"])
    road = root.find("road")
    if root.tag != "OpenDRIVE" or road is None or road.attrib["id"] != "146108":
        raise ValueError("One-way road request missing")
    if len(road.findall("lanes/laneSection/right/lane")) != 2:
        raise ValueError("Two same-direction lanes missing")
    if road.find("objects/object").attrib.get("type") != "crosswalk":
        raise ValueError("Marked crosswalk missing")
    if set(c["name"] for c in value["cameras"]) != CAMERAS:
        raise ValueError("Four camera requests missing")
    if value["planned_frames"] != 600 or value["rate_hz"] != 20 or value["native_road_verified"]:
        raise ValueError("Duration or source assertion invalid")
    return {"case": value["case"], "camera_count": 4, "planned_frames": 600,
            "authored_request_checked": True, "native_road_verified": False}
