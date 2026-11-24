"""Authored one-way curb road and three wheel-clearance parking requests."""

import xml.etree.ElementTree as ET

CLEARANCES_IN = {"16": 16, "18": 18, "20": 20}
CAMERAS = {"overview", "ego_front", "curb_side", "wheel_closeup"}


def road_xml():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", name="C149985-right-curb",
                  version="1", north="4", south="-4", east="80", west="-80", vendor="full-train-worker")
    road = ET.SubElement(root, "road", id="149985", name="one_way_curbed_highway", length="160", junction="-1")
    ET.SubElement(road, "link")
    geom = ET.SubElement(ET.SubElement(road, "planView"), "geometry", s="0", x="-80", y="0", hdg="0", length="160")
    ET.SubElement(geom, "line")
    ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation", s="0", a="0", b="0", c="0", d="0")
    lanes = ET.SubElement(road, "lanes")
    ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
    section = ET.SubElement(lanes, "laneSection", s="0")
    left = ET.SubElement(ET.SubElement(section, "left"), "lane", id="1", type="driving", level="false")
    ET.SubElement(left, "width", sOffset="0", a="4", b="0", c="0", d="0")
    ET.SubElement(ET.SubElement(section, "center"), "lane", id="0", type="none", level="false")
    right = ET.SubElement(ET.SubElement(section, "right"), "lane", id="-1", type="driving", level="false")
    ET.SubElement(right, "width", sOffset="0", a="4", b="0", c="0", d="0")
    objects = ET.SubElement(road, "objects")
    for name, t in (("right_curb", -4), ("left_curb", 4)):
        ET.SubElement(objects, "object", id=name, s="0", t=str(t), name=name,
                      type="curb", orientation="none", zOffset="0", length="160", width="0.15",
                      hdg="0", pitch="0", roll="0")
    ET.SubElement(road, "signals")
    return ET.tostring(root, encoding="unicode")


def request(case):
    if case not in CLEARANCES_IN:
        raise ValueError("Unknown curb clearance request")
    gap_m = CLEARANCES_IN[case] * 0.0254
    wheel_y = -4 + gap_m
    return {"format": "worker-authored-right-curb-request", "case": case,
            "road_opendrive": road_xml(), "right_curb_y_m": -4, "left_curb_y_m": 4,
            "ego": {"blueprint": "vehicle.tesla.model3", "initial_xyz": [-35, -2, 0.5],
                    "heading_deg": 0, "right_wheel_track_half_m": 0.8,
                    "requested_park_center_xy_m": [0, wheel_y + 0.8]},
            "controller": {"policy": "parallel_park_at_right_wheel_clearance",
                           "requested_gap_in": CLEARANCES_IN[case], "target_right_wheel_outer_y_m": wheel_y,
                           "target_heading_deg": 0, "parking_brake_after_settling": True},
            "cameras": [{"name": "overview", "xyz": [0, -12, 18], "pitch": -40, "size": [1920, 1080]},
                        {"name": "ego_front", "xyz": [1, 0, 2], "pitch": -8,
                         "attach_to_ego": True, "size": [1280, 720]},
                        {"name": "curb_side", "xyz": [2, -8, 5], "pitch": -18, "size": [1280, 720]},
                        {"name": "wheel_closeup", "xyz": [0, -5.5, 2], "pitch": -15, "size": [1280, 720]}],
            "rate_hz": 20, "duration_s": 30, "planned_frames": 600,
            "native_curb_verified": False, "physical_success_claimed": False}


def validate(value):
    root = ET.fromstring(value["road_opendrive"])
    road = root.find("road")
    if root.tag != "OpenDRIVE" or road is None or road.attrib["id"] != "149985":
        raise ValueError("One-way curb road missing")
    if {o.attrib["name"] for o in road.findall("objects/object")} != {"right_curb", "left_curb"}:
        raise ValueError("Adjacent curbs missing")
    if set(c["name"] for c in value["cameras"]) != CAMERAS:
        raise ValueError("Four camera requests missing")
    if value["planned_frames"] != 600 or value["rate_hz"] != 20 or value["native_curb_verified"]:
        raise ValueError("Duration or source assertion invalid")
    return {"case": value["case"], "camera_count": 4, "planned_frames": 600,
            "authored_request_checked": True, "native_curb_verified": False}
