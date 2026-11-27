"""Three same-direction lanes for a conditional emergency move-over request."""
import xml.etree.ElementTree as ET


ROAD_ID = 405647
EMERGENCY_LANE = -1
ADJACENT_LANE = -2
NONADJACENT_LANE = -3


def road_xml():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", name="C405647-emergency-lanes",
                  version="1", north="12", south="-14", east="120", west="-120", vendor="worker")
    road = ET.SubElement(root, "road", id=str(ROAD_ID), name="emergency_move_over",
                         length="240", junction="-1")
    ET.SubElement(road, "link")
    ET.SubElement(ET.SubElement(road, "planView"), "geometry", s="0", x="-120", y="0",
                  hdg="0", length="240").append(ET.Element("line"))
    ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation", s="0", a="0",
                  b="0", c="0", d="0")
    lanes = ET.SubElement(road, "lanes")
    ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
    section = ET.SubElement(lanes, "laneSection", s="0")
    ET.SubElement(ET.SubElement(section, "left"), "lane", id="1", type="none", level="false")
    center = ET.SubElement(section, "center")
    ET.SubElement(center, "lane", id="0", type="none", level="false")
    right = ET.SubElement(section, "right")
    for lane_id in (EMERGENCY_LANE, ADJACENT_LANE, NONADJACENT_LANE):
        lane = ET.SubElement(right, "lane", id=str(lane_id), type="driving", level="false")
        ET.SubElement(lane, "width", sOffset="0", a="3.5", b="0", c="0", d="0")
        ET.SubElement(lane, "roadMark", sOffset="0", type="broken", color="white", width="0.12")
    ET.SubElement(road, "objects")
    ET.SubElement(road, "signals")
    return ET.tostring(root, encoding="unicode")


def lane_centers():
    return {EMERGENCY_LANE: -1.75, ADJACENT_LANE: -5.25, NONADJACENT_LANE: -8.75}


def check():
    tree = ET.fromstring(road_xml())
    road = tree.find("road")
    lanes = road.find("lanes/laneSection/right").findall("lane")
    if road.get("id") != str(ROAD_ID) or [int(x.get("id")) for x in lanes] != [-1, -2, -3]:
        raise ValueError("Three-lane construction changed")
    if any(float(x.find("width").get("a")) != 3.5 for x in lanes):
        raise ValueError("Lane widths changed")
    return {"road_id": ROAD_ID, "lane_ids": [-1, -2, -3],
            "lane_centers_y_m": lane_centers(), "physical_realization_verified": False}
