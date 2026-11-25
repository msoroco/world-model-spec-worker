"""Authored C238396 roundabout source inventory; Native readback remains required."""
from pathlib import Path
import xml.etree.ElementTree as ET

ROAD = Path(__file__).with_name("roundabout-road.xodr")


def open_drive():
    return ROAD.read_text()


def check():
    root = ET.fromstring(open_drive())
    roads = {int(road.attrib["id"]): road for road in root.findall("road")}
    if set(roads) != {20, 21, 22, 23}:
        raise ValueError("Authored roundabout road inventory differs")
    if {int(j.attrib["id"]) for j in root.findall("junction")} != {100, 101}:
        raise ValueError("Authored roundabout junction inventory differs")
    if any(float(roads[i].attrib["length"]) < 20 for i in (21, 23)):
        raise ValueError("Circulatory road length missing")
    return {"authored_topology_passed": True, "native_topology_verified": False,
            "roundabout_center_xy_m": [22, 0], "ring_road_ids": [21, 23],
            "physical_completion_claimed": False}
