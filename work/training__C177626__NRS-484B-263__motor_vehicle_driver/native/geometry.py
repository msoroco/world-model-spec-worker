"""Connected highway and entry-ramp OpenDRIVE proposal for C177626.

The map is an authored physical hypothesis. Its controlled-access legal
designation is unresolved until an independent authority source is attached.
"""

from __future__ import annotations

from math import atan2, cos, hypot, sin
import xml.etree.ElementTree as ET


LANE_WIDTH_M = 3.5
MERGE_X_M = 0.0
MERGE_Y_M = 0.0
RAMP_START = (-140.0, -40.0)
RAMP_JOIN = (-70.0, -20.0)
RAMP_HEADING = atan2(20.0, 70.0)


def _road(root: ET.Element, road_id: int, name: str, start: tuple[float, float],
          heading: float, length: float, junction_id: int, predecessor: tuple[str, int] | None,
          successor: tuple[str, int] | None) -> None:
    road = ET.SubElement(root, "road", id=str(road_id), name=name,
                         length=str(length), junction=str(junction_id))
    link = ET.SubElement(road, "link")
    for tag, target in (("predecessor", predecessor), ("successor", successor)):
        if target is not None:
            kind, target_id = target
            attributes = {"elementType": kind, "elementId": str(target_id)}
            if kind == "road":
                attributes["contactPoint"] = "end" if tag == "predecessor" else "start"
            ET.SubElement(link, tag, **attributes)
    geometry = ET.SubElement(ET.SubElement(road, "planView"), "geometry",
                             s="0", x=str(start[0]), y=str(start[1]),
                             hdg=str(heading), length=str(length))
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
    lane_link = ET.SubElement(lane, "link")
    if predecessor is not None:
        ET.SubElement(lane_link, "predecessor", id="-1")
    if successor is not None:
        ET.SubElement(lane_link, "successor", id="-1")
    ET.SubElement(lane, "width", sOffset="0", a=str(LANE_WIDTH_M),
                  b="0", c="0", d="0")
    ET.SubElement(road, "objects")
    ET.SubElement(road, "signals")


def open_drive() -> str:
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4",
                  name="C177626-entry-ramp-proposal", version="1",
                  date="2026-11-27", north="80", south="-80", east="180",
                  west="-180", vendor="full-train-worker")
    _road(root, 1, "highway_approach", (-150.0, 0.0), 0.0, 150.0, -1,
          None, ("junction", 100))
    _road(root, 2, "highway_merge", (0.0, 0.0), 0.0, 20.0, 100,
          ("road", 1), ("road", 4))
    _road(root, 4, "highway_departure", (20.0, 0.0), 0.0, 160.0, -1,
          ("junction", 100), None)
    _road(root, 3, "entry_access", RAMP_START, RAMP_HEADING,
          hypot(70.0, 20.0), -1, None, ("junction", 100))
    _road(root, 13, "entry_connector", RAMP_JOIN, RAMP_HEADING,
          hypot(70.0, 20.0), 100, ("road", 3), ("road", 2))
    junction = ET.SubElement(root, "junction", id="100", name="entry_merge")
    for index, incoming, connecting in ((0, 1, 2), (1, 3, 13)):
        connection = ET.SubElement(junction, "connection", id=str(index),
                                   incomingRoad=str(incoming),
                                   connectingRoad=str(connecting),
                                   contactPoint="start")
        ET.SubElement(connection, "laneLink", **{"from": "-1", "to": "-1"})
    return ET.tostring(root, encoding="unicode")


def _lane_center(start: tuple[float, float], heading: float, distance: float) -> tuple[float, float]:
    half = LANE_WIDTH_M / 2
    return (start[0] + distance * cos(heading) + half * sin(heading),
            start[1] + distance * sin(heading) - half * cos(heading))


