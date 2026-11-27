"""Authored yield approach, near-side crosswalk, traffic and paired stop policies."""

import xml.etree.ElementTree as ET

CASES = {"before_crosswalk": -9.0, "past_crosswalk": -4.0,
         "before_stop_line": -9.0, "past_stop_line": -4.0,
         "before_viewpoint": -9.0, "past_viewpoint": -4.0}
CAMERAS = {"overview", "approach", "reference_corner", "driver_reference"}


def reference_kind(case):
    return "crosswalk" if case.endswith("crosswalk") else (
        "stop_line" if case.endswith("stop_line") else "viewpoint")


def road_xml(kind="crosswalk"):
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", name="C111343-yield-crosswalk",
                  version="1", north="80", south="-80", east="80", west="-80", vendor="full-train-worker")
    for ident, name, x, y, heading in ((111343, "yield_approach", -80, 0, 0),
                                       (111344, "intersecting_highway", 0, -80, 1.57079632679)):
        road = ET.SubElement(root, "road", id=str(ident), name=name, length="160", junction="-1")
        ET.SubElement(road, "link")
        geom = ET.SubElement(ET.SubElement(road, "planView"), "geometry", s="0", x=str(x), y=str(y),
                             hdg=str(heading), length="160")
        ET.SubElement(geom, "line")
        ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation", s="0", a="0", b="0", c="0", d="0")
        lanes = ET.SubElement(road, "lanes")
        ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
        section = ET.SubElement(lanes, "laneSection", s="0")
        for side, lane_id in (("left", 1), ("center", 0), ("right", -1)):
            lane = ET.SubElement(ET.SubElement(section, side), "lane", id=str(lane_id),
                                 type="none" if lane_id == 0 else "driving", level="false")
            if lane_id:
                ET.SubElement(lane, "width", sOffset="0", a="3.5", b="0", c="0", d="0")
        objects = ET.SubElement(road, "objects")
        signals = ET.SubElement(road, "signals")
        if ident == 111343:
            if kind == "crosswalk":
                ET.SubElement(objects, "object", id="near-crosswalk-111343", s="74", t="-1.75",
                              name="near_side_crosswalk", type="crosswalk", orientation="none",
                              zOffset="0", length="2", width="3.5", hdg="0", pitch="0", roll="0")
            elif kind == "stop_line":
                ET.SubElement(objects, "object", id="marked-stop-line-111343", s="74", t="-1.75",
                              name="marked_stop_line", type="stopLine", orientation="none",
                              zOffset="0", length="0.2", width="3.5", hdg="0", pitch="0", roll="0")
            elif kind == "viewpoint":
                ET.SubElement(objects, "object", id="sight-obstruction-111343", s="72", t="-5.2",
                              name="sight_obstruction", type="building", orientation="none",
                              zOffset="0", length="4", width="1", height="3", hdg="0", pitch="0", roll="0")
            else:
                raise ValueError("Unknown stopping reference")
            ET.SubElement(signals, "signal", id="yield-111343", s="70", t="-3.7", name="YIELD",
                          dynamic="no", orientation="+", zOffset="0", country="US", type="205",
                          subtype="0", value="0", unit="", height="0.8", width="0.8")
    return ET.tostring(root, encoding="unicode")


def request(case):
    if case not in CASES:
        raise ValueError("Unknown crosswalk stop policy")
    kind = reference_kind(case)
    return {"format": "worker-authored-yield-crosswalk-request", "case": case,
            "road_opendrive": road_xml(kind), "reference_kind": kind,
            "reference_near_x_m": -6, "reference_far_x_m": -4,
            "crosswalk_near_x_m": -6 if kind == "crosswalk" else None,
            "crosswalk_far_x_m": -4 if kind == "crosswalk" else None,
            "intersection_near_x_m": -3.5, "stop_line_present": kind == "stop_line",
            "ego": {"blueprint": "vehicle.tesla.model3", "start_xyz": [-45, -1.75, 0.5],
                    "heading_deg": 0, "body_length_m": 4.5},
            "intersecting_vehicle": {"blueprint": "vehicle.tesla.model3", "start_xyz": [1.75, -40, 0.5],
                                     "heading_deg": 90, "requested_speed_mps": 5},
            "controller": {"policy": "stop_at_requested_front_position_then_resume",
                           "requested_stop_front_x_m": CASES[case], "safety_stop_assumed_for_fixture": True},
            "cameras": [{"name": "overview", "xyz": [-14, -14, 20], "pitch": -45,
                         "yaw": 35, "size": [1920, 1080], "pose_strategy": "fixed surveyed intersection overview"},
                        {"name": "driver_reference", "xyz": [1, 0, 2], "pitch": -8,
                         "yaw": 0, "attach_to_ego": True, "size": [1280, 720],
                         "pose_strategy": "attached subject approach and intersecting-highway view"},
                        {"name": "reference_corner", "xyz": [-8, -11, 7], "pitch": -25,
                         "yaw": 30, "size": [1280, 720],
                         "pose_strategy": "fixed near-side crosswalk and front-bumper view"},
                        {"name": "approach", "xyz": [11, -10, 9], "pitch": -30,
                         "yaw": 160, "size": [1280, 720],
                         "pose_strategy": "fixed intersecting-traffic and yield-approach view"}],
            "rate_hz": 20, "duration_s": 30, "planned_frames": 600,
            "native_geometry_verified": False, "physical_success_claimed": False}


def validate(value):
    root = ET.fromstring(value["road_opendrive"])
    roads = root.findall("road")
    if root.tag != "OpenDRIVE" or {r.attrib["id"] for r in roads} != {"111343", "111344"}:
        raise ValueError("Intersection roads missing")
    kind = value.get("reference_kind")
    objects = roads[0].findall("objects/object")
    types = {item.attrib.get("type") for item in objects}
    if (kind == "crosswalk" and types != {"crosswalk"}) or (
            kind == "stop_line" and types != {"stopLine"}) or (
            kind == "viewpoint" and types != {"building"}):
        raise ValueError("Stopping reference hierarchy differs")
    if roads[0].find("signals/signal").attrib.get("name") != "YIELD":
        raise ValueError("Yield sign missing")
    if set(c["name"] for c in value["cameras"]) != CAMERAS:
        raise ValueError("Four camera requests missing")
    if any(not c.get("pose_strategy") or not isinstance(c.get("yaw"), (int, float))
           or tuple(c.get("size", [])) != ((1920, 1080) if c["name"] == "overview" else (1280, 720))
           for c in value["cameras"]):
        raise ValueError("Exact camera pose and size plan missing")
    if value["planned_frames"] != 600 or value["rate_hz"] != 20 or value["native_geometry_verified"]:
        raise ValueError("Capture duration or source assertion invalid")
    return {"case": value["case"], "road_count": 2, "camera_count": 4,
            "planned_frames": 600, "authored_request_checked": True, "native_geometry_verified": False}
