"""Materialize exact catalog-cell route and sign sources for lead integration."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from geometry import CELLS, FRAMES, TURN_FIRST_FRAME, check, open_drive, sampled_source

ROOT = Path(__file__).resolve().parent
SOURCE_LAW = "LVMC-11-40-080"
REPO = ROOT.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def build(direction):
    proof = check(direction)
    cell_id, maneuver, sign_code, _ = CELLS[direction]
    catalog_path = REPO / "inputs/coverage/candidate-cells.json"
    catalog = json.loads(catalog_path.read_text())
    matching = [item for item in catalog["cells"] if item["cell_id"] == cell_id]
    if len(matching) != 1 or any(matching[0].get(key) != value for key, value in (
            ("layout", "hill_crest"), ("maneuver", maneuver),
            ("control", "turn_prohibition_device"))):
        raise ValueError("Candidate catalog cell does not match signed turn")
    folder = ROOT / direction
    folder.mkdir(exist_ok=True)
    road = folder / "road.xodr"
    road.write_text(open_drive(direction) + "\n")
    cases = []
    for behavior in ("obey", "turn"):
        case_id = f"training__{cell_id}__{SOURCE_LAW}__cycle_or_scooter_operator__controlled_{1 if behavior=='obey' else 2}"
        rows = sampled_source(direction, behavior)
        route = folder / f"{behavior}-source.jsonl"
        route.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
        cases.append({"case_id":case_id,"behavior":behavior,"maneuver":maneuver,
                      "sign_code":sign_code,"road_source":road.relative_to(ROOT).as_posix(),
                      "road_sha256":sha(road),"sampled_source":route.relative_to(ROOT).as_posix(),
                      "sampled_source_sha256":sha(route),"frames":FRAMES,
                      "status":"staged_cpu_source_only"})
    obey = sampled_source(direction,"obey")
    turn = sampled_source(direction,"turn")
    for index in range(TURN_FIRST_FRAME+1):
        if obey[index]["body_center_xy_m"] != turn[index]["body_center_xy_m"]:
            raise ValueError("Controlled approach changed")
    if obey[-1]["body_center_xy_m"] == turn[-1]["body_center_xy_m"]:
        raise ValueError("Turn response is not distinct")
    source = {"format":"c104538-compatible-turn-cell-staging-v1",
              "law_id":SOURCE_LAW,"cell_id":cell_id,
              "frozen_catalog_source":"inputs/coverage/candidate-cells.json",
              "frozen_catalog_sha256":sha(catalog_path),
              "frozen_catalog_cell":matching[0],
              "matching_catalog_cell":proof,
              "cases":cases,"controlled_pair":{"fixed":"machine, sign, governed approach, map and first 221 positions",
                                         "changed":"requested route through versus actual right/left turn",
                                         "turn_starts_frame":TURN_FIRST_FRAME,
                                         "observed_source_kind":"authored_cpu_route_plan"},
              "native_capture_executed":False,"public_compatibility_passed":False,
              "saved_replay_passed":False,"semantic_delivery_passed":False,
              "physical_acceptance_claimed":False}
    target=folder/"staging-index.json"
    write_json(target,source)
    return target,sha(target)


if __name__ == "__main__":
    for direction in ("left","right"):
        target,digest=build(direction)
        print(json.dumps({"direction":direction,"index":str(target.relative_to(ROOT)),
                          "sha256":digest},sort_keys=True))
