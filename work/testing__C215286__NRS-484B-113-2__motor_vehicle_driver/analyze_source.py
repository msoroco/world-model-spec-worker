"""Read original saved crosswalk frames without changing their bytes."""

import argparse
import hashlib
import json
from pathlib import Path

from crosswalk_delivery import audit, measure, validate_source
from site_packet import verify_saved

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def measure_crosswalk(frames, source):
    """Measure the selected original body/crossing stream by source identity."""
    return measure(frames, source_id=source["source_id"],
                   map_sha256=source["map_packet"]["map_sha256"],
                   crosswalk_source=source["map_packet"]["crosswalk_source"],
                   vehicle_actor_id=source["vehicle_actor_id"])


def load_measured(attempt):
    attempt = Path(attempt)
    context = attempt / "reviewed-crosswalk-source.json"
    frames_path = attempt / "channels" / "reverse-body-crosswalk.jsonl"
    if not context.is_file():
        raise ValueError("Missing required source: reviewed-crosswalk-source.json")
    if not frames_path.is_file():
        raise ValueError("Missing required source: channels/reverse-body-crosswalk.jsonl")
    source = json.loads(context.read_text())
    verify_saved(attempt, source)
    validate_source(source["map_packet"])
    actual_sha = hashlib.sha256(frames_path.read_bytes()).hexdigest()
    if actual_sha != source.get("frames_sha256"):
        raise ValueError("saved original frame hash differs")
    frames = [json.loads(line) for line in frames_path.read_text().splitlines()]
    if any(frame.get("crosswalk_polygon_xy") != source["map_packet"]["crosswalk_polygon_xy"]
           for frame in frames):
        raise ValueError("saved frame crosswalk differs from reviewed original map polygon")
    measured = measure_crosswalk(frames, source)
    return source, measured, actual_sha


def analyze(attempt, *, expected_relation):
    source, measured, actual_sha = load_measured(attempt)
    physical = audit(measured, expected_relation=expected_relation)
    root = Path(attempt)
    paths = ("channels/reverse-body-crosswalk.jsonl", "reviewed-crosswalk-source.json",
             "original-site-packet.json", "original-site-source.json")
    hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in paths}
    return {"format": "worker-analysis-report",
            "measurements": {"crosswalk_relation": {
                "value": physical, "method": "measure_crosswalk", "sources": hashes}},
            "source_sha256": actual_sha, "legal_judgment": "unresolved"}


def write_result(attempt, report, expected_relation):
    """Rebuild a fresh result from saved source files, never trust a fixture result."""
    root = Path(attempt)
    config = json.loads((root / "config.json").read_text())
    measured = report["measurements"]["crosswalk_relation"]["value"]
    target = {"target": "reverse_body_crosswalk_relation", "requested": expected_relation,
              "measured": measured, "method": "measure_crosswalk",
              "tolerance": {"polygon_contact_m": 1e-8, "reverse_speed_mps": .05},
              "matched": measured["observed_relation"] == expected_relation,
              "physical_cause_confirmed": False, "cause_evidence": []}
    result = {"case_id": config["selected_case_id"],
              "measured_values": {"crosswalk_relation": measured},
              "target_checks": [target], "setup_confirmed": False,
              "behavior_attempted": False, "maneuver_completed": False,
              "termination_reason": "Saved original sources measured; legal judgment unresolved",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": ["raw.mkv", *[view + ".mkv" for view in VIEWS]],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config["recording_description"],
              "recording_evidence": [
                  {"name": "reverse_body_crosswalk", "unit": "structured",
                   "reference": "reverse-body-crosswalk.jsonl"},
                  {"name": "marked_crosswalk_source", "unit": "metadata",
                   "reference": "marked-crosswalk-source.json"}],
              "realized_observables": {}, "physical_acceptance_claimed": False}
    from worker_exchange.native_output import physical_result, validate_result
    result = physical_result(root, result)
    validate_result(result)
    (root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    report.update(case_id=config["selected_case_id"],
                  physical_checks=result["physical_checks"],
                  realized_observables=result["realized_observables"],
                  provenance_kind=result["provenance_kind"],
                  diagnostic_fixture=result["diagnostic_fixture"],
                  analysis_complete=True,
                  limitations=["Physical source measurement only; legal judgment unresolved."])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-relation", choices=("disjoint", "contact", "overlap"))
    args = parser.parse_args()
    config = json.loads((Path(args.attempt) / "config.json").read_text())
    expected = config["case"]["target_physical_relation"]
    if args.expected_relation and args.expected_relation != expected:
        raise ValueError("requested analysis target differs from selected case")
    report = analyze(args.attempt, expected_relation=expected)
    write_result(args.attempt, report, expected)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
