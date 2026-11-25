"""Authored two-intersection taxi route; Native topology needs readback."""
import math
import xml.etree.ElementTree as ET

FIRST_X = 80.0
LATER_X = 130.0


def _road(root, ident, name, x, y, heading, length, *, junction=-1,
          curvature=0.0):
    road = ET.SubElement(root, "road", id=str(ident), name=name,
                         length=str(length), junction=str(junction))
    ET.SubElement(road, "link")
    geometry = ET.SubElement(ET.SubElement(road, "planView"), "geometry",
                             s="0", x=str(x), y=str(y), hdg=str(heading),
                             length=str(length))
    if curvature:
        ET.SubElement(geometry, "arc", curvature=str(curvature))
    else:
        ET.SubElement(geometry, "line")
    ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation",
                  s="0", a="0", b="0", c="0", d="0")
    lanes = ET.SubElement(road, "lanes")
    ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
    section = ET.SubElement(lanes, "laneSection", s="0")
    for side, ids in (("left", (1,)), ("center", (0,)), ("right", (-1,))):
        group = ET.SubElement(section, side)
        for lane_id in ids:
            lane = ET.SubElement(group, "lane", id=str(lane_id),
                                 type="none" if lane_id == 0 else "driving",
                                 level="false")
            if lane_id:
                ET.SubElement(lane, "width", sOffset="0", a="3.5", b="0",
                              c="0", d="0")
            ET.SubElement(lane, "roadMark", sOffset="0", type="broken",
                          color="white", width="0.12")
    ET.SubElement(road, "objects")
    ET.SubElement(road, "signals")
    return road


def _link(road, tag, kind, ident):
    ET.SubElement(road.find("link"), tag, elementType=kind,
                  elementId=str(ident), contactPoint="start")


def open_drive():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4",
                  name="C110875-two-junction-taxi-draft", version="1",
                  date="2026-11-25", north="200", south="-200",
                  east="200", west="0", vendor="full-train-worker")
    approach = _road(root, 1, "stand-to-first-street", 0, 0, 0, 80)
    ET.SubElement(approach.find("objects"), "object", id="501",
                  name="taxicab-stand-draft", type="taxicab_stand",
                  s="5", t="-5", zOffset="0", hdg="0", roll="0",
                  pitch="0", orientation="+", length="8", width="2",
                  height="0.2")
    ET.SubElement(approach.find("signals"), "signal", id="502",
                  name="right-turn-notice-draft", s="10", t="-4.5",
                  zOffset="2", hOffset="0", roll="0", pitch="0",
                  orientation="+", dynamic="no", country="US",
                  type="right_turn_only", subtype="0", value="0",
                  unit="", height="0.7", width="0.7")
    through_first = _road(root, 11, "first-street-through", 80, 0, 0, 1,
                          junction=100)
    turn_first = _road(root, 12, "first-street-right", 80, 0, 0,
                       6 * math.pi / 2, junction=100, curvature=1 / 6)
    between = _road(root, 2, "between-streets", 81, 0, 0, 49)
    right_exit = _road(root, 3, "right-exit-street", 86, 6, math.pi / 2, 100)
    through_later = _road(root, 21, "later-street-through", 130, 0, 0, 1,
                          junction=200)
    beyond = _road(root, 4, "after-later-street", 131, 0, 0, 50)
    for road, junction in ((approach, 100), (between, 200)):
        _link(road, "successor", "junction", junction)
    for road, predecessor in ((through_first, 1), (turn_first, 1),
                              (through_later, 2)):
        _link(road, "predecessor", "road", predecessor)
    for road, predecessor in ((between, 100), (right_exit, 100), (beyond, 200)):
        _link(road, "predecessor", "junction", predecessor)
    for road, successor in ((through_first, 2), (turn_first, 3),
                            (through_later, 4)):
        _link(road, "successor", "road", successor)
    for junction_id, incoming, connecting in ((100, 1, 11), (100, 1, 12),
                                              (200, 2, 21)):
        junction = root.find(f"./junction[@id='{junction_id}']")
        if junction is None:
            junction = ET.SubElement(root, "junction", id=str(junction_id),
                                     name=f"street-intersection-{junction_id}")
        connection = ET.SubElement(junction, "connection",
                                   id=str(len(junction.findall("connection"))),
                                   incomingRoad=str(incoming),
                                   connectingRoad=str(connecting),
                                   contactPoint="start")
        ET.SubElement(connection, "laneLink", **{"from": "-1", "to": "-1"})
    return ET.tostring(root, encoding="unicode")


def check():
    root = ET.fromstring(open_drive())
    roads = {int(r.attrib["id"]): r for r in root.findall("road")}
    if set(roads) != {1, 2, 3, 4, 11, 12, 21}:
        raise ValueError("First and later street roads missing")
    first = root.find("./junction[@id='100']")
    later = root.find("./junction[@id='200']")
    if first is None or later is None or len(first.findall("connection")) != 2 or len(later.findall("connection")) != 1:
        raise ValueError("First/later street choice is not connected")
    if roads[12].find("planView/geometry/arc") is None or FIRST_X >= LATER_X:
        raise ValueError("Right turn or street ordering absent")
    if roads[1].find("objects/object[@id='501']") is None or roads[1].find("signals/signal[@id='502']") is None:
        raise ValueError("Stand or sign geometry missing")
    return {"roads": len(roads), "first_intersection_x_m": FIRST_X,
            "later_intersection_x_m": LATER_X,
            "first_choices": [11, 12], "native_readback_required": True}


if __name__ == "__main__":
    print(check())