def route_points(kind: str, step_m: float = 0.5) -> list[list[float]]:
    """Return lane-center waypoints for either actor through the merge."""
    if kind == "ego_entry":
        pieces = ((RAMP_START, RAMP_HEADING, hypot(70.0, 20.0)),
                  (RAMP_JOIN, RAMP_HEADING, hypot(70.0, 20.0)),
                  ((0.0, 0.0), 0.0, 20.0), ((20.0, 0.0), 0.0, 80.0))
    elif kind == "highway_approach":
        pieces = (((-150.0, 0.0), 0.0, 150.0),
                  ((0.0, 0.0), 0.0, 20.0), ((20.0, 0.0), 0.0, 80.0))
    else:
        raise ValueError("unknown route kind")
    points: list[list[float]] = []
    for start, heading, length in pieces:
        count = round(length / step_m)
        for i in range(count + 1):
            x, y = _lane_center(start, heading, min(i * step_m, length))
            if not points or hypot(x - points[-1][0], y - points[-1][1]) > step_m / 4:
                points.append([x, y])
    return points


def topology_summary() -> dict:
    ego = route_points("ego_entry")
    highway = route_points("highway_approach")
    merge_gap = hypot(ego[-161][0] - highway[-161][0],
                      ego[-161][1] - highway[-161][1])
    return {
        "route_kind": "entry",
        "access_road_ids": [3, 13],
        "highway_road_ids": [1, 2, 4],
        "junction_id": 100,
        "ego_waypoints": len(ego),
        "highway_waypoints": len(highway),
        "controlled_access_designation_verified": False,
        "merge_centerline_gap_m": merge_gap,
    }


def validate_topology(source: str) -> dict:
    """Reject missing links, mismatched physical joins and claimed legal status."""
    root = ET.fromstring(source)
    roads = {int(road.get("id")): road for road in root.findall("road")}
    if set(roads) != {1, 2, 3, 4, 13}:
        raise ValueError("five distinct ramp and highway roads required")
    junction = root.find("junction")
    if junction is None or junction.get("id") != "100":
        raise ValueError("entry merge junction required")
    links = {(int(connection.get("incomingRoad")), int(connection.get("connectingRoad")))
             for connection in junction.findall("connection")}
    if links != {(1, 2), (3, 13)}:
        raise ValueError("both incoming merge links required")
    for incoming, connecting in links:
        connection = next(c for c in junction.findall("connection")
                          if int(c.get("incomingRoad")) == incoming)
        lane_links = {(x.get("from"), x.get("to"))
                      for x in connection.findall("laneLink")}
        if lane_links != {("-1", "-1")}:
            raise ValueError("driving lane link required")
        if roads[incoming].find("link/successor").get("elementId") != "100":
            raise ValueError("incoming road must enter merge junction")
        if roads[connecting].get("junction") != "100":
            raise ValueError("connecting road must belong to merge junction")
    if roads[13].find("link/successor").get("elementId") != "2":
        raise ValueError("ramp connector must join highway connector")
    def endpoint(road_id: int) -> tuple[float, float]:
        road = roads[road_id]
        geometry = road.find("planView/geometry")
        heading = float(geometry.get("hdg"))
        length = float(road.get("length"))
        return (float(geometry.get("x")) + length * cos(heading),
                float(geometry.get("y")) + length * sin(heading))
    def startpoint(road_id: int) -> tuple[float, float]:
        geometry = roads[road_id].find("planView/geometry")
        return float(geometry.get("x")), float(geometry.get("y"))
    for a, b in ((1, 2), (2, 4), (3, 13), (13, 2)):
        ax, ay = endpoint(a)
        bx, by = startpoint(b)
        if hypot(ax - bx, ay - by) > 1e-6:
            raise ValueError("road reference-line physical join failed")
    if any(road.find("lanes/laneSection/right/lane[@id='-1']") is None
           for road in roads.values()):
        raise ValueError("continuous right-hand driving lane required")
    return topology_summary()
