"""Exact source, topology, and 600-frame request checker."""
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from build import CASE, CASES, FRAMES, HERE, PLAN, POLICIES, SOURCE, SOURCE_SHA, road, rows, sha


def topology(path):
    root = ET.parse(path).getroot()
    roads = {int(row.attrib["id"]): row for row in root.findall("road")}
    if set(roads) != {250, 251, 252, 253, 254, 255}:
        raise ValueError("Six road regions required")
    if {int(roads[x].attrib["junction"]) for x in (251, 254)} != {1} or \
            any(int(roads[x].attrib["junction"]) != -1 for x in (250, 252, 253, 255)):
        raise ValueError("Junction connector topology")
    for ids, origin, heading in (((250, 251, 252), (-60, 0), 0),
                                 ((253, 254, 255), (0, -60), math.pi/2)):
        for index, road_id in enumerate(ids):
            geometry = roads[road_id].find("./planView/geometry")
            if (geometry is None or geometry.find("line") is None or
                    abs(float(geometry.attrib["length"]) - 40) > 1e-9 or
                    abs(float(geometry.attrib["hdg"]) - heading) > 1e-9 or
                    math.dist((float(geometry.attrib["x"]), float(geometry.attrib["y"])),
                              (origin[0] + index*40*math.cos(heading),
                               origin[1] + index*40*math.sin(heading))) > 1e-8):
                raise ValueError("Crossed highway endpoint mismatch")
            lane = roads[road_id].find("./lanes/laneSection/right/lane")
            if lane is None or lane.attrib["id"] != "-1" or \
                    abs(float(lane.find("width").attrib["a"]) - 3.5) > 1e-9:
                raise ValueError("Driving-lane geometry mismatch")
    junction = root.find("junction")
    if junction is None or junction.attrib.get("id") != "1":
        raise ValueError("Junction missing")
    connections = {(int(c.attrib["incomingRoad"]), int(c.attrib["connectingRoad"]))
                   for c in junction.findall("connection")}
    if connections != {(250, 251), (253, 254)}:
        raise ValueError("Distinct-highway connections missing")
    if any(road.find("signals/signal") is not None for road in roads.values()):
        raise ValueError("Authored official device would change applicability")


def check(bundle):
    bundle = Path(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    suffix = cfg["case_id"].split("__")[-1]
    candidate = cfg["candidate_id"]
    if suffix not in CASES or candidate not in POLICIES:
        raise ValueError("Unknown case or candidate")
    if (bundle / "assignment-source.json").read_bytes() != SOURCE.read_bytes() or \
            (bundle / "case-plan.json").read_bytes() != PLAN.read_bytes() or \
            sha(SOURCE) != SOURCE_SHA:
        raise ValueError("Copied frozen source mismatch")
    if (bundle / "crossroads.xodr").read_text() != road() or \
            cfg["road_sha256"] != sha(bundle / "crossroads.xodr"):
        raise ValueError("Authored road mismatch")
    topology(bundle / "crossroads.xodr")
    source = json.loads(SOURCE.read_text())
    speed, camera, stop = POLICIES[candidate]
    if (cfg["assignment_id"] != CASE.name or cfg["assignment_sha256"] != SOURCE_SHA or
            cfg["case_plan_sha256"] != sha(PLAN) or
            cfg["source_text"] != source["law_record"]["text"] or
            cfg["rate_hz"] != 20 or cfg["frames"] != FRAMES or
            cfg["ego_highway_road_ids"] != [250, 251, 252] or
            cfg["right_other_highway_road_ids"] != [253, 254, 255] or
            cfg["requested_speed_mps"] != speed or cfg["camera_policy"] != camera or
            cfg["stop_before_entry"] != stop or cfg["requested_yield_action"] != (suffix == "controlled_1") or
            cfg["status"] != "unselected_native_request" or cfg["original_native_observed"] is not False or
            cfg["legal_verdict"] is not None):
        raise ValueError("Source-bound configuration mismatch")
    track = bundle / "requested-tracks.jsonl"
    if cfg["tracks_sha256"] != sha(track):
        raise ValueError("Track digest mismatch")
    actual = [json.loads(line) for line in track.read_text().splitlines()]
    if len(actual) != FRAMES or actual != rows(suffix, candidate):
        raise ValueError("Requested entry trajectories changed")
    return {"case_id": cfg["case_id"], "candidate": candidate,
            "frames": len(actual), "delivery_ready": False,
            "original_native_observed": False}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.bundle)))
