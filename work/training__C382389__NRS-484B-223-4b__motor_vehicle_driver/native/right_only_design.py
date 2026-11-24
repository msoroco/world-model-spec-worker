"""Repair prototype for the C382389 right-only approach lane topology.

The existing draft OpenDRIVE gives lane -2 both a right-turn and straight
connector. This source transform removes that straight lane link while keeping
the road surface, adjacent straight link, right-turn link and arrow. A driver
can still physically attempt the planned straight path; Native realization
and regulatory lane designation require independent review.
"""
import hashlib
import xml.etree.ElementTree as ET

from geometry import open_drive


def build():
    root = ET.fromstring(open_drive())
    straight = next(c for c in root.findall("junction/connection")
                    if c.attrib.get("connectingRoad") == "14")
    bad = [link for link in straight.findall("laneLink")
           if link.attrib.get("from") == "-2"]
    if len(bad) != 1:
        raise ValueError("expected exactly one prohibited right-only straight lane link")
    straight.remove(bad[0])
    xml = ET.tostring(root, encoding="unicode")
    validate(xml)
    return xml


def validate(xml):
    root = ET.fromstring(xml)
    roads = {r.attrib["id"]: r for r in root.findall("road")}
    if set(roads) != {"1", "2", "3", "4", "13", "14"}:
        raise ValueError("authored road inventory changed")
    arrow = roads["1"].find("objects/object")
    if arrow is None or arrow.attrib.get("name") != "right_turn_arrow" or arrow.attrib.get("t") != "-5.25":
        raise ValueError("right-only lane arrow source missing")
    connections = {c.attrib["connectingRoad"]: c for c in root.findall("junction/connection")}
    if set(connections) != {"13", "14"}:
        raise ValueError("junction connector inventory changed")
    turning = {(x.attrib["from"], x.attrib["to"]) for x in connections["13"].findall("laneLink")}
    straight = {(x.attrib["from"], x.attrib["to"]) for x in connections["14"].findall("laneLink")}
    if turning != {("-2", "-2")} or straight != {("-1", "-1")}:
        raise ValueError("right-only/adjacent connector topology mismatch")
    return {"format": "c382389-right-only-topology-diagnostic-v1",
            "authored_xodr_sha256": hashlib.sha256(xml.encode()).hexdigest(),
            "right_only_turn_link": True,
            "right_only_straight_link": False,
            "adjacent_straight_link": True,
            "road_surface_changed": False,
            "native_design_verified": False,
            "legal_verdict": None}
