"""Source-bound saved-only railroad stop measurements."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_rail_queue import measure
from source_review import ROLES, reviewed_context

ASSIGNMENT = "training__C202463__NRS-484B-560-3__motor_vehicle_driver"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CHANNELS = ("st.railway_crossing", "drv.stopped", "st.road_edge", "rel.occupies",
            "rel.longitudinal_overlap", "drv.laned_roadway", "st.lane_adjacency",
            "st.lane_marking")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def analyze(attempt):
    attempt = Path(attempt)
    required = ("config.json", "road.xodr", "rail-inventory.json", "geometry.json",
                "sources.json", "actors.jsonl", "gate.jsonl", "trace.jsonl",
                "video_frames.jsonl", "acquisition-provenance.json",
                *(name + ".mkv" for name in CAMERAS),
                *("rail-review/" + role + suffix for role in ROLES
                  for suffix in (".json", ".source.txt")))
    for name in required:
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    case = config.get("case_id", "")
    if (case not in tuple(ASSIGNMENT + "__probe_" + letter for letter in "abcde")
            or config.get("selected_case_id") != case
            or config.get("law_id") != "NRS-484B-560-3"
            or config.get("cell_id") != "C202463"
            or config.get("rate_hz") != 20 or config.get("duration_s") != 30):
        raise ValueError("Exact saved rail case contract differs")
    context = reviewed_context(attempt)
    rows = [json.loads(line) for line in (attempt / "actors.jsonl").read_text().splitlines()]
    gates = [json.loads(line) for line in (attempt / "gate.jsonl").read_text().splitlines()]
    frames = [json.loads(line) for line in (attempt / "video_frames.jsonl").read_text().splitlines()]
    if len(rows) != len(gates) or len(rows) != len(frames) or len(rows) != 600:
        raise ValueError("Incomplete saved Native rail frame join")
    for i, (row, gate, frame) in enumerate(zip(rows, gates, frames)):
        if (row.get("video_frame") != i or gate.get("video_frame") != i
                or frame.get("video_frame") != i
                or row["frame"] != gate["frame"]
                or row["frame"] != frame.get("native_frame")
                or row.get("camera_native_frames") != frame.get("camera_native_frames")):
            raise ValueError("Saved rail camera/actor/gate join differs")
    measurement = measure(attempt)
    if context["total_marked_lanes"] != measurement["total_marked_lanes"]:
        raise ValueError("Reviewed lane count differs")
    return {"case_id": case, "config": config, "context": context,
            "measurement": measurement,
            "source_sha256": {name: sha(attempt / name) for name in required},
            "rows": rows, "gates": gates}


def measure_required_stop(data):
    keys = ("rail-review/required-stop.json", "rail-review/required-stop.source.txt",
            "gate.jsonl", "road.xodr")
    return {"value": {"authority_source_reviewed": not data["context"]["diagnostic_fixture"],
                      "gate_stop_frames": data["measurement"]["stopped_during_gate_stop_frames"],
                      "legal_result": None}, "method": "measure_required_stop",
            "sources": {name: data["source_sha256"][name] for name in keys}}


def measure_far_right(data):
    keys = ("actors.jsonl", "geometry.json", "rail-review/right-edge.json",
            "rail-review/right-availability.json")
    return {"value": {"minimum_right_edge_gap_m": data["measurement"]["minimum_right_edge_gap_m"],
                      "rightmost_possible_judgment": "unresolved"},
            "method": "measure_far_right",
            "sources": {name: data["source_sha256"][name] for name in keys}}


def measure_two_lanes(data):
    keys = ("actors.jsonl", "gate.jsonl", "geometry.json", "video_frames.jsonl")
    return {"value": {"abreast_two_queue_frames": data["measurement"]["abreast_two_queue_frames"],
                      "legal_result": None}, "method": "measure_two_lanes",
            "sources": {name: data["source_sha256"][name] for name in keys}}


def measure_marked_lanes(data):
    keys = ("road.xodr", "rail-inventory.json", "rail-review/lane-markings.json",
            "rail-review/lane-markings.source.txt")
    return {"value": {"total_marked_lanes": data["measurement"]["total_marked_lanes"],
                      "four_or_more": data["measurement"]["total_marked_lanes"] >= 4,
                      "far_right_duty_still_applies": True},
            "method": "measure_marked_lanes",
            "sources": {name: data["source_sha256"][name] for name in keys}}


def finalize(attempt, output):
    from worker_exchange.native_output import write_result
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Retain prior saved rail measurement")
    data = analyze(attempt)
    observed = data["measurement"]
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    for name in CHANNELS:
        with (channels / (name + ".jsonl")).open("x") as stream:
            for row, gate in zip(data["rows"], data["gates"]):
                item = {"native_frame": row["frame"],
                        "source_reviewed": not data["context"]["diagnostic_fixture"],
                        "ego": row["actors"]["ego"], "other": row["actors"]["other"],
                        "gate_indication": gate["indication"],
                        "marked_lanes": observed["total_marked_lanes"]}
                stream.write(json.dumps({"time_s": row["time_s"], "value": item}) + "\n")
    case = data["case_id"]
    result = {"case_id": case,
        "measured_values": {"rail_stop_queue": {"value": observed,
            "source_hashes": data["source_sha256"], "legal_result": None}},
        "target_checks": [{"target": "sourced rail stop and queue geometry",
            "requested": data["config"]["queue_mode"], "measured": observed,
            "method": "saved source-bound rail actor/gate/road/video join", "tolerance": 0,
            "matched": False, "physical_cause_confirmed": False,
            "cause_evidence": list(data["source_sha256"])}],
        "setup_confirmed": False, "behavior_attempted": True,
        "maneuver_completed": False,
        "termination_reason": "Saved rail measurement complete; physical and legal judgment pending",
        "physical_failure_flags": ["original_rail_context_and_position_review_pending"],
        "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in CAMERAS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": data["config"]["recording_description"],
        "recording_evidence": [{"name": name, "unit": "structured",
            "reference": "channels/" + name + ".jsonl"} for name in CHANNELS],
        "realized_observables": {"marked_lane_count": {"value": observed["total_marked_lanes"],
            "unit": "lanes", "method": "reviewed original marked road",
            "time_window": "600 joined Native frames", "statistic": "fixed source inventory",
            "reference": "channels/st.lane_marking.jsonl"}},
        "accepted": False, "legal_verdict_claimed": False}
    write_result(attempt, result)
    report = {"format": "c202463-saved-rail-measurements-v1", "case_id": case,
        "measurements": {"required_stop": measure_required_stop(data),
                         "far_right": measure_far_right(data),
                         "two_lanes": measure_two_lanes(data),
                         "marked_lanes": measure_marked_lanes(data)},
        "diagnostic": {"source_sha256": data["source_sha256"],
            "diagnostic_fixture": data["context"]["diagnostic_fixture"]},
        "physical_acceptance_claimed": False, "legal_verdict_claimed": False}
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
