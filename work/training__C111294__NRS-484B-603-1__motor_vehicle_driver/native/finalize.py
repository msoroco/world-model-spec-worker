"""Saved-only NRS 484B.603(1) approach measurement contract processor."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from measure_approach import measure


def _required(folder: Path, name: str) -> Path:
    path = folder / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure_intersection_approach(rows: list[dict], relation: dict,
                                  road: ET.Element) -> dict:
    if road.tag != "OpenDRIVE" or len(road.findall("road")) != 6:
        raise ValueError("Saved intersection map differs")
    other_start = rows[0]["other_position_m"]
    other_end = rows[-1]["other_position_m"]
    return {"declared_actor_role": rows[0]["ego_role"],
            "frames": relation["frames"],
            "approach_start_mph": relation["approach_start_mph"],
            "preentry_mph": relation["preentry_mph"],
            "crossing_peak_mph": relation["crossing_peak_mph"],
            "measured_decrease_mph": relation["decrease_mph"],
            "measured_relation": relation["measured_relation"],
            "measured_travel_direction_y": relation["measured_travel_direction_y"],
            "other_vehicle_displacement_m": round(abs(other_end[0]-other_start[0]), 3),
            "authored_road_count": len(road.findall("road")),
            "engineering_surrogate_thresholds_mph": relation["surrogate_thresholds_mph"],
            "reduction_necessity_legally_verified": False,
            "physical_hazard_observed": False,
            "legal_verdict": None}


def finalize(folder: Path, contract: dict, expected_source_sha256: str) -> dict:
    folder = Path(folder)
    rows_path = _required(folder, "native_samples.jsonl")
    road_path = _required(folder, "road.xodr")
    relation = measure(rows_path, expected_source_sha256)
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
    road = ET.parse(road_path).getroot()
    value = measure_intersection_approach(rows, relation, road)
    result = {"case_id": contract["case_id"], "source_kind": relation["source_kind"],
              "source_complete": True, "selected": False, "accepted": False,
              "legal_verdict": None, "measurements": {}}
    for req in contract["requirements"]:
        if req["output_key"] != "intersection_approach" or req["method"] != "measure_intersection_approach":
            raise ValueError("Measurement method differs from saved finalizer")
        result["measurements"][req["output_key"]] = {
            "method": req["method"], "value": value,
            "sources": {name: _sha(_required(folder, name)) for name in req["inputs"]}}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    contract = json.loads(args.contract.read_text())
    report = finalize(args.folder, contract, args.source_sha256)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"case_id": report["case_id"], "passed": True,
                      "source_kind": report["source_kind"], "selected": False},
                     sort_keys=True))
