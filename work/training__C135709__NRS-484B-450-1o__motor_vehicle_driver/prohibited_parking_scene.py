"""Authored narrow-road no-parking zone and matched park requests."""

import xml.etree.ElementTree as ET

CASES = {"false": 12.0, "true": -10.0}
CAMERAS = {"overview", "ego_front", "restriction_sign", "curb_side"}


def road_xml():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", name="C135709-device-parking",
                  version="1", north="5", south="-5", east="70", west="-70", vendor="full-train-worker")
    road = ET.SubElement(root, "road", id="135709", name="narrow_road", length="140", junction="-1")
    ET.SubElement(road, "link")
    geom = ET.SubElement(ET.SubElement(road, "planView"), "geometry", s="0", x="-70", y="0", hdg="0", length="140")
    ET.SubElement(geom, "line")
    ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation", s="0", a="0", b="0", c="0", d="0")
    lanes = ET.SubElement(road, "lanes")
    ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
    section = ET.SubElement(lanes, "laneSection", s="0")
    for side, ident in (("left", 1), ("center", 0), ("right", -1)):
        lane = ET.SubElement(ET.SubElement(section, side), "lane", id=str(ident),
                             type="none" if ident == 0 else "driving", level="false")
        if ident:
            ET.SubElement(lane, "width", sOffset="0", a="2.75", b="0", c="0", d="0")
    ET.SubElement(road, "objects")
    signals = ET.SubElement(road, "signals")
    ET.SubElement(signals, "signal", id="official-no-parking-135709", s="50", t="-3.1",
                  name="NO_PARKING", dynamic="no", orientation="+", zOffset="0", country="US",
                  type="no_parking", subtype="0", value="0", unit="", height="0.8", width="0.6")
    return ET.tostring(root, encoding="unicode")


def request(case):
    if case not in CASES:
        raise ValueError("Unknown zone comparison case")
    return {"format": "worker-authored-device-parking-request", "case": case,
            "road_opendrive": road_xml(), "device_id": "official-no-parking-135709",
            "governed_zone_x_m": [-20, 0], "device_condition": "all_hours_all_vehicle_classes",
            "ego": {"blueprint": "vehicle.tesla.model3", "initial_xyz": [-45, -1.25, 0.5],
                    "body_length_m": 4.5},
            "controller": {"policy": "approach_park_apply_brake", "park_center_x_m": CASES[case],
                           "requested_stationary_start_frame": 200,
                           "requested_stationary_end_frame": 450},
            "cameras": [{"name": "overview", "xyz": [-5, -12, 18], "pitch": -40, "size": [1920, 1080]},
                        {"name": "ego_front", "xyz": [1, 0, 2], "pitch": -8,
                         "attach_to_ego": True, "size": [1280, 720]},
                        {"name": "restriction_sign", "xyz": [-22, -7, 5], "pitch": -15, "size": [1280, 720]},
                        {"name": "curb_side", "xyz": [-5, -8, 7], "pitch": -25, "size": [1280, 720]}],
            "rate_hz": 20, "duration_s": 30, "planned_frames": 600,
            "native_device_verified": False, "physical_success_claimed": False}


def validate(value):
    root = ET.fromstring(value["road_opendrive"])
    road = root.find("road")
    if root.tag != "OpenDRIVE" or road is None or road.attrib["id"] != "135709":
        raise ValueError("Narrow-road geometry missing")
    if road.find("signals/signal").attrib.get("name") != "NO_PARKING":
        raise ValueError("Regulatory device missing")
    if set(c["name"] for c in value["cameras"]) != CAMERAS:
        raise ValueError("Four camera requests missing")
    if value["planned_frames"] != 600 or value["rate_hz"] != 20 or value["native_device_verified"]:
        raise ValueError("Duration or source assertion invalid")
    return {"case": value["case"], "camera_count": 4, "planned_frames": 600,
            "authored_request_checked": True, "native_device_verified": False}
