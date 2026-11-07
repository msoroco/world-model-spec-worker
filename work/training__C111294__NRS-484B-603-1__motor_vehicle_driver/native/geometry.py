"""Same-cell authored intersection map retained for the speed-profile cases."""
from __future__ import annotations

import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET

FPS = 20
FRAMES = 480
MPH_TO_MPS = .44704
ROOT = Path(__file__).resolve().parent
ROAD = ROOT / "authored-road.xodr"


def open_drive() -> str:
    return ROAD.read_text()


def check() -> dict:
    raw = ROAD.read_bytes()
    expected = "bc708461e9ccb79fef6df587b5e13189197a2cc0e31c535a5edbe374fe45327e"
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("Authored same-cell OpenDRIVE changed")
    tree = ET.fromstring(raw)
    roads = {int(road.attrib["id"]): road for road in tree.findall("road")}
    if set(roads) != {1, 2, 3, 4, 13, 14}:
        raise ValueError("Authored intersection road set changed")
    for road_id in (1, 13, 4, 3, 14, 2):
        lane = roads[road_id].find("lanes/laneSection/right/lane[@id='-1']")
        if lane is None or lane.attrib["type"] != "driving":
            raise ValueError("Ego or cross-traffic lane absent")
    links = {(node.attrib["incomingRoad"], node.attrib["connectingRoad"])
             for node in tree.findall("junction/connection")}
    if not {("1", "13"), ("3", "14")}.issubset(links):
        raise ValueError("Through-junction route changed")
    return {"passed": True, "cell_id": "C111294", "law_id": "NRS-484B-603-1",
            "road_sha256": expected, "road_length_m": 1093,
            "native_map_import_observed": False}
