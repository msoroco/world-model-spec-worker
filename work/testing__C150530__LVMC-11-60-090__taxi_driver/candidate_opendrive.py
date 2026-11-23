"""Generate an OpenDRIVE CPU candidate for a one-way stand and first junction.

This XML is an engineering candidate. Its signal and stand objects do not prove
municipal designation, licensing, visibility, or Native waypoint loading.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from xml.etree import ElementTree as ET

from stand_route import CASES, make, inspect as inspect_route

ROOT = Path(__file__).resolve().parent
ROAD_SPEC = {
    10: (-90, 0, 0, 86, -1),
    110: (-4, 0, 0, 2 * math.pi, 1),
    11: (0, -4, -math.pi / 2, 46, -1),
    120: (-4, 0, 0, 8, 1),
    12: (4, 0, 0, 46, -1),
    20: (0, 50, -math.pi / 2, 46, -1),
    220: (0, 4, -math.pi / 2, 8, 1),
}
ROUTES = ((10, 110, 11), (10, 120, 12), (20, 220, 11))


def _road(root, ident, spec):
    x, y, heading, length, junction = spec
    road = ET.SubElement(root, "road", {"id": str(ident), "name": f"C150530 road {ident}",
                                        "length": str(length), "junction": str(junction)})
    link = ET.SubElement(road, "link")
    predecessor = {110: ("road", 10), 120: ("road", 10), 11: ("junction", 1),
                   12: ("junction", 1), 220: ("road", 20)}.get(ident)
    successor = {10: ("junction", 1), 110: ("road", 11), 120: ("road", 12),
                 20: ("junction", 1), 220: ("road", 11)}.get(ident)
    for tag, relation in (("predecessor", predecessor), ("successor", successor)):
        if relation:
            attrs = {"elementType": relation[0], "elementId": str(relation[1])}
            if relation[0] == "road":
                attrs["contactPoint"] = "end" if tag == "predecessor" else "start"
            ET.SubElement(link, tag, attrs)
    plan = ET.SubElement(road, "planView")
    geometry = ET.SubElement(plan, "geometry", {"s": "0", "x": str(x), "y": str(y),
                                                 "hdg": str(heading), "length": str(length)})
    if ident == 110:
        ET.SubElement(geometry, "arc", {"curvature": "-0.25"})
    else:
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
    return road


def build(case):
    layout = make(case)
    inspect_route(layout)
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", {"revMajor": "1", "revMinor": "4", "name": "C150530 CPU candidate",
                                   "version": "1", "north": "50", "south": "-50", "east": "50",
                                   "west": "-90", "vendor": "worker-candidate"})
    roads = {ident: _road(root, ident, spec) for ident, spec in ROAD_SPEC.items()}
    stand_s = layout["stand"]["center"][0] + 90
    notice_s = layout["posted_notice"]["point"][0] + 90
    objects = ET.SubElement(roads[10], "objects")
    ET.SubElement(objects, "object", {"id": "1", "name": "candidate taxi stand marker",
                                     "type": "parkingSpace", "s": str(stand_s), "t": "-4.5",
                                     "zOffset": "0", "hdg": "0", "length": "5", "width": "2"})
    signals = ET.SubElement(roads[10], "signals")
    ET.SubElement(signals, "signal", {"id": "1", "name": "candidate right turn notice",
                                     "s": str(notice_s), "t": "-3.5", "zOffset": "1.5",
                                     "hOffset": "0", "orientation": "+", "type": "R2-1",
                                     "subtype": "right", "value": "0", "unit": "none",
                                     "height": "0.7", "width": "0.7"})
    junction = ET.SubElement(root, "junction", {"id": "1", "name": "first street intersection"})
    for connection_id, incoming, connecting in ((1, 10, 110), (2, 10, 120), (3, 20, 220)):
        connection = ET.SubElement(junction, "connection", {"id": str(connection_id),
                  "incomingRoad": str(incoming), "connectingRoad": str(connecting),
                  "contactPoint": "start"})
        ET.SubElement(connection, "laneLink", {"from": "-1", "to": "-1"})
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _lane_endpoints(road):
    geometry = road.find("./planView/geometry")
    x, y, heading, length = (float(geometry.get(key)) for key in ("x", "y", "hdg", "length"))
    arc = geometry.find("arc")
    curvature = float(arc.get("curvature")) if arc is not None else 0.0
    end_heading = heading + curvature * length
    if curvature:
        end = (x + (math.sin(end_heading) - math.sin(heading)) / curvature,
               y + (math.cos(heading) - math.cos(end_heading)) / curvature)
    else:
        end = (x + length * math.cos(heading), y + length * math.sin(heading))
    return ((x + 1.75 * math.sin(heading), y - 1.75 * math.cos(heading)),
            (end[0] + 1.75 * math.sin(end_heading), end[1] - 1.75 * math.cos(end_heading)))


def inspect(data: bytes, case: str) -> dict:
    root = ET.fromstring(data)
    roads = {int(road.get("id")): road for road in root.findall("road")}
    if set(roads) != set(ROAD_SPEC):
        raise ValueError("candidate roads differ")
    for ident, expected in ROAD_SPEC.items():
        road = roads[ident]
        x, y, heading, length, junction = expected
        geometry = road.find("./planView/geometry")
        if geometry is None or road.get("junction") != str(junction) or any(
                not math.isclose(float(geometry.get(key, "nan")), value, abs_tol=1e-8)
                for key, value in (("x", x), ("y", y), ("hdg", heading),
                                   ("length", length))) or not math.isclose(float(road.get("length", "nan")), length, abs_tol=1e-8):
            raise ValueError("authored road geometry differs")
        if ident != 110 and (geometry.find("line") is None or geometry.find("arc") is not None):
            raise ValueError("one-way road primitive differs")
        section = road.find("./lanes/laneSection")
        if section is None or section.find("./left/lane") is not None:
            raise ValueError("counterflow or missing one-way lane section")
        right_lanes = section.findall("./right/lane")
        if len(right_lanes) != 1 or right_lanes[0].get("id") != "-1" or right_lanes[0].get("type") != "driving":
            raise ValueError("one-way driving lane differs")
        width = right_lanes[0].find("width")
        if width is None or any(not math.isclose(float(width.get(key, "nan")), expected_value, abs_tol=1e-8)
                                for key, expected_value in (("a", 3.5), ("b", 0),
                                                            ("c", 0), ("d", 0))):
            raise ValueError("one-way driving lane width differs")
    junctions = root.findall("junction")
    if len(junctions) != 1 or junctions[0].get("id") != "1":
        raise ValueError("first junction count differs")
    connections = {(int(c.get("incomingRoad")), int(c.get("connectingRoad")))
                   for c in junctions[0].findall("connection")
                   if any(link.get("from") == "-1" and link.get("to") == "-1"
                          for link in c.findall("laneLink"))}
    if connections != {(10, 110), (10, 120), (20, 220)}:
        raise ValueError("one-way junction connections differ")
    for route in ROUTES:
        for first, second in zip(route, route[1:]):
            if math.dist(_lane_endpoints(roads[first])[1], _lane_endpoints(roads[second])[0]) > 0.01:
                raise ValueError("driving-lane endpoint discontinuity")
    if roads[110].find("./planView/geometry/arc") is None or abs(
            float(roads[110].find("./planView/geometry/arc").get("curvature")) + 0.25) > 1e-9:
        raise ValueError("right turn arc absent")
    expected = make(case)
    stand = roads[10].find("./objects/object")
    notice = roads[10].find("./signals/signal")
    if stand is None or notice is None or abs(float(stand.get("s")) -
            (expected["stand"]["center"][0] + 90)) > 1e-9 or abs(float(notice.get("s")) -
            (expected["posted_notice"]["point"][0] + 90)) > 1e-9:
        raise ValueError("stand or notice position differs")
    if stand.get("type") != "parkingSpace" or stand.get("t") != "-4.5":
        raise ValueError("stand marker geometry differs")
    if notice.get("type") != "R2-1" or notice.get("subtype") != "right" or notice.get("t") != "-3.5":
        raise ValueError("right-turn notice object differs")
    return {"format": "c150530-xodr-cpu-topology-v1", "case": case,
            "sha256": hashlib.sha256(data).hexdigest(),
            "routes": [list(route) for route in ROUTES],
            "limitation": "XML lane continuity only; Native loading and legal/documentary context unverified"}


def write() -> None:
    target = ROOT / "candidates"
    target.mkdir(exist_ok=True)
    for case in CASES:
        data = build(case)
        proof = inspect(data, case)
        (target / f"{case}.xodr").write_bytes(data)
        (target / f"{case}.topology.json").write_text(json.dumps(proof, indent=2) + "\n")


if __name__ == "__main__":
    write()
