"""Straight narrow highway with a surveyed excavation beside the parking zone.

Coordinates are authored engineering targets. Native map and actor readback,
actual clearance, and legal obstruction still require original capture.
"""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET

ROAD = (-100.0, -3.5, 100.0, 3.5)
EXCAVATION = (0.0, 1.0, 5.0, 3.4)
PARK_CENTERS_Y = {"condition_a": -1.1, "condition_b": -2.5}
FRAME_COUNT = 600


def open_drive() -> str:
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4",
                  name="C135702-narrow-highway-excavation", version="1",
                  date="2026-11-27", north="100", south="-100",
                  east="100", west="-100", vendor="full-train-worker")
    road = ET.SubElement(root, "road", id="1", name="narrow-highway",
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
    for side, lane_id in (("left", 1), ("center", 0), ("right", -1)):
        group = ET.SubElement(section, side)
        lane = ET.SubElement(group, "lane", id=str(lane_id),
                             type="none" if lane_id == 0 else "driving", level="false")
        if lane_id:
            ET.SubElement(lane, "width", sOffset="0", a="3.5", b="0", c="0", d="0")
        ET.SubElement(lane, "roadMark", sOffset="0",
                      type="solid" if lane_id == 0 else "broken",
                      color="yellow" if lane_id == 0 else "white", width="0.12")
    ET.SubElement(road, "objects")
    ET.SubElement(road, "signals")
    return ET.tostring(root, encoding="unicode")


def largest_open_width(road: tuple[float, ...], occupied: list[tuple[float, ...]]) -> float:
    cursor = road[1]
    widths = []
    for low, high in sorted((max(road[1], body[1]), min(road[3], body[3]))
                            for body in occupied):
        if high <= low:
            continue
        widths.append(max(0.0, low - cursor))
        cursor = max(cursor, high)
    widths.append(max(0.0, road[3] - cursor))
    return max(widths)


def check() -> dict:
    root = ET.fromstring(open_drive())
    if len(root.findall("road")) != 1 or len(root.findall(".//lane[@type='driving']")) != 2:
        raise ValueError("Narrow two-lane highway geometry absent")
    if not (ROAD[0] < EXCAVATION[0] < EXCAVATION[2] < ROAD[2] and
            ROAD[1] < EXCAVATION[1] < EXCAVATION[3] < ROAD[3]):
        raise ValueError("Excavation misses highway")
    # A 1.8 m vehicle footprint provides two distinct measured openings while
    # the road and excavation stay fixed. This is an authored target only.
    openings = {}
    for name, center in PARK_CENTERS_Y.items():
        body = (0.1, center - 0.9, 4.9, center + 0.9)
        openings[name] = largest_open_width(ROAD, [EXCAVATION, body])
    if not openings["condition_a"] < 1.8 < openings["condition_b"]:
        raise ValueError("Authored comparison does not straddle passing width")
    return {"passed": True, "cell_id": "C135702", "law_id": "NRS-484B-450-1k",
            "road_xy_m": ROAD, "excavation_xy_m": EXCAVATION,
            "authored_openings_m": openings, "native_readback_observed": False,
            "physical_cause_confirmed": False, "legal_verdict_claimed": False}


if __name__ == "__main__":
    import json
    print(json.dumps(check()))
