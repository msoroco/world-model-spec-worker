"""Authored roundabout road request and source geometry checks.

The OpenDRIVE topology is a Native proposal. A CARLA map readback and the
original video must establish the realized ring and entry boundary.
"""
import json
import math
import xml.etree.ElementTree as ET


RADIUS_M = 20.0
ROAD_WIDTH_M = 3.5
RING_LENGTH_M = 2 * math.pi * RADIUS_M


def _lane(section, side, lane_id):
    lane = ET.SubElement(ET.SubElement(section, side), "lane", id=str(lane_id),
                         type="driving", level="false")
    ET.SubElement(lane, "width", sOffset="0", a=str(ROAD_WIDTH_M), b="0", c="0", d="0")
    ET.SubElement(lane, "roadMark", sOffset="0", type="broken", color="white", width=".10")


def open_drive():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", name="C239014 roundabout",
                  version="1.00", north="55", south="-55", east="55", west="-55")
    ring = ET.SubElement(root, "road", id="1", name="circulatory-roadway",
                         length=f"{RING_LENGTH_M:.9f}", junction="-1")
    links = ET.SubElement(ring, "link")
    ET.SubElement(links, "predecessor", elementType="road", elementId="1", contactPoint="end")
    ET.SubElement(links, "successor", elementType="road", elementId="1", contactPoint="start")
    geometry = ET.SubElement(ET.SubElement(ring, "planView"), "geometry", s="0", x="0",
                             y=str(-RADIUS_M), hdg="0", length=f"{RING_LENGTH_M:.9f}")
    ET.SubElement(geometry, "arc", curvature=str(1 / RADIUS_M))
    ET.SubElement(ET.SubElement(ring, "elevationProfile"), "elevation",
                  s="0", a="0", b="0", c="0", d="0")
    lanes = ET.SubElement(ring, "lanes")
    ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
    section = ET.SubElement(lanes, "laneSection", s="0")
    ET.SubElement(ET.SubElement(section, "center"), "lane", id="0", type="none", level="false")
    _lane(section, "right", -1)
    approach = ET.SubElement(root, "road", id="2", name="south-entry-approach",
                             length="32", junction="-1")
    ET.SubElement(ET.SubElement(approach, "link"), "successor", elementType="road",
                  elementId="1", contactPoint="start")
    geometry = ET.SubElement(ET.SubElement(approach, "planView"), "geometry", s="0",
                             x="0", y="-52", hdg=str(math.pi / 2), length="32")
    ET.SubElement(geometry, "line")
    ET.SubElement(ET.SubElement(approach, "elevationProfile"), "elevation",
                  s="0", a="0", b="0", c="0", d="0")
    lanes = ET.SubElement(approach, "lanes")
    ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
    section = ET.SubElement(lanes, "laneSection", s="0")
    ET.SubElement(ET.SubElement(section, "center"), "lane", id="0", type="none", level="false")
    _lane(section, "right", -1)
    return ET.tostring(root, encoding="unicode")


def check():
    root = ET.fromstring(open_drive())
    roads = root.findall("road")
    if len(roads) != 2 or roads[0].find("planView/geometry/arc") is None:
        raise ValueError("Authored ring geometry absent")
    if roads[1].find("planView/geometry/line") is None:
        raise ValueError("Authored approach geometry absent")
    if abs(float(roads[0].attrib["length"]) - RING_LENGTH_M) > 1e-6:
        raise ValueError("Ring circumference differs")
    if roads[1].find("link/successor").attrib["elementId"] != "1":
        raise ValueError("Approach-to-ring link absent")
    return {"authored_ring_radius_m": RADIUS_M, "authored_approach_length_m": 32,
            "authored_topology_passed": True, "native_topology_verified": False,
            "physical_completion_claimed": False}


if __name__ == "__main__":
    print(json.dumps(check(), sort_keys=True))
