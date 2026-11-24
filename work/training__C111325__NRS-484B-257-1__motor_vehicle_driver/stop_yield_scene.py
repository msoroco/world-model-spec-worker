"""Authored crossroad, governing stop sign, actors, controls and capture request."""

import xml.etree.ElementTree as ET

CASES = {"complete_stop_then_yield", "roll_through_conflict"}
CAMERAS = {"overview", "ego_front", "stop_line_side", "through_road"}


def open_drive():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", name="C111325-stop-through-crossroad",
                  version="1", north="100", south="-100", east="100", west="-100", vendor="full-train-worker")
    for road_id, road_name, x, y, heading in ((111325, "stop_approach", -80, 0, 0),
                                              (111326, "through_highway", 0, -80, 1.57079632679)):
        road = ET.SubElement(root, "road", id=str(road_id), name=road_name, length="160", junction="-1")
        ET.SubElement(road, "link")
        geom = ET.SubElement(ET.SubElement(road, "planView"), "geometry", s="0", x=str(x), y=str(y),
                             hdg=str(heading), length="160")
        ET.SubElement(geom, "line")
        ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation", s="0", a="0", b="0", c="0", d="0")
        lanes = ET.SubElement(road, "lanes")
        ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
        section = ET.SubElement(lanes, "laneSection", s="0")
        for side, ident in (("left", 1), ("center", 0), ("right", -1)):
            lane = ET.SubElement(ET.SubElement(section, side), "lane", id=str(ident),
                                 type="none" if ident == 0 else "driving", level="false")
            if ident:
                ET.SubElement(lane, "width", sOffset="0", a="3.5", b="0", c="0", d="0")
        ET.SubElement(road, "objects")
        signals = ET.SubElement(road, "signals")
        if road_id == 111325:
            ET.SubElement(signals, "signal", id="stop-111325", s="74", t="-3.7", name="STOP",
                          dynamic="no", orientation="+", zOffset="0", country="US", type="206", subtype="0",
                          value="0", unit="", height="0.8", width="0.8")
    return ET.tostring(root, encoding="unicode")


def request(case):
    if case not in CASES:
        raise ValueError("Unknown stop/yield case")
    return {"format": "worker-authored-stop-yield-request", "case": case,
            "road_opendrive": open_drive(), "stop_line_x_m": -6,
            "intersection_near_x_m": -3.5, "intersection_far_x_m": 3.5,
            "stop_line_marking": {"endpoints_xy_m": [[-6, -3.5], [-6, 0]], "width_m": 0.4},
            "governing_sign": "stop-111325", "police_controlling": False, "signal_controlling": False,
            "ego": {"blueprint": "vehicle.tesla.model3", "start_xyz": [-45, -1.75, 0.5],
                    "heading_deg": 0, "body_length_m": 4.5},
            "through_vehicle": {"blueprint": "vehicle.tesla.model3", "start_xyz": [1.75, -50, 0.5],
                                "heading_deg": 90, "requested_speed_mps": 5},
            "controller": {"policy": case, "stop_front_x_m": -7,
                           "wait_for_through_vehicle_clearance": case == "complete_stop_then_yield"},
            "cameras": [{"name": "overview", "xyz": [-14, -14, 20], "pitch": -45, "size": [1920, 1080]},
                        {"name": "ego_front", "xyz": [1, 0, 2], "pitch": -8, "attach_to_ego": True, "size": [1280, 720]},
                        {"name": "stop_line_side", "xyz": [-8, -11, 6], "pitch": -20, "size": [1280, 720]},
                        {"name": "through_road", "xyz": [12, -5, 9], "pitch": -30, "size": [1280, 720]}],
            "rate_hz": 20, "duration_s": 30, "planned_frames": 600,
            "native_geometry_verified": False, "physical_success_claimed": False}


def validate(requested):
    root = ET.fromstring(requested["road_opendrive"])
    roads = root.findall("road")
    if root.tag != "OpenDRIVE" or {r.attrib["id"] for r in roads} != {"111325", "111326"}:
        raise ValueError("Two-road intersection missing")
    if roads[0].find("signals/signal").attrib.get("name") != "STOP":
        raise ValueError("Stop sign missing")
    if requested["stop_line_marking"]["endpoints_xy_m"][0][0] != requested["stop_line_x_m"]:
        raise ValueError("Marked stop line missing")
    if set(c["name"] for c in requested["cameras"]) != CAMERAS:
        raise ValueError("Four camera requests missing")
    if requested["planned_frames"] != 600 or requested["rate_hz"] != 20:
        raise ValueError("30-second capture request missing")
    if requested["police_controlling"] or requested["signal_controlling"] or requested["native_geometry_verified"]:
        raise ValueError("Control exception or unsourced Native claim")
    return {"case": requested["case"], "road_count": 2, "camera_count": 4,
            "planned_frames": 600, "authored_request_checked": True, "native_geometry_verified": False}
