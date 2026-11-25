"""Saved-only sidewalk fixture measurement; original source roles are mandatory."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_fixture import CAMERAS, measure
from source_review import ROLES, reviewed_context

ASSIGNMENT = "training__C150668__LVMC-11-52-130-A5__motor_vehicle_driver"
MEASUREMENT_INPUTS = ("vehicle-poses.jsonl", "video_frames.jsonl",
    "fixture-review/fixture-identity.json", "fixture-review/fixture-geometry.json",
    "fixture-review/sidewalk-geometry.json", "fixture-review/front-orientation.json",
    "road.xodr")
EXCEPTION_INPUTS = ("fixture-review/traffic-context.json",
                    "fixture-review/police-direction.json",
                    "fixture-review/device-direction.json")
CHANNELS = ("st.obstruction", "st.sidewalk", "rel.centre_distance",
            "drv.standing_or_parked", "rel.occupies", "kin.extent",
            "traffic_conflict_context", "police_direction_context",
            "device_direction_context")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def analyze(attempt):
    attempt = Path(attempt)
    for name in ("config.json", "vehicle-poses.jsonl", "video_frames.jsonl",
                 "trace.jsonl", *(camera + ".mkv" for camera in sorted(CAMERAS))):
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    case = config.get("case_id")
    if case not in tuple(ASSIGNMENT + "__probe_" + str(i) for i in range(1, 8)) or config.get(
            "selected_case_id") != case or config.get("law_id") != "LVMC-11-52-130-A5" or config.get(
            "cell_id") != "C150668" or config.get("rate_hz") != 20 or config.get(
            "duration_s") != 30:
        raise ValueError("Exact saved case contract differs")
    context = reviewed_context(attempt)
    mode = config.get("exception_mode", "none")
    if mode not in ("none", "traffic_conflict", "police_direction", "device_direction"):
        raise ValueError("Unknown exception mode")
    if (context["traffic_conflict_reviewed"],
            context["police_stop_direction_reviewed"],
            context["device_stop_direction_reviewed"]) != (
                mode == "traffic_conflict", mode == "police_direction",
                mode == "device_direction"):
        raise ValueError("Exception source context differs from selected mode")
    poses = [json.loads(line) for line in (attempt / "vehicle-poses.jsonl").read_text().splitlines()]
    frames = [json.loads(line) for line in (attempt / "video_frames.jsonl").read_text().splitlines()]
    if len(poses) != 600 or len(frames) != 600:
        raise ValueError("Incomplete saved Native frame join")
    for pose, frame in zip(poses, frames):
        if any(pose.get(key) != frame.get(key) for key in
               ("video_frame", "native_frame", "time_s", "camera_native_frames")):
            raise ValueError("Saved Native camera/pose join differs")
    measured = measure(context, poses)
    source_names = ("road.xodr", "fixture-inventory.json", "vehicle-poses.jsonl",
                    "video_frames.jsonl", "trace.jsonl", *(camera + ".mkv" for camera in sorted(CAMERAS)),
                    *("fixture-review/" + role + ".json" for role in ROLES),
                    *("fixture-review/" + role + ".source.txt" for role in ROLES))
    return {"case_id": case, "config": config, "measurement": measured,
            "context": context,
            "source_sha256": {name: sha(attempt / name) for name in source_names},
            "diagnostic_fixture": context["diagnostic_fixture"]}


def measure_fixture_stop(data):
    return {"value": data["measurement"], "method": "measure_fixture_stop",
            "sources": {name: data["source_sha256"][name] for name in MEASUREMENT_INPUTS}}


def measure_direct_front(data):
    return {"value": {"frame_count_at_rest": data["measurement"]["directly_in_front_frame_count_at_rest"]},
            "method": "measure_direct_front", "sources": {name: data["source_sha256"][name]
                for name in ("vehicle-poses.jsonl", "video_frames.jsonl",
                             "fixture-review/front-orientation.json", "fixture-review/fixture-geometry.json")}}


def measure_traffic_exception(data):
    return {"value": {"conflict_necessity_source_reviewed": data["context"]["traffic_conflict_reviewed"],
                      "legal_exception_result": None},
            "method": "measure_traffic_exception", "sources": {name: data["source_sha256"][name]
                for name in ("fixture-review/traffic-context.json", "trace.jsonl")}}


def measure_police_exception(data):
    return {"value": {"police_stop_direction_source_reviewed": data["context"]["police_stop_direction_reviewed"],
                      "legal_exception_result": None},
            "method": "measure_police_exception", "sources": {name: data["source_sha256"][name]
                for name in ("fixture-review/police-direction.json", "trace.jsonl")}}


def measure_device_exception(data):
    return {"value": {"device_stop_direction_source_reviewed": data["context"]["device_stop_direction_reviewed"],
                      "legal_exception_result": None},
            "method": "measure_device_exception", "sources": {name: data["source_sha256"][name]
                for name in ("fixture-review/device-direction.json", "trace.jsonl")}}


def finalize(attempt, output):
    from worker_exchange.native_output import write_result
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Retain prior saved analysis/result")
    data = analyze(attempt)
    value = data["measurement"]
    poses = [json.loads(line) for line in (attempt / "vehicle-poses.jsonl").read_text().splitlines()]
    channels = attempt / "channels"
    channels.mkdir()
    for name in CHANNELS:
        with (channels / (name + ".jsonl")).open("x") as stream:
            for row in poses:
                if name == "st.obstruction":
                    item = {"fixture_kind": "sidewalk_elevator",
                            "source_reviewed": True}
                elif name == "st.sidewalk":
                    item = {"sidewalk_geometry_source_reviewed": True}
                elif name == "rel.centre_distance":
                    item = {"side_clearance_m": value["side_clearance_m_range_at_rest"][0]}
                elif name == "drv.standing_or_parked":
                    item = {"stationary_diagnostic": row["observed_vehicle_speed_mps"] <= .10,
                            "legal_purpose_classified": False}
                elif name == "rel.occupies":
                    item = {"direct_front_frame_count_at_rest": value["directly_in_front_frame_count_at_rest"]}
                elif name == "traffic_conflict_context":
                    item = {"conflict_necessity_source_reviewed": data["context"]["traffic_conflict_reviewed"]}
                elif name == "police_direction_context":
                    item = {"police_stop_direction_source_reviewed": data["context"]["police_stop_direction_reviewed"]}
                elif name == "device_direction_context":
                    item = {"device_stop_direction_source_reviewed": data["context"]["device_stop_direction_reviewed"]}
                else:
                    item = {"vehicle_footprint_m": row["vehicle_footprint_m"]}
                stream.write(json.dumps({"time_s": row["time_s"], "value": item}) + "\n")
    requested = ("outside" if data["case_id"].endswith("probe_1") else
                 "front" if data["case_id"].endswith("probe_3") else "side_band")
    observed = ("front" if value["directly_in_front_frame_count_at_rest"] >= 100 else
                "side_band" if value["within_five_foot_side_band_at_rest"] else "outside")
    source = data["source_sha256"]
    result = {"case_id": data["case_id"],
              "measured_values": {"fixture_stop": {"value": value,
                  "source_hashes": source, "legal_result": None}},
              "target_checks": [{"target": "five-foot sidewalk fixture side band",
                  "requested": requested, "measured": observed,
                  "method": "saved vehicle footprint and separately sourced fixture bounds",
                  "tolerance": 0, "matched": requested == observed,
                  "physical_cause_confirmed": False,
                  "cause_evidence": list(source)}],
              "setup_confirmed": False, "behavior_attempted": True,
              "maneuver_completed": False,
              "termination_reason": "Saved source meter complete; original fixture identity and legal exceptions require review",
              "physical_failure_flags": ["original_fixture_and_exception_review_pending"],
              "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in sorted(CAMERAS)],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": data["config"]["recording_description"],
              "recording_evidence": [{"name": name, "unit": "structured",
                  "reference": "channels/" + name + ".jsonl"} for name in CHANNELS],
              "realized_observables": {"side_clearance_m": {
                  "value": value["side_clearance_m_range_at_rest"][0], "unit": "m",
                  "method": "saved footprint to sourced fixture side extents",
                  "time_window": "longest observed rest interval",
                  "statistic": "minimum", "reference": "channels/rel.centre_distance.jsonl"}},
              "accepted": False, "legal_verdict_claimed": False}
    write_result(attempt, result)
    report = {"format": "c150668-saved-fixture-measurements-v1",
              "case_id": data["case_id"],
              "measurements": {"fixture_stop": measure_fixture_stop(data),
                               "direct_front": measure_direct_front(data),
                               "traffic_exception": measure_traffic_exception(data),
                               "police_exception": measure_police_exception(data),
                               "device_exception": measure_device_exception(data)},
              "diagnostic": {"source_sha256": source,
                             "diagnostic_fixture": data["diagnostic_fixture"]},
              "physical_acceptance_claimed": False,
              "legal_verdict_claimed": False}
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
