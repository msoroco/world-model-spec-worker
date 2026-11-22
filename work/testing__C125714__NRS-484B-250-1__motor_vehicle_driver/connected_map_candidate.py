"""Worker-owned OpenDRIVE topology candidate for a divided-road crossing.

XML connectivity is CPU checked. Native waypoint loading and public-roadway
identity remain unverified; this source must not be called reviewed context.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent
ROUTES = {"ego": [10, 110, 11], "other": [31, 131, 32],
          "opposite_carriageway": [20, 120, 21],
          "opposite_left": [20, 140, 40]}


def _road(root, ident, x, y, heading, length, junction, predecessor=None, successor=None):
    road = ET.SubElement(root, "road", {"name": f"C125714 engineering road {ident}",
                                       "length": str(length), "id": str(ident),
                                       "junction": str(junction)})
    link = ET.SubElement(road, "link")
    for tag, relation in (("predecessor", predecessor), ("successor", successor)):
        if relation:
            element_type, element_id, contact = relation
            attrs = {"elementType": element_type, "elementId": str(element_id)}
            if element_type == "road":
                attrs["contactPoint"] = contact
            ET.SubElement(link, tag, attrs)
    plan = ET.SubElement(road, "planView")
    geometry = ET.SubElement(plan, "geometry", {"s": "0", "x": str(x), "y": str(y),
                                                "hdg": str(heading), "length": str(length)})
    ET.SubElement(geometry, "line")
    elevation = ET.SubElement(road, "elevationProfile")
    ET.SubElement(elevation, "elevation", {"s": "0", "a": "0", "b": "0", "c": "0", "d": "0"})
    ET.SubElement(road, "lateralProfile")
    lanes = ET.SubElement(road, "lanes")
    section = ET.SubElement(lanes, "laneSection", {"s": "0"})
    center = ET.SubElement(section, "center")
    ET.SubElement(center, "lane", {"id": "0", "type": "none", "level": "false"})
    right = ET.SubElement(section, "right")
    lane = ET.SubElement(right, "lane", {"id": "-1", "type": "driving", "level": "false"})
    lane_link = ET.SubElement(lane, "link")
    if predecessor:
        ET.SubElement(lane_link, "predecessor", {"id": "-1"})
    if successor:
        ET.SubElement(lane_link, "successor", {"id": "-1"})
    ET.SubElement(lane, "width", {"sOffset": "0", "a": "3.5", "b": "0", "c": "0", "d": "0"})
    ET.SubElement(lane, "roadMark", {"sOffset": "0", "type": "solid", "weight": "standard",
                                    "color": "white", "width": "0.12", "laneChange": "none"})


def build(path=None):
    path = Path(path) if path else ROOT / "connected-median-candidate.xodr"
    root = ET.Element("OpenDRIVE")
    header = ET.SubElement(root, "header", {"revMajor": "1", "revMinor": "4",
                                            "name": "C125714 engineering divided-road crossing",
                                            "version": "1", "north": "20", "south": "-20",
                                            "east": "30", "west": "-30", "vendor": "worker-candidate"})
    ET.SubElement(header, "geoReference").text = (
        "+proj=tmerc +lat_0=0 +lon_0=0 +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs")
    paths = ((10, -30, -4, 0, 26, -1, None, ("junction", 1, None)),
             (110, -4, -4, 0, 8, 1, ("road", 10, "end"), ("road", 11, "start")),
             (11, 4, -4, 0, 26, -1, ("junction", 1, None), None),
             (31, -1.75, -20, math.pi/2, 14, -1, None, ("junction", 1, None)),
             (131, -1.75, -6, math.pi/2, 12, 1, ("road", 31, "end"), ("road", 32, "start")),
             (32, -1.75, 6, math.pi/2, 14, -1, ("junction", 1, None), None),
             (20, 30, 4, math.pi, 26, -1, None, ("junction", 1, None)),
             (120, 4, 4, math.pi, 8, 1, ("road", 20, "end"), ("road", 21, "start")),
             (21, -4, 4, math.pi, 26, -1, ("junction", 1, None), None),
             (140, 4, 4, math.pi, 2*math.pi, 1,
              ("road", 20, "end"), ("road", 40, "start")),
             (40, 0, 0, 3*math.pi/2, 20, -1, ("junction", 1, None), None))
    for row in paths:
        _road(root, *row)
    turn_geometry = root.find("./road[@id='140']/planView/geometry")
    turn_geometry.remove(turn_geometry.find("line"))
    ET.SubElement(turn_geometry, "arc", {"curvature": "0.25"})
    junction = ET.SubElement(root, "junction", {"name": "candidate divided-road median opening",
                                                "id": "1"})
    for incoming, connecting in ((10, 110), (31, 131), (20, 120), (20, 140)):
        connection = ET.SubElement(junction, "connection", {"id": str(connecting),
                  "incomingRoad": str(incoming), "connectingRoad": str(connecting),
                  "contactPoint": "start"})
        ET.SubElement(connection, "laneLink", {"from": "-1", "to": "-1"})
    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    path.write_bytes(data)
    proof = inspect(path)
    (path.with_suffix(".topology.json")).write_text(json.dumps(proof, indent=2) + "\n")
    return proof


def inspect(path):
    path = Path(path)
    data = path.read_bytes()
    root = ET.fromstring(data)
    roads = {int(road.get("id")): road for road in root.findall("road")}
    if len(roads) != 11:
        raise ValueError("candidate needs eleven distinct approach and junction roads")
    junctions = root.findall("junction")
    if len(junctions) != 1 or junctions[0].get("id") != "1":
        raise ValueError("one declared median junction required")
    connections = {(int(c.get("incomingRoad")), int(c.get("connectingRoad"))): c
                   for c in junctions[0].findall("connection")}
    for label, (approach, through, departure) in ROUTES.items():
        if (approach, through) not in connections:
            raise ValueError(f"{label} has no junction connection")
        connection = connections[approach, through]
        if connection.get("contactPoint") != "start" or not any(
                link.get("from") == "-1" and link.get("to") == "-1"
                for link in connection.findall("laneLink")):
            raise ValueError(f"{label} lane connection differs")
        if roads[through].get("junction") != "1":
            raise ValueError(f"{label} through road is outside junction")
        for source, tag, expected_type, expected_id in (
                (roads[approach], "successor", "junction", 1),
                (roads[through], "predecessor", "road", approach),
                (roads[through], "successor", "road", departure),
                (roads[departure], "predecessor", "junction", 1)):
            link = source.find("./link/" + tag)
            if link is None or link.get("elementType") != expected_type or int(link.get("elementId", -1)) != expected_id:
                raise ValueError(f"{label} road link differs")
        for ident in (approach, through, departure):
            if roads[ident].find("./lanes/laneSection/right/lane[@id='-1']") is None:
                raise ValueError(f"{label} driving lane absent")
    arc = roads[140].find("./planView/geometry/arc")
    if arc is None or float(arc.get("curvature", "nan")) != 0.25:
        raise ValueError("opposite left junction arc differs")
    return {"format": "c125714-candidate-topology", "map_sha256": hashlib.sha256(data).hexdigest(),
            "route_road_ids": ROUTES, "junction_connection_count": len(connections),
            "review_status": "CPU XML connectivity only; Native map loading and legal context unverified"}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
