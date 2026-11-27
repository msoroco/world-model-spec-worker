"""Source-preserving one-way tunnel variant for the subsection 3 exception.

This is an authored CPU request. The original Native road survey and physical
tunnel/view still need review before any legal or physical conclusion.
"""

import json
import xml.etree.ElementTree as ET

from tunnel_scene import CAMERAS, LANE_WIDTH_M


ROAD_ID = 313131
PORTAL_X_M = 0.0
HIGHWAY_CENTRE_Y_M = -LANE_WIDTH_M
RIGHT_Y_M = -1.5 * LANE_WIDTH_M
LEFT_Y_M = -0.5 * LANE_WIDTH_M
TARGETS = {"one_way_right": RIGHT_Y_M, "one_way_left": LEFT_Y_M}


def road_xml():
    """Two eastbound right-hand lanes; no westbound driving lane."""
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4",
                  name="C313130-one-way-tunnel-approach", version="1",
                  north="15", south="-15", east="100", west="-100",
                  vendor="full-train-worker")
    road = ET.SubElement(root, "road", id=str(ROAD_ID),
                         name="C313130_one_way_tunnel_approach",
                         length="200", junction="-1")
    ET.SubElement(road, "link")
    geometry = ET.SubElement(ET.SubElement(road, "planView"), "geometry",
                             s="0", x="-100", y="0", hdg="0", length="200")
    ET.SubElement(geometry, "line")
    ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation",
                  s="0", a="0", b="0", c="0", d="0")
    lanes = ET.SubElement(road, "lanes")
    ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
    section = ET.SubElement(lanes, "laneSection", s="0")
    ET.SubElement(section, "left")
    centre = ET.SubElement(section, "center")
    ET.SubElement(centre, "lane", id="0", type="none", level="false")
    right = ET.SubElement(section, "right")
    for lane_id in (-1, -2):
        lane = ET.SubElement(right, "lane", id=str(lane_id), type="driving", level="false")
        ET.SubElement(lane, "width", sOffset="0", a=str(LANE_WIDTH_M),
                      b="0", c="0", d="0")
    ET.SubElement(road, "objects")
    ET.SubElement(road, "signals")
    return ET.tostring(root, encoding="unicode")


def request(case):
    if case not in TARGETS:
        raise ValueError("Unknown one-way tunnel case")
    value = {"format": "worker-one-way-tunnel-request",
             "case": case, "road_opendrive": road_xml(),
             "road_id": ROAD_ID, "portal_x_m": PORTAL_X_M,
             "highway_centre_y_m": HIGHWAY_CENTRE_Y_M,
             "ego_start_xyz_m": [-65, RIGHT_Y_M, 1.5],
             "requested_target_y_m": TARGETS[case],
             "original_direction_readback": {
                 "required_lane_ids": [-1, -2],
                 "forbidden_opposing_driving_lane_ids": [1, 2],
                 "must_retain_native_map_hash": True,
                 "one_way_legal_classification": "independent_review_required"},
             "tunnel_blueprint": "static.prop.tunnel",
             "occluder_blueprint": "static.prop.hedge",
             "cameras": sorted(CAMERAS), "rate_hz": 20,
             "duration_frames": 600, "duration_s": 30,
             "physical_verified": False, "legal_verdict": None}
    validate(value)
    return value


def validate(value):
    root = ET.fromstring(value["road_opendrive"])
    road = root.find("road")
    if root.tag != "OpenDRIVE" or road is None or road.get("id") != str(ROAD_ID):
        raise ValueError("One-way source road identity missing")
    lanes = road.findall("lanes/laneSection/*/lane")
    actual = {int(lane.get("id")): lane.get("type") for lane in lanes}
    if actual != {0: "none", -1: "driving", -2: "driving"}:
        raise ValueError("One-way eastbound lane geometry missing")
    if (value.get("case") not in TARGETS or
            value.get("requested_target_y_m") != TARGETS[value["case"]] or
            value.get("highway_centre_y_m") != HIGHWAY_CENTRE_Y_M):
        raise ValueError("One-way controlled lateral target changed")
    survey = value.get("original_direction_readback", {})
    if (survey.get("required_lane_ids") != [-1, -2] or
            survey.get("forbidden_opposing_driving_lane_ids") != [1, 2] or
            survey.get("must_retain_native_map_hash") is not True or
            survey.get("one_way_legal_classification") != "independent_review_required"):
        raise ValueError("Original one-way Native direction proof missing")
    if (sorted(value.get("cameras", [])) != sorted(CAMERAS) or
            value.get("rate_hz") != 20 or value.get("duration_frames") != 600 or
            value.get("duration_s") != 30 or value.get("physical_verified") is not False or
            value.get("legal_verdict") is not None):
        raise ValueError("One-way camera, duration or review contract changed")
    return {"case": value["case"], "authored_one_way_lanes": [-1, -2],
            "original_native_survey_pending": True}


if __name__ == "__main__":
    print(json.dumps({case: validate(request(case)) for case in TARGETS}, indent=2))
