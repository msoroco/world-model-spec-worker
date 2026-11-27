"""Authored one-way two-lane marked and intersection-unmarked requests."""

import xml.etree.ElementTree as ET
import math

CASES = {"false", "true", "unmarked_false", "unmarked_true"}
CAMERAS = {"overview", "driver_reference", "reference_corner", "approach"}


def road_xml(unmarked=False):
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
    if unmarked:
        ET.SubElement(objects, "object", id="intersection-mouth-146108", s="78", t="-3.5",
                      name="intersection_unmarked_crossing_reference", type="none",
                      orientation="none", zOffset="0", length="4", width="7",
                      hdg="0", pitch="0", roll="0")
        for ident, y, length, junction_id in ((146109, -20, 13, -1),
                                              (146110, -7, 14, 146108),
                                              (146111, 7, 13, -1)):
            crossing_road = ET.SubElement(root, "road", id=str(ident),
                                          name="intersection_cross_road", length=str(length),
                                          junction=str(junction_id))
            link = ET.SubElement(crossing_road, "link")
            if ident == 146109:
                ET.SubElement(link, "successor", elementType="junction", elementId="146108")
            elif ident == 146111:
                ET.SubElement(link, "predecessor", elementType="junction", elementId="146108")
            else:
                ET.SubElement(link, "predecessor", elementType="road", elementId="146109", contactPoint="end")
                ET.SubElement(link, "successor", elementType="road", elementId="146111", contactPoint="start")
            geometry = ET.SubElement(ET.SubElement(crossing_road, "planView"),
                                     "geometry", s="0", x="0", y=str(y),
                                     hdg=str(math.pi / 2), length=str(length))
            ET.SubElement(geometry, "line")
            ET.SubElement(ET.SubElement(crossing_road, "elevationProfile"),
                          "elevation", s="0", a="0", b="0", c="0", d="0")
            crossing_lanes = ET.SubElement(crossing_road, "lanes")
            ET.SubElement(crossing_lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
            section_cross = ET.SubElement(crossing_lanes, "laneSection", s="0")
            ET.SubElement(section_cross, "left")
            ET.SubElement(ET.SubElement(section_cross, "center"), "lane", id="0", type="none", level="false")
            right_cross = ET.SubElement(section_cross, "right")
            cross_lane = ET.SubElement(right_cross, "lane", id="-1", type="driving", level="false")
            ET.SubElement(cross_lane, "width", sOffset="0", a="3.5", b="0", c="0", d="0")
            ET.SubElement(crossing_road, "objects")
            ET.SubElement(crossing_road, "signals")
        junction = ET.SubElement(root, "junction", id="146108", name="crossing-intersection")
        connection = ET.SubElement(junction, "connection", id="0", incomingRoad="146109",
                                   connectingRoad="146110", contactPoint="start")
        ET.SubElement(connection, "laneLink", **{"from": "-1", "to": "-1"})
    else:
        ET.SubElement(objects, "object", id="marked-crosswalk-146108", s="78", t="-3.5",
                      name="marked_crosswalk", type="crosswalk", orientation="none",
                      zOffset="0", length="4", width="7", hdg="0", pitch="0", roll="0")
    ET.SubElement(road, "signals")
    return ET.tostring(root, encoding="unicode")


def request(case):
    if case not in CASES:
        raise ValueError("Unknown pass policy")
    unmarked = case.startswith("unmarked_")
    return {"format": "worker-authored-crosswalk-pass-request", "case": case,
            "crosswalk_kind_requested": "unmarked_intersection" if unmarked else "marked",
            "road_opendrive": road_xml(unmarked), "crosswalk_x_m": [-2, 2],
            "lead": {"blueprint": "vehicle.tesla.model3", "center_xy_m": [-6, -1.75],
                     "body_length_m": 4.5, "requested_stopped_for_pedestrian": True},
            "pedestrian": {"blueprint": "walker.pedestrian.0001", "start_xy_m": [0, -8],
                           "crossing_x_m": 0, "requested_crossing_interval_frames": [120, 220]},
            "ego": {"blueprint": "vehicle.tesla.model3", "start_xy_m": [-40, -1.75],
                    "heading_deg": 0, "body_length_m": 4.5},
            "controller": {"policy": "pass_adjacent_lane" if case.endswith("true") else "hold_behind_lead",
                           "adjacent_lane_y_m": -5.25, "hold_center_x_m": -13},
            "cameras": [{"name": "overview", "xyz": [-5, -10, 20], "pitch": -45, "size": [1920, 1080]},
                        {"name": "driver_reference", "xyz": [1, 0, 2], "pitch": -8,
                         "attach_to_ego": True, "size": [1280, 720]},
                        {"name": "reference_corner", "xyz": [3, -12, 8], "pitch": -25, "size": [1280, 720]},
                        {"name": "approach", "xyz": [-12, -8, 6], "pitch": -15, "size": [1280, 720]}],
            "rate_hz": 20, "duration_s": 30, "planned_frames": 600,
            "native_road_verified": False, "physical_success_claimed": False}


def validate(value):
    root = ET.fromstring(value["road_opendrive"])
    road = root.find("road")
    if root.tag != "OpenDRIVE" or road is None or road.attrib["id"] != "146108":
        raise ValueError("One-way road request missing")
    if len(road.findall("lanes/laneSection/right/lane")) != 2:
        raise ValueError("Two same-direction lanes missing")
    if value["crosswalk_kind_requested"] == "marked":
        if road.find("objects/object").attrib.get("type") != "crosswalk":
            raise ValueError("Marked crosswalk missing")
    elif value["crosswalk_kind_requested"] == "unmarked_intersection":
        if (root.find("junction/connection/laneLink") is None or
                len(root.findall("road")) != 4 or
                road.find("objects/object").attrib.get("type") == "crosswalk"):
            raise ValueError("Unmarked intersection reference missing or painted")
    else:
        raise ValueError("Crosswalk kind missing")
    if set(c["name"] for c in value["cameras"]) != CAMERAS:
        raise ValueError("Four camera requests missing")
    if value["planned_frames"] != 600 or value["rate_hz"] != 20 or value["native_road_verified"]:
        raise ValueError("Duration or source assertion invalid")
    return {"case": value["case"], "camera_count": 4, "planned_frames": 600,
            "authored_request_checked": True, "native_road_verified": False}
