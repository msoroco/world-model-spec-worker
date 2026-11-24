"""Selected saved-only analyzer for exact NRS 484B.253 diagnostic compatibility.

The same source join applies to Native and diagnostic acquisitions. Diagnostic
outputs remain labeled synthetic and never assert physical or legal acceptance.
"""

import argparse
import json
from pathlib import Path

from requirement_finalizer import finalize
from requirement_finalizer import measure_initial_within as _initial
from requirement_finalizer import measure_approaching as _approaching
from requirement_finalizer import measure_permission as _permission
from requirement_finalizer import measure_reciprocal as _reciprocal


def measure_initial_within(rows):
    return _initial(rows)


def measure_approaching(rows):
    return _approaching(rows)


def measure_permission(rows):
    return _permission(rows)


def measure_reciprocal(rows):
    return _reciprocal(rows)


def analyze(attempt):
    from worker_exchange.native_output import physical_result, validate_result

    root = Path(attempt)
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    case_id = config["selected_case_id"]
    receipt = json.loads((root / "acquisition-receipt.json").read_text(encoding="utf-8"))
    if receipt["case_id"] != case_id:
        raise ValueError("acquisition receipt identity mismatch")
    diagnostic = receipt["diagnostic_fixture"] is True
    report = finalize(case_id=case_id, attempt=root, allow_diagnostic=diagnostic)
    if report["diagnostic_fixture"] != diagnostic:
        raise ValueError("diagnostic provenance mismatch")
    description = config["case"]["recording_description"]
    if description != json.loads((root / "construction.json").read_text(encoding="utf-8"))["recording_description"]:
        raise ValueError("saved recording description changed")
    samples = [json.loads(line) for line in (root / "original-trace.jsonl").read_text(encoding="utf-8").splitlines()]
    output = root / "channels"
    output.mkdir(exist_ok=True)
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        if name == "ego_body_history":
            values = [(row["time_s"], row["ego_vertices"]) for row in samples]
        elif name == "opponent_body_history":
            values = [(row["time_s"], row["opponent_vertices"]) for row in samples]
        elif name == "ego_signal_history":
            values = [(row["time_s"], row["ego_signal_left"]) for row in samples]
        else:
            raise ValueError("Unsupported recorded channel: " + name)
        path = output / (name + ".jsonl")
        with path.open("x", encoding="utf-8") as stream:
            for time_s, value in values:
                stream.write(json.dumps({"time_s": time_s, "value": value}) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(path.relative_to(root))})
    context = {"intersection_geometry": json.loads((root / "original-map.json").read_text(encoding="utf-8"))["intersection_polygon"]}
    context_path = output / "context.json"
    context_path.write_text(json.dumps(context) + "\n", encoding="utf-8")
    for item in description["context_inputs"]:
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": str(context_path.relative_to(root))})
    observed = report["observations"]
    target = {"target": "source-bound exact left-turn events",
              "requested": True, "measured": bool(observed),
              "method": report["method"], "tolerance": 0,
              "matched": bool(observed), "physical_cause_confirmed": False,
              "cause_evidence": report["source_hashes"]}
    result = {"case_id": case_id, "measured_values": observed,
              "target_checks": [target], "setup_confirmed": False,
              "behavior_attempted": False, "maneuver_completed": False,
              "termination_reason": "Saved original events measured; physical acceptance pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in
                                   ("overview", "approach", "reference_corner", "driver_reference")],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": evidence,
              "realized_observables": {}}
    result = physical_result(root, result)
    validate_result(result)
    (root / "result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    Path(args.output).write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
