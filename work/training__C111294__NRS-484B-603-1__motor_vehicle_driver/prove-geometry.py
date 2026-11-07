"""Authored OpenDRIVE and saved synthetic path containment check."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
ROAD = ROOT/"draft-fixtures"/"road.xodr"


def check() -> dict:
    raw = ROAD.read_bytes()
    root = ET.fromstring(raw)
    if root.tag != "OpenDRIVE":
        raise AssertionError("OpenDRIVE absent")
    roads = {int(r.attrib["id"]): r for r in root.findall("road")}
    if set(roads) != {1, 2, 3, 4, 13, 14}:
        raise AssertionError("Same-cell intersection road set differs")
    for road_id in (1, 13, 4):
        lane = roads[road_id].find("lanes/laneSection/left/lane[@id='1']")
        if lane is None or lane.attrib["type"] != "driving":
            raise AssertionError("Continuous ego driving lane absent")
        if float(lane.find("width").attrib["a"]) < 3.5:
            raise AssertionError("Lane narrower than authored body path")
    links = {(x.attrib["incomingRoad"], x.attrib["connectingRoad"])
             for x in root.findall("junction/connection")}
    if ("1", "13") not in links or ("4", "13") not in links:
        raise AssertionError("Through junction linkage absent")
    cases = {}
    for name in ("decrease", "hold"):
        rows = [json.loads(x) for x in (ROOT/"draft-fixtures"/f"{name}-synthetic-native.jsonl").read_text().splitlines()]
        if len(rows) != 480:
            raise AssertionError("Saved path incomplete")
        positions = [r["ego_position_m"] for r in rows]
        if not all(.5 <= p[0] <= 3.0 and -235 <= p[1] <= 1095 and abs(p[2]) < .01
                   for p in positions):
            raise AssertionError("Synthetic ego body leaves authored lane envelope")
        if not (positions[0][1] < -7 and positions[-1][1] > 7):
            raise AssertionError("Intersection crossing absent")
        cases[name] = {"start_y_m": round(positions[0][1], 3),
                       "end_y_m": round(positions[-1][1], 3),
                       "authored_lane_contained": True}
    return {"passed": True, "road_sha256": hashlib.sha256(raw).hexdigest(),
            "source": "same-cell C111294 authored OpenDRIVE proposal",
            "synthetic_cases": cases, "carla_import_observed": False,
            "native_lane_readback_observed": False}


if __name__ == "__main__":
    result = check()
    (ROOT/"geometry-proof.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, sort_keys=True))
