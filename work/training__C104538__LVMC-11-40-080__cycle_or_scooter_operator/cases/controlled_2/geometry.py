"""Authored hill-crest, governed no-U-turn sign and bicycle route proposal."""
import math
import xml.etree.ElementTree as ET


def open_drive():
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4", name="C104538-rider-signed-turn",
                  version="1", date="2026-11-07", north="100", south="-100",
                  east="100", west="-100", vendor="full-train-worker")
    road = ET.SubElement(root, "road", id="1", name="hill_crest_no_u_turn",
                         length="160", junction="-1")
    ET.SubElement(road, "link")
    geom = ET.SubElement(ET.SubElement(road, "planView"), "geometry",
                         s="0", x="-80", y="0", hdg="0", length="160")
    ET.SubElement(geom, "line")
    profile = ET.SubElement(road, "elevationProfile")
    ET.SubElement(profile, "elevation", s="0", a="0", b="0.04", c="-0.00025", d="0")
    ET.SubElement(profile, "elevation", s="80", a="1.6", b="0", c="-0.00025", d="0")
    lanes = ET.SubElement(road, "lanes")
    ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
    section = ET.SubElement(lanes, "laneSection", s="0")
    for side, lane_id in (("left", "1"), ("right", "-1")):
        lane = ET.SubElement(ET.SubElement(section, side), "lane", id=lane_id,
                             type="driving", level="false")
        ET.SubElement(lane, "width", sOffset="0", a="8", b="0", c="0", d="0")
        ET.SubElement(lane, "roadMark", sOffset="0", type="solid", color="white", width="0.12")
    center = ET.SubElement(section, "center")
    lane = ET.SubElement(center, "lane", id="0", type="none", level="false")
    ET.SubElement(lane, "roadMark", sOffset="0", type="solid", color="yellow", width="0.12")
    signals = ET.SubElement(road, "signals")
    ET.SubElement(signals, "signal", id="1140080", name="no_u_turn_rider_proposal",
                  s="72", t="-6", zOffset="2.3", hOffset="0", pitch="0", roll="0",
                  orientation="+", dynamic="no", country="US", type="206", subtype="0",
                  value="0", unit="none")
    ET.SubElement(road, "objects")
    return ET.tostring(root, encoding="unicode")


def native_route(kind, start_x=-35.0):
    if kind not in ("mounted_obey", "mounted_turn", "dismounted_turn"):
        raise ValueError("Unknown rider route")
    if start_x not in (-35.0, -50.0):
        raise ValueError("Unapproved approach length")
    approach = [[start_x + i*.1, 4.0] for i in range(round(-start_x/.1)+1)]
    if kind == "mounted_obey":
        return approach + [[i*.1, 4.0] for i in range(1, 301)]
    turn = []
    for i in range(1, 201):
        angle = math.pi/2 - math.pi*i/200
        turn.append([4*math.cos(angle), 4*math.sin(angle)])
    return approach + turn + [[-i*.1, -4.0] for i in range(1, 251)]


def check():
    road = ET.fromstring(open_drive()).find("road")
    assert road is not None and road.attrib["id"] == "1"
    assert float(road.findall("elevationProfile/elevation")[1].attrib["a"]) > 0
    assert road.find("signals/signal").attrib["name"] == "no_u_turn_rider_proposal"
    assert {int(x.attrib["id"]) for x in road.findall("lanes/laneSection/*/lane")} == {-1, 0, 1}
    cases = {}
    for kind in ("mounted_obey", "mounted_turn", "dismounted_turn"):
        for start in (-35.0, -50.0):
            route = native_route(kind, start)
            gaps = [math.dist(a, b) for a, b in zip(route, route[1:])]
            assert max(gaps) < .11
            assert all(-80 <= x <= 80 and -8 <= y <= 8 for x, y in route)
            assert route[0] == [start, 4.0]
            assert route[-1][1] == (4.0 if kind == "mounted_obey" else -4.0)
            cases[f"{kind}:{start}"] = {"points": len(route), "max_step_m": max(gaps)}
    return {"passed": True, "scope": "authored OpenDRIVE/route CPU proposal",
            "native_sign_readback": False, "native_rider_readback": False, "cases": cases}


if __name__ == "__main__":
    import json
    print(json.dumps(check(), sort_keys=True))
