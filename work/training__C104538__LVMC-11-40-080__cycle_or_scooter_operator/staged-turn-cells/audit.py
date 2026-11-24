"""Independent hash-bound saved-source audit for staged signed-turn cells."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("c104538_staged_audit_geometry", ROOT/"geometry.py")
_geometry = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_geometry)
CELLS, FRAMES, RATE_HZ, TURN_FIRST_FRAME, TURN_LAST_FRAME = (
    _geometry.CELLS, _geometry.FRAMES, _geometry.RATE_HZ,
    _geometry.TURN_FIRST_FRAME, _geometry.TURN_LAST_FRAME)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def audit(direction, folder=None):
    if direction not in CELLS:
        raise ValueError("Unknown catalog turn direction")
    cell, maneuver, sign, _ = CELLS[direction]
    folder = Path(folder) if folder is not None else ROOT/direction
    index = json.loads((folder/"staging-index.json").read_text())
    if index["cell_id"] != cell or len(index["cases"]) != 2:
        raise ValueError("Staged case inventory differs")
    catalog_path = ROOT.parents[2]/"inputs/coverage/candidate-cells.json"
    catalog = json.loads(catalog_path.read_text())
    matches = [item for item in catalog["cells"] if item["cell_id"] == cell]
    if (index.get("frozen_catalog_sha256") != sha(catalog_path) or len(matches) != 1 or
            index.get("frozen_catalog_cell") != matches[0]):
        raise ValueError("Staged catalog cell source differs")
    road_path = folder/"road.xodr"
    root = ET.fromstring(road_path.read_text())
    signal = root.find("road[@id='1']/signals/signal")
    if signal is None or signal.attrib["name"] != sign or signal.attrib["orientation"] != "+":
        raise ValueError("Source sign is not the matching governed prohibition")
    hill = root.findall("road[@id='1']/elevationProfile/elevation")
    if len(hill) != 2 or float(hill[0].attrib["c"]) <= 0 or float(hill[1].attrib["c"]) >= 0:
        raise ValueError("Hill-crest source is absent")
    rows = {}
    source_hashes = {}
    for case in index["cases"]:
        behavior = case["behavior"]
        if behavior not in ("obey","turn") or behavior in rows:
            raise ValueError("Expected one obey and one turn source")
        path = folder/f"{behavior}-source.jsonl"
        if sha(path) != case["sampled_source_sha256"] or sha(road_path) != case["road_sha256"]:
            raise ValueError("Staged retained source hash changed")
        source = load_rows(path)
        if len(source) != FRAMES or [r["frame"] for r in source] != list(range(FRAMES)):
            raise ValueError("Saved route frame inventory differs")
        if any(r["time_s"] != r["frame"]/RATE_HZ or
               r["cell_id"] != cell or r["sign_code"] != sign or
               r["machine_class"] != "bicycle" or r["mounted"] is not True or
               r["governed_approach_road_id"] != 1 or
               r["governed_approach_lane_id"] != -1 for r in source):
            raise ValueError("Saved route time, class or sign applicability differs")
        rows[behavior] = source
        source_hashes[behavior] = sha(path)
    if set(rows) != {"obey","turn"}:
        raise ValueError("Controlled behavior pair incomplete")
    obey, turn = rows["obey"], rows["turn"]
    if any(a["body_center_xy_m"] != b["body_center_xy_m"]
           for a,b in zip(obey[:TURN_FIRST_FRAME+1],turn[:TURN_FIRST_FRAME+1])):
        raise ValueError("Controlled approach differs before decision")
    if any(r["maneuver"] != "through" for r in obey) or any(r["maneuver"] != maneuver for r in turn):
        raise ValueError("Saved maneuver identity differs")
    start = turn[TURN_FIRST_FRAME]["body_center_xy_m"]
    end = turn[TURN_LAST_FRAME]["body_center_xy_m"]
    if start != [0,-8] or end != ([8,0] if direction=="right" else [-8,0]):
        raise ValueError("Actual quarter-turn geometry differs")
    if obey[TURN_LAST_FRAME]["body_center_xy_m"] != [0,0]:
        raise ValueError("Obey route does not continue north")
    turn_delta = (end[0]-start[0],end[1]-start[1])
    if (direction == "right" and turn_delta[0] <= 0) or (
            direction == "left" and turn_delta[0] >= 0):
        raise ValueError("Turn side differs")
    for source in rows.values():
        points = [r["body_center_xy_m"] for r in source]
        if max(math.dist(a,b) for a,b in zip(points,points[1:])) > .2:
            raise ValueError("Saved route has a discontinuity")
    return {"format":"c104538-staged-turn-saved-source-audit-v1",
            "cell_id":cell,"law_id":"LVMC-11-40-080",
            "sign_code":sign,"maneuver":maneuver,
            "controlled_approach_frames":TURN_FIRST_FRAME+1,
            "turn_exit_xy_m":end,"obey_exit_xy_m":obey[TURN_LAST_FRAME]["body_center_xy_m"],
            "source_sha256":{"road":sha(road_path),**source_hashes},
            "passed":True,"native_capture_observed":False,
            "official_sign_authorization_verified":False,"legal_outcome_claimed":False}


if __name__ == "__main__":
    for direction in ("left","right"):
        proof = audit(direction)
        target = ROOT/direction/"saved-source-audit.json"
        target.write_text(json.dumps(proof,indent=2,sort_keys=True)+"\n")
        print(json.dumps({"direction":direction,"audit_sha256":sha(target)},sort_keys=True))
