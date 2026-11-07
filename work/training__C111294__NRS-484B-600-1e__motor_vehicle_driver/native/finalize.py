"""Saved-only C111294 measurement finalizer for unselected CPU fixtures."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from measure_speed import measure

INPUTS = ("native_samples.jsonl", "road.xodr")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _required(folder: Path, name: str) -> Path:
    path = folder / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def measure_subject_operation(rows: list[dict], speed: dict) -> dict:
    return {"ego_actor_id": speed["ego_actor_id"],
            "declared_blueprint": rows[0]["ego_blueprint"],
            "declared_role": rows[0]["ego_role"],
            "control_frames": sum(isinstance(r.get("ego_control"), dict) for r in rows),
            "personal_operation_legally_verified": False}


def measure_speed_relation(rows: list[dict], speed: dict) -> dict:
    return {"derived_peak_mph": speed["derived_peak_mph"],
            "uncertainty_mph": speed["uncertainty_mph"],
            "peak_interval_mph": speed["peak_interval_mph"],
            "statutory_value_mph": speed["statutory_value_mph"],
            "measured_relation": speed["measured_relation"],
            "velocity_source": speed["velocity_source"]}


def measure_unconditional_scope(rows: list[dict], road: ET.Element) -> dict:
    return {"authored_road_count": len(road.findall("road")),
            "authored_signal_count": len(road.findall(".//signal")),
            "measured_frames": len(rows),
            "posted_limit_used_in_speed_measurement": False,
            "territorial_applicability_verified": False}


def measure_other_vehicle_context(rows: list[dict], speed: dict) -> dict:
    return {"other_actor_id": speed["other_actor_id"],
            "other_declared_blueprint": rows[0]["other_blueprint"],
            "initial_native_position_m": rows[0]["other_position_m"],
            "last_native_position_m": rows[-1]["other_position_m"],
            "observed_route_motion_m": round(abs(
                rows[-1]["other_position_m"][1] - rows[0]["other_position_m"][1]), 6)}


def finalize(folder: Path, contract: dict, expected_source_sha256: str) -> dict:
    folder = Path(folder)
    paths = {name: _required(folder, name) for name in INPUTS}
    rows = [json.loads(line) for line in paths["native_samples.jsonl"].read_bytes().splitlines()]
    speed = measure(paths["native_samples.jsonl"], expected_source_sha256)
    road = ET.parse(paths["road.xodr"]).getroot()
    if road.tag != "OpenDRIVE" or len(road.findall("road")) != 6:
        raise ValueError("Saved map is not the six-road C111294 construction")
    values = {
        "subject_operation": measure_subject_operation(rows, speed),
        "speed_relation": measure_speed_relation(rows, speed),
        "unconditional_scope": measure_unconditional_scope(rows, road),
        "other_vehicle_context": measure_other_vehicle_context(rows, speed)}
    methods = {"subject_operation": "measure_subject_operation",
               "speed_relation": "measure_speed_relation",
               "unconditional_scope": "measure_unconditional_scope",
               "other_vehicle_context": "measure_other_vehicle_context"}
    report = {"case_id": contract["case_id"], "source_kind": speed["source_kind"],
              "source_complete": True, "selected": False, "accepted": False,
              "legal_verdict": None, "measurements": {}}
    for row in contract["requirements"]:
        key = row["output_key"]
        if key not in values or row["method"] != methods[key]:
            raise ValueError("Contract method differs from saved finalizer")
        report["measurements"][key] = {
            "method": methods[key], "value": values[key],
            "sources": {name: _sha(paths[name]) for name in row["inputs"]}}
    return report


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
                      "source_kind": report["source_kind"],
                      "selected": False}, sort_keys=True))
