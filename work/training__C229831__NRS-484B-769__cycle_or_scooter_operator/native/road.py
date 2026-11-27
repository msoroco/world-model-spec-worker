"""Authored single-lane roadway and connected right-turn junction for C229831.

The model establishes an executable OpenDRIVE proposal. Native lane readback,
roadway status, and physical rider motion still require the original run.
"""
from __future__ import annotations

from math import cos, pi, sin
import xml.etree.ElementTree as ET


WIDTH_M = 3.5
RADIUS_M = 7.0
CONNECTOR_LENGTH_M = RADIUS_M * pi / 2


def open_drive():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4",
                  name="C229831-rider-right-turn", version="1", date="2026-11-27",
                  north="60", south="-60", east="60", west="-60",
                  vendor="full-train-worker")
    for road_id, x, y, heading, length, junction in (
        (1, -60.0, 0.0, 0.0, 53.0, -1),
        (2, 0.0, -7.0, -pi / 2, 53.0, -1),
        (13, -7.0, 0.0, 0.0, CONNECTOR_LENGTH_M, 100),
    ):
        road = ET.SubElement(root, "road", id=str(road_id), name=f"rider_{road_id}",
                             length=str(length), junction=str(junction))
        link = ET.SubElement(road, "link")
        if road_id == 1:
            ET.SubElement(link, "successor", elementType="junction", elementId="100")
        elif road_id == 2:
            ET.SubElement(link, "predecessor", elementType="junction", elementId="100")
        else:
            ET.SubElement(link, "predecessor", elementType="road", elementId="1",
                          contactPoint="end")
            ET.SubElement(link, "successor", elementType="road", elementId="2",
                          contactPoint="start")
        geometry = ET.SubElement(ET.SubElement(road, "planView"), "geometry",
                                 s="0", x=str(x), y=str(y), hdg=str(heading),
                                 length=str(length))
        if road_id == 13:
            ET.SubElement(geometry, "arc", curvature=str(-1 / RADIUS_M))
        else:
            ET.SubElement(geometry, "line")
        ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation",
                      s="0", a="0", b="0", c="0", d="0")
        lanes = ET.SubElement(road, "lanes")
        ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
        section = ET.SubElement(lanes, "laneSection", s="0")
        ET.SubElement(section, "left")
        ET.SubElement(ET.SubElement(section, "center"), "lane", id="0", type="none",
                      level="false")
        right = ET.SubElement(section, "right")
        lane = ET.SubElement(right, "lane", id="-1", type="driving", level="false")
        if road_id == 13:
            lane_link = ET.SubElement(lane, "link")
            ET.SubElement(lane_link, "predecessor", id="-1")
            ET.SubElement(lane_link, "successor", id="-1")
        ET.SubElement(lane, "width", sOffset="0", a=str(WIDTH_M), b="0", c="0", d="0")
        ET.SubElement(road, "objects")
        ET.SubElement(road, "signals")
    junction = ET.SubElement(root, "junction", id="100", name="connected_right_turn")
    connection = ET.SubElement(junction, "connection", id="0", incomingRoad="1",
                               connectingRoad="13", contactPoint="start")
    ET.SubElement(connection, "laneLink", **{"from": "-1", "to": "-1"})
    return ET.tostring(root, encoding="unicode")


def lane_center_route():
    """Approximate lane center points across approach, arc and exit."""
    approach = [[-45 + i * 0.25, -WIDTH_M / 2] for i in range(153)]
    radius = RADIUS_M - WIDTH_M / 2
    turn = [[-7 + radius * cos(pi / 2 - i * pi / 200),
             -7 + radius * sin(pi / 2 - i * pi / 200)] for i in range(101)]
    departure = [[-WIDTH_M / 2, -7 - i * 0.25] for i in range(101)]
    return approach + turn[1:] + departure[1:]
