"""Synthetic freight protocol analysis for CPU compatibility only."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from freight_zone import CASES, measure_history


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def measure_freight_zone(rows, case, scene):
    """Bind the case-specific synthetic source rows to the shared measurement."""
    return measure_history([{**row, "case_id": case.name} for row in rows], case, scene)


def analyze(attempt):
    root = Path(attempt)
    config = json.loads(required(root, "config.json").read_text())
    scene = json.loads(required(root, "scene.json").read_text())
    note_path = required(root, "diagnostic-source-note.json")
    note = json.loads(note_path.read_text())
    if (note.get("source_kind") != "synthetic_diagnostic_fixture" or
            note.get("accepted_original_source") is not False or
            scene.get("source_kind") != "synthetic_diagnostic_fixture"):
        raise ValueError("synthetic freight diagnostic provenance required")
    case = next((c for c in CASES if c.name == config["case"]["name"]), None)
    if case is None or scene.get("case_id") != config.get("selected_case_id"):
        raise ValueError("exact freight diagnostic case changed")
    row_path = required(root, "freight-rows.json")
    rows = json.loads(row_path.read_text())
    if len(rows) != 900:
        raise ValueError("900 synthetic freight rows required")
    # Only the case label differs between the exact recipe and original-history
    # measurement API. All source and frame fields are checked by that API.
    measured = measure_freight_zone(rows, case, scene)
    sources = {"freight-rows.json": sha(row_path), "diagnostic-source-note.json": sha(note_path)}
    channels = config["case"]["recording_description"]["channels"]
    values = {
        "marked_freight_zone": lambda row: {"zone_source_sha256": row["zone_source_sha256"],
                                               "inside_zone": row["ego_center_xy"] == [4, 0]},
        "effective_hours": lambda row: {"effective": scene["regulations"]["effective_at_civil_time"],
                                         "civil_time": scene["clock"]["civil_time_iso"]},
        "ego_halt_and_conduct": lambda row: {"ego_id": row["ego_id"], "speed_mps": row["ego_speed_mps"],
                                              "center_xy": row["ego_center_xy"]},
        "materials_activity": lambda row: {"event": row["material_event"], "materials_id": row["materials_id"]},
        "passenger_activity": lambda row: {"event": row["passenger_event"], "passenger_id": row["passenger_id"]},
        "freight_vehicle_entry": lambda row: {"event": row["freight_event"],
                                                "freight_vehicle_id": row["freight_vehicle_id"],
                                                "entry_blocked": row["freight_entry_blocked"]},
        "traffic_and_official_directions": lambda row: {"source_sha256": row["traffic_and_official_directions_source_sha256"]},
        "expeditiousness": lambda row: {"first_material_event_frame": measured["first_material_event_frame"],
                                        "legal_judgment": None},
        "camera_frame_identity": lambda row: {"original_frame": row["original_frame"]},
    }
    evidence = []
    for channel in channels:
        name = channel["name"]
        if name not in values:
            raise ValueError("unknown freight diagnostic channel: " + name)
        path = root / ("channel-" + name + ".jsonl")
        path.write_text("".join(json.dumps({"time_s": row["elapsed_s"], "value": values[name](row)}) + "\n" for row in rows))
        evidence.append({"name": name, "unit": channel["unit"], "reference": path.name})
    from worker_exchange.native_output import physical_result, write_result
    result = {"case_id": config["selected_case_id"], "measured_values": measured,
              "target_checks": [{"target": "synthetic freight curb protocol",
                                 "requested": config["case"], "measured": measured,
                                 "method": "900 source-shaped synthetic joined rows",
                                 "tolerance": 0, "matched": True,
                                 "physical_cause_confirmed": False, "cause_evidence": sources}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False, "termination_reason": "synthetic compatibility only",
              "physical_failure_flags": ["original_freight_marking_provision_activity_absent"],
              "trace_reference": "trace.jsonl",
              "video_references": [x + ".mkv" for x in ("overview", "approach", "reference_corner", "driver_reference")],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config["case"]["recording_description"],
              "recording_evidence": evidence, "realized_observables": {},
              "diagnostic_fixture": True, "physical_acceptance_claimed": False,
              "legal_verdict_claimed": False}
    result = physical_result(root, result)
    write_result(root, result)
    return {"format": "worker-analysis-report", "case_id": config["selected_case_id"],
            "analysis_complete": True, "diagnostic_fixture": True,
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False,
            "measurements": {"freight_curb_zone": {"method": "measure_freight_zone",
                                                    "value": measured, "sources": sources}},
            "physical_checks": result["physical_checks"], "realized_observables": {},
            "limitations": ["Synthetic fixture proves software compatibility only; original freight marking, materials transfer, passenger exception and legal review remain open."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior freight analysis report")
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + "\n")
