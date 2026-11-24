"""Source-bound saved intersection measurement without a legal conclusion."""
import argparse
import hashlib
import json
from pathlib import Path

from finalize_delivery import finalize_saved
from finalize_observables import finalize as finalize_original


def measure_intersection_contact(observations):
    frames = observations["frames"]
    return {"contact_frames": [row["frame"] for row in frames if row["within_or_touching_boundary"]],
            "frame_count": len(frames), "boundary_method": observations["boundary_method"]}


def measure_activity(observations):
    return {"original_observation": observations["activity_observation"],
            "independent_sample_count": len(observations["activity_samples"] or []),
            "legal_class": "unresolved"}


def measure_traffic_conflict(observations):
    return {"original_observation": observations["traffic_conflict_observation"],
            "necessity_judgment": "unresolved"}


def measure_law_direction(observations):
    return {"original_observation": observations["law_direction_observation"],
            "applicable_law_judgment": "unresolved"}


def measure_officer_direction(observations):
    return {"original_observation": observations["officer_direction_observation"],
            "compliance_judgment": "unresolved"}


def measure_device_direction(observations):
    return {"original_observation": observations["device_direction_observation"],
            "compliance_judgment": "unresolved"}


def analyze(attempt, case_id, contract):
    attempt = Path(attempt)
    contract = Path(contract)
    spec = json.loads(contract.read_text())
    if spec["case_id"] != case_id:
        raise ValueError("selected measurement contract case differs")
    for row in spec["requirements"]:
        for relative in row["inputs"]:
            if not (attempt / relative).is_file():
                raise ValueError("Missing required source: " + relative)
    diagnostic = (attempt / "acquisition-provenance.json").is_file() and json.loads(
        (attempt / "acquisition-provenance.json").read_text()).get("diagnostic_fixture") is True
    if diagnostic:
        diagnostic_manifest = attempt / "diagnostic-manifest.json"
        source_manifest = json.loads(diagnostic_manifest.read_text())
        if source_manifest.get("diagnostic_fixture") is not True:
            raise ValueError("compact fixture must declare synthetic provenance in its source seal")
        observations = finalize_original(diagnostic_manifest)
        saved = {"source_manifest_sha256": hashlib.sha256(diagnostic_manifest.read_bytes()).hexdigest()}
    else:
        saved = finalize_saved(attempt, expected_case=case_id)
        observations = saved["observations"]
    methods = {name: globals()[name] for name in (
        "measure_intersection_contact", "measure_activity", "measure_traffic_conflict",
        "measure_law_direction", "measure_officer_direction", "measure_device_direction")}
    measurements = {}
    for row in spec["requirements"]:
        sources = {name: hashlib.sha256((attempt / name).read_bytes()).hexdigest()
                   for name in row["inputs"]}
        measurements[row["output_key"]] = {"method": row["method"],
            "value": methods[row["method"]](observations), "sources": sources}
    report = {"case_id": case_id, "measurements": measurements,
            "source_manifest_sha256": saved["source_manifest_sha256"],
            "physical_completion_verified": False, "legal_conclusion": None}
    if (attempt / "config.json").is_file() and (attempt / "trace.jsonl").is_file():
        from worker_exchange.native_output import physical_result, validate_result
        config = json.loads((attempt / "config.json").read_text())
        description = json.loads((attempt / "construction.json").read_text())["recording_description"]
        trace = json.loads((attempt / "trace.json").read_text())["samples"]
        activity = json.loads((attempt / "activity.json").read_text())
        streams = {
            "activity_history": [row.get("activity_observation") or {"status": "unresolved"} for row in activity["activity_samples"]],
            "body_footprint_history": [row["body_footprint"] for row in trace],
            "traffic_conflict_history": [row.get("traffic_conflict_observation") or {"status": "unresolved"} for row in activity["activity_samples"]],
            "direction_history": [{"law": row.get("law_direction_observation"),
                                   "officer": row.get("officer_direction_observation"),
                                   "device": row.get("device_direction_observation")} for row in activity["activity_samples"]],
        }
        channel_dir = attempt / "channels"
        channel_dir.mkdir(exist_ok=True)
        evidence = []
        for channel in description["channels"]:
            name = channel["name"]
            path = channel_dir / (name + ".jsonl")
            with path.open("x") as output:
                for row, value in zip(trace, streams[name]):
                    output.write(json.dumps({"time_s": row["time_s"], "value": value}) + "\n")
            evidence.append({"name": name, "unit": channel["unit"],
                             "reference": str(path.relative_to(attempt))})
        context_path = channel_dir / "context.json"
        context_path.write_text(json.dumps({"intersection_geometry": json.loads((attempt / "boundary.json").read_text()),
                                            "applicable_law_source": {"status": "unresolved"}}) + "\n")
        for context in description["context_inputs"]:
            evidence.append({"name": context["name"], "unit": context["unit"],
                             "reference": str(context_path.relative_to(attempt))})
        target = {"target": "source-bound intersection observations", "requested": True,
                  "measured": bool(measurements), "method": "saved original source join", "tolerance": 0,
                  "matched": bool(measurements), "physical_cause_confirmed": False,
                  "cause_evidence": observations["source_seals"]}
        result = {"case_id": case_id, "measured_values": measurements,
                  "target_checks": [target], "setup_confirmed": False, "behavior_attempted": False,
                  "maneuver_completed": False, "termination_reason": "Saved source observations; legal judgment unresolved",
                  "physical_failure_flags": [], "trace_reference": "trace.jsonl",
                  "video_references": [name + ".mkv" for name in ("overview", "approach", "reference_corner", "driver_reference")],
                  "video_frame_map_reference": "video_frames.jsonl", "recording_description": description,
                  "recording_evidence": evidence, "realized_observables": {}}
        result = physical_result(attempt, result)
        validate_result(result)
        (attempt / "result.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case")
    parser.add_argument("--contract")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    attempt = Path(args.attempt)
    case_id = args.case
    if case_id is None:
        case_id = json.loads((attempt / "config.json").read_text())["selected_case_id"]
    contract = args.contract or attempt / "measurement-contract.json"
    result = analyze(attempt, case_id, contract)
    output = Path(args.output)
    if output.exists():
        raise ValueError("retain prior measurement output; choose fresh path")
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print("exact source-bound intersection measurements complete: " + case_id)


if __name__ == "__main__":
    main()
