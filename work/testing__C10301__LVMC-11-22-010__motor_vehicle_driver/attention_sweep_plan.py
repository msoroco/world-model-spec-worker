"""Draft a physical attention sweep only from reviewed original sources.

This emits a proposal for later canonical stage integration. It does not alter
selected cases or turn observed gaze into a legal label.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

from reviewed_attention_intake import validate


def draft(packet_path: Path, cases_path: Path, *, allow_diagnostic: bool = False) -> dict:
    intake = validate(packet_path, allow_diagnostic=allow_diagnostic)
    cases = json.loads(Path(cases_path).read_text())
    old = next((row for row in cases.get("sweep_specs", [])
                if row.get("sweep_id") == "alley_attention_observation"), None)
    baseline = next((row for row in cases.get("cases", [])
                     if row.get("target_type") == "baseline"), None)
    if (cases.get("cell_id") != "C10301" or cases.get("actor") != "motor_vehicle_driver"
            or old is None or old.get("status") != "incomplete" or baseline is None):
        raise ValueError("original C10301 incomplete attention sweep required")
    axis = deepcopy(intake["axis"])
    feasible = intake["source_sha256"]["control_feasibility"]
    sensor = intake["source_sha256"]["interior_sensor"]
    physical_axis = {key: axis[key] for key in
                     ("variable", "observable", "unit", "min", "max", "spacing",
                      "measurement", "range_rationale", "spacing_rationale")}
    physical_axis["feasibility_evidence"] = (
        "reviewed original Native control feasibility SHA256 " + feasible
        + "; original interior sensor SHA256 " + sensor)
    description = deepcopy(baseline["recording_description"])
    description["channels"].append({
        "name": axis["observable"], "unit": axis["unit"],
        "sampling_rate_hz": 20,
        "method": "original interior sensor cumulative duration history",
        "time_window": "full original 45-second alley operation",
        "reference_frame": "same original Native frame and simulation time",
        "uncertainty": "20 Hz sampling; measured interior gaze is not a legal attention finding",
    })
    description["context_inputs"].append({
        "name": "reviewed_original_interior_sensor", "unit": "source citation",
        "method": "original Native sensor identity and source hash",
    })
    description["limitations"].append(
        "A physical gaze-duration sample does not define full time and attention or a statutory cutoff.")
    assignments = deepcopy(baseline["variable_assignments"])
    assignments["lateral_controller_profile"]["value"] = "steady"
    assignments[axis["variable"]] = {
        "kind": "controller", "value": axis["min"],
        "note": "Source-reviewed physical setpoint; actual original gaze is measured separately",
    }
    spec = {key: deepcopy(old[key]) for key in ("sweep_id", "target_law_id", "judgment_refs")}
    spec.update({
        "status": "complete", "mode": "one_dimensional", "axes": [physical_axis],
        "landmarks": [],
        "rationale": "Fixed source-reviewed physical interior gaze coverage with legal judgment unresolved",
        "variable_assignments": assignments,
        "recording_description": description,
    })
    return {
        "format": "worker-source-gated-attention-sweep-draft",
        "assignment_id": intake["assignment_id"],
        "intake_packet_sha256": intake["packet_sha256"],
        "diagnostic_fixture": intake["diagnostic_fixture"],
        "sweep_spec": spec,
        "binding_parameter": {
            "name": axis["variable"], "kind": "controller",
            "range_or_domain": "reviewed original physical grid",
            "used_by_laws": ["LVMC-11-22-010"],
        },
        "observable_requirement": {
            "name": axis["observable"], "unit": axis["unit"],
            "description": "source-bound original interior sensor readback; no legal threshold",
        },
        "legal_judgment": "unresolved",
        "selected_cases_changed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("attention sweep draft output already exists")
    result = draft(args.packet, args.cases)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
