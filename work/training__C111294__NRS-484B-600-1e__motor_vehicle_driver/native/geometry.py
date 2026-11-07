"""Authored C111294 long through road and separate opposing vehicle route.

This is a construction proposal. CARLA map import, actual vehicle motion,
territorial applicability and original pixels require later observations.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

LANE_WIDTH_M = 3.5
FPS = 20
FRAMES = 480
EGO_START_Y_M = -70.0
OTHER_START_Y_M = 100.0
OTHER_SPEED_MPS = 10.0
SPEED_MPH = {"below_80_mph": 75.0, "inside_80_mph": 79.5,
             "above_80_mph": 85.0}
MPH_TO_MPS = 0.44704


def open_drive() -> str:
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", revMajor="1", revMinor="4",
                  name="C111294-80mph-long-intersection-draft", version="1",
                  date="2026-11-06", north="1200", south="-250",
                  east="100", west="-100", vendor="full-train-worker")
    # The long north/south road is continuous through junction 100. CARLA
    # reflects authored OpenDRIVE y on import; read back Native poses later.
    roads = ((1, 0, -240, math.pi / 2, 233, -1),
             (13, 0, -7, math.pi / 2, 14, 100),
             (4, 0, 7, math.pi / 2, 1093, -1),
             (3, -100, 0, 0, 93, -1),
             (14, -7, 0, 0, 14, 100),
             (2, 7, 0, 0, 93, -1))
    for ident, x, y, heading, length, junction in roads:
        road = ET.SubElement(root, "road", id=str(ident),
                             name=f"C111294_speed_{ident}",
                             length=str(length), junction=str(junction))
        link = ET.SubElement(road, "link")
        if ident in (1, 3):
            ET.SubElement(link, "successor", elementType="junction",
                          elementId="100")
        elif ident in (4, 2):
            ET.SubElement(link, "predecessor", elementType="junction",
                          elementId="100")
        else:
            before, after = (1, 4) if ident == 13 else (3, 2)
            ET.SubElement(link, "predecessor", elementType="road",
                          elementId=str(before), contactPoint="end")
            ET.SubElement(link, "successor", elementType="road",
                          elementId=str(after), contactPoint="start")
        geom = ET.SubElement(ET.SubElement(road, "planView"), "geometry",
                             s="0", x=str(x), y=str(y), hdg=str(heading),
                             length=str(length))
        ET.SubElement(geom, "line")
        ET.SubElement(ET.SubElement(road, "elevationProfile"), "elevation",
                      s="0", a="0", b="0", c="0", d="0")
        lanes = ET.SubElement(road, "lanes")
        ET.SubElement(lanes, "laneOffset", s="0", a="0", b="0", c="0", d="0")
        sec = ET.SubElement(lanes, "laneSection", s="0")
        for side, lane_ids in (("left", (1,)), ("center", (0,)),
                               ("right", (-1,))):
            group = ET.SubElement(sec, side)
            for lane_id in lane_ids:
                lane = ET.SubElement(group, "lane", id=str(lane_id),
                                     type="none" if lane_id == 0 else "driving",
                                     level="false")
                if lane_id:
                    ET.SubElement(lane, "width", sOffset="0",
                                  a=str(LANE_WIDTH_M), b="0", c="0", d="0")
                    if ident in (13, 14):
                        lane_link = ET.SubElement(lane, "link")
                        ET.SubElement(lane_link, "predecessor", id=str(lane_id))
                        ET.SubElement(lane_link, "successor", id=str(lane_id))
                ET.SubElement(lane, "roadMark", sOffset="0",
                              type="solid" if lane_id == 0 else "broken",
                              color="yellow" if lane_id == 0 else "white",
                              width="0.12")
        ET.SubElement(road, "objects")
        ET.SubElement(road, "signals")
    junction = ET.SubElement(root, "junction", id="100",
                             name="uncontrolled-other-vehicle-intersection")
    for connection_id, incoming, connector, contact, lane_id in (
            (0, 1, 13, "start", -1),
            (1, 3, 14, "start", -1),
            (2, 4, 13, "end", 1)):
        connection = ET.SubElement(junction, "connection", id=str(connection_id),
                                   incomingRoad=str(incoming),
                                   connectingRoad=str(connector),
                                   contactPoint=contact)
        ET.SubElement(connection, "laneLink", **{"from": str(lane_id),
                                                 "to": str(lane_id)})
    return ET.tostring(root, encoding="unicode")


def proposed_samples(case: str) -> list[dict]:
    """Synthetic constant-speed geometry probe, not a CARLA observation."""
    if case not in SPEED_MPH:
        raise ValueError("Unknown case")
    speed = SPEED_MPH[case] * MPH_TO_MPS
    return [{"frame": i, "t_s": i / FPS,
             "ego_x_m": LANE_WIDTH_M / 2,
             "ego_y_m": EGO_START_Y_M + speed * i / FPS,
             "other_x_m": -LANE_WIDTH_M / 2,
             "other_y_m": OTHER_START_Y_M - OTHER_SPEED_MPS * i / FPS}
            for i in range(FRAMES)]


def check() -> dict:
    root = ET.fromstring(open_drive())
    roads = {int(r.attrib["id"]): r for r in root.findall("road")}
    if set(roads) != {1, 2, 3, 4, 13, 14}:
        raise ValueError("Road set incomplete")
    if {(x.attrib["incomingRoad"], x.attrib["connectingRoad"],
         x.attrib["contactPoint"], x.find("laneLink").attrib["from"])
            for x in root.findall("junction/connection")} != {
                ("1", "13", "start", "-1"),
                ("3", "14", "start", "-1"),
                ("4", "13", "end", "1")}:
        raise ValueError("Junction links incomplete")
    if root.findall(".//signal") or root.findall(".//object"):
        raise ValueError("No traffic control or object is authored")
    result = {}
    for case, mph in SPEED_MPH.items():
        rows = proposed_samples(case)
        ego_y = [r["ego_y_m"] for r in rows]
        other_y = [r["other_y_m"] for r in rows]
        if not (ego_y[0] - 2.5 >= -240 and ego_y[-1] + 2.5 <= 1100):
            raise ValueError("Ego body exceeds authored long road")
        if not (other_y[-1] - 2.5 >= -240 and other_y[0] + 2.5 <= 1100):
            raise ValueError("Other vehicle exceeds authored long road")
        if not (ego_y[0] < -7 < 7 < ego_y[-1]):
            raise ValueError("Ego misses intersection")
        if min(abs(r["ego_x_m"] - r["other_x_m"]) for r in rows) < 3.5:
            raise ValueError("Separate opposing lanes lost")
        if not all(math.dist((r["ego_x_m"], r["ego_y_m"]),
                             (s["ego_x_m"], s["ego_y_m"])) < 2.0
                   for r, s in zip(rows, rows[1:])):
            raise ValueError("Synthetic sample gap too large")
        result[case] = {"commanded_mph": mph,
                        "prospective_terminal_y_m": round(ego_y[-1], 3),
                        "intersection_crossed": True,
                        "other_actor_motion_m": round(other_y[0] - other_y[-1], 3)}
    return {"passed": True, "source_scope": "authored road and synthetic kinematics",
            "cell_id": "C111294", "law_id": "NRS-484B-600-1e",
            "sample_rate_hz": FPS, "frames": FRAMES,
            "native_map_import_observed": False,
            "physical_speed_observed": False,
            "other_actor_observed": False,
            "cases": result}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = check()
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "road.xodr").write_text(open_drive())
        (args.output / "geometry-check.json").write_text(json.dumps(result, indent=2) + "\n")
        for case in SPEED_MPH:
            (args.output / f"proposed-{case}.jsonl").write_text(
                "".join(json.dumps(row, sort_keys=True) + "\n"
                        for row in proposed_samples(case)))
    print(json.dumps(result, sort_keys=True))
