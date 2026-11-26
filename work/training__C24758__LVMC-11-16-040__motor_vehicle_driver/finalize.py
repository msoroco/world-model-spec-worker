"""Saved-only C24758 source review and measured output; no legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

from context_review import assemble, sha
from sight_speed_measure import EXPECTED_ID, require

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def measure_blind_speed(observation):
    """Original traversal speed in mph, retaining the complete source stream."""
    return observation["traversal_speed_mph_max"]


def measure_context(observation):
    """Return source references for independently reviewed exceptions and sight."""
    return {"exception_source_refs": observation["exception_context_source_refs"],
            "sight_limited_frame_count": observation["sight_limited_frame_count"],
            "last_100ft_sampled_frames": observation["last_100ft_sampled_frames"]}


def emit_stream(path, values):
    with path.open("x") as output:
        for i, value in enumerate(values):
            output.write(json.dumps({"time_s": i / 20, "value": value}) + "\n")


def run(attempt, output):
    attempt = Path(attempt).resolve()
    config = json.loads((attempt / "config.json").read_text())
    case = config["case_id"]
    require(case.startswith(EXPECTED_ID + "__"), "selected case identity changed")
    required = ("native-ego-readback.jsonl", "native-context-readback.json",
                "native-map-readback.xodr", "frame-map.json", "review.json",
                "video_frames.jsonl", "trace.jsonl")
    for name in required:
        require((attempt / name).is_file(), "Missing required source: " + name)
    for name in CAMERAS:
        require((attempt / (name + ".mkv")).is_file(),
                "Missing required source: " + name + ".mkv")
    measured = assemble(attempt, attempt / "review.json", attempt / "observation.json")
    observation = json.loads((attempt / "observation.json").read_text())
    require(observation["review_sha256"] == sha(attempt / "review.json"),
            "review changed after observation assembly")
    raw = [json.loads(line) for line in
           (attempt / "native-ego-readback.jsonl").read_text().splitlines()]
    rows = observation["frames"]
    require(len(raw) == len(rows) == 600, "saved Native frame count differs")
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    streams = {
        "ego_speed": [r["ego_speed_mps"] for r in raw],
        "ego_pose": [{"position_m": r["ego_xyz_m"], "heading_deg": r["ego_yaw_deg"]} for r in raw],
        "distance_to_boundary": [r["distance_to_boundary_m"] for r in rows],
        "intersection_sight": [r["intersection_clear_100ft"] for r in rows],
        "entering_approach_visibility": [r["entering_approach_views"] for r in rows],
        "intersection_traversal": ["in" if r["within_intersection"] else "out" for r in rows]}
    for name, values in streams.items():
        emit_stream(channels / (name + ".jsonl"), values)
    contexts = {
        "through_street_context": observation["context"]["through_street"],
        "traffic_control_context": observation["context"]["traffic_controlled_intersection"]}
    for name, value in contexts.items():
        (channels / (name + ".json")).write_text(json.dumps({name: value}, indent=2) + "\n")
    description = config["case"]["recording_description"]
    evidence = [{"name": item["name"], "unit": item["unit"],
                 "reference": "channels/" + item["name"] + ".jsonl"}
                for item in description["channels"]]
    evidence += [{"name": item["name"], "unit": item["unit"],
                  "reference": "channels/" + item["name"] + ".json"}
                 for item in description["context_inputs"]]
    requested = config["target_speed_mps"] * 2.2369362921
    observed = measure_blind_speed(measured)
    target_check = {"target": "requested traversal speed", "requested": requested,
                    "measured": observed, "method": "original Native velocity across intersection frames",
                    "tolerance": 1.1, "matched": abs(observed - requested) <= 1.1,
                    "physical_cause_confirmed": False,
                    "cause_evidence": ["native-ego-readback.jsonl", "review.json"]}
    result = {"case_id": case, "measured_values": {"traversal_speed_mph_max": observed,
              "sight_limited_frame_count": measured["sight_limited_frame_count"]},
              "target_checks": [target_check], "setup_confirmed": False,
              "behavior_attempted": False, "maneuver_completed": False,
              "termination_reason": "Source analysis complete; original physical review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in CAMERAS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": evidence,
              "realized_observables": {}}
    from worker_exchange.native_output import physical_result, validate_result
    result = physical_result(attempt, result)
    validate_result(result)
    (attempt / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    speed_sources = {name: sha(attempt / name) for name in
                     ("native-ego-readback.jsonl", "review.json")}
    context_sources = {name: sha(attempt / name) for name in
                       ("native-context-readback.json", "review.json")}
    report = {"format": "worker-analysis-report", "case_id": case,
        "measurements": {
            "blind_intersection_speed_mph": {"method": "measure_blind_speed",
                                             "value": observed, "sources": speed_sources},
            "sight_and_exception_context": {"method": "measure_context",
                                            "value": measure_context(measured),
                                            "sources": context_sources}},
        "physical_checks": result["physical_checks"],
        "realized_observables": result["realized_observables"],
        "limitations": ["Source review and measured speed do not establish prima facie legal status."]}
    Path(output).write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.attempt, args.output)


if __name__ == "__main__":
    main()
