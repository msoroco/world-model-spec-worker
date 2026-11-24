"""Deterministic C229398 curb scene requests; Native feasibility is unproven."""

import xml.etree.ElementTree as ET

CASES_IN = {"16": 16.0, "18": 18.0, "20": 20.0}
VARIANTS = {
    "primary": {"spawn_x_m": -28.0, "approach_speed_mps": 2.5, "steering_gain": 0.8},
    "fallback1": {"spawn_x_m": -36.0, "approach_speed_mps": 2.5, "steering_gain": 0.8},
    "fallback2": {"spawn_x_m": -28.0, "approach_speed_mps": 1.5, "steering_gain": 0.8},
    "fallback3": {"spawn_x_m": -28.0, "approach_speed_mps": 2.5, "steering_gain": 0.65},
}


def road_xml():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", name="C229398-curbed-road",
                  version="1", north="8", south="-8", east="60", west="-60",
                  vendor="full-train-worker")
    road = ET.SubElement(root, "road", id="229398", name="curbed_highway",
                         length="120", junction="-1")
    ET.SubElement(road, "link")
    geometry = ET.SubElement(ET.SubElement(road, "planView"), "geometry",
                             s="0", x="-60", y="0", hdg="0", length="120")
    ET.SubElement(geometry, "line")
    ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation",
                  s="0", a="0", b="0", c="0", d="0")
    lanes = ET.SubElement(road, "lanes")
    ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
    section = ET.SubElement(lanes, "laneSection", s="0")
    left = ET.SubElement(ET.SubElement(section, "left"), "lane", id="1",
                         type="driving", level="false")
    ET.SubElement(left, "width", sOffset="0", a="4", b="0", c="0", d="0")
    ET.SubElement(ET.SubElement(section, "center"), "lane", id="0", type="none", level="false")
    right = ET.SubElement(ET.SubElement(section, "right"), "lane", id="-1",
                          type="driving", level="false")
    ET.SubElement(right, "width", sOffset="0", a="4", b="0", c="0", d="0")
    objects = ET.SubElement(road, "objects")
    for name, lateral in (("right_curb", -4), ("left_curb", 4)):
        ET.SubElement(objects, "object", id=name, name=name, type="curb",
                      s="0", t=str(lateral), zOffset="0", length="120",
                      width="0.15", hdg="0", pitch="0", roll="0", orientation="none")
    ET.SubElement(road, "signals")
    return ET.tostring(root, encoding="unicode")


def request(case, variant="primary"):
    if case not in CASES_IN or variant not in VARIANTS:
        raise ValueError("Unknown case or candidate")
    tuning = VARIANTS[variant]
    target_wheel_y_m = -4 + CASES_IN[case] * 0.0254
    return {
        "format": "worker-c229398-native-scene-request", "case": case,
        "candidate": variant, "road_opendrive": road_xml(),
        "ego": {"blueprint": "vehicle.tesla.model3",
                "spawn_xyz_m": [tuning["spawn_x_m"], -2.1, 0.5],
                "heading_deg": 0},
        "controller": {"policy": "approach_and_parallel_park",
                       "approach_speed_mps": tuning["approach_speed_mps"],
                       "steering_gain": tuning["steering_gain"],
                       "requested_right_wheel_outer_y_m": target_wheel_y_m,
                       "requested_gap_in": CASES_IN[case],
                       "parking_brake_after_settling": True},
        "capture": {"rate_hz": 20, "duration_s": 30, "frames": 600,
                    "source_cameras": ["overview", "ego_front", "curb_side", "wheel_closeup"]},
        "native_curb_verified": False, "physical_success_claimed": False}


def validate_request(value):
    root = ET.fromstring(value["road_opendrive"])
    road = root.find("road")
    if road is None or road.attrib.get("id") != "229398":
        raise ValueError("C229398 road identity missing")
    if {obj.attrib["name"] for obj in road.findall("objects/object")} != {"right_curb", "left_curb"}:
        raise ValueError("Adjacent curbs missing")
    if value["capture"] != {"rate_hz": 20, "duration_s": 30, "frames": 600,
                             "source_cameras": ["overview", "ego_front", "curb_side", "wheel_closeup"]}:
        raise ValueError("Capture contract changed")
    if value["native_curb_verified"] or value["physical_success_claimed"]:
        raise ValueError("Unobserved physical assertion")
    return True
