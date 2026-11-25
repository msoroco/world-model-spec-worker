"""Saved-only subsection 2 finalization of original Native and camera sources."""

import argparse
import hashlib
import json
from pathlib import Path

from officer_camera import CAMERAS
from officer_saved_review import process
from officer_site import validate_site


ASSIGNMENT = "testing__C157964__NRS-484B-257-2__motor_vehicle_driver"
CHANNELS = ("officer_control_observed", "officer_direction_observed",
            "ego_body_in_intersection", "other_body_in_intersection",
            "other_approaching_observed", "ego_speed_mps", "other_speed_mps")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def measure_signed_entrance(attempt, observed):
    packet = json.loads((attempt / "source_review/source-packet.json").read_text())
    review = packet["review"]
    return {"site_id": packet["site_id"], "entrances": review["entrances"],
            "non_through_highway": True}


def measure_officer_control(attempt, observed):
    entry = observed["first_ego_entry"] or observed["first_hold_observation"]
    return entry["traffic_control_observed"]


def measure_officer_direction(attempt, observed):
    entry = observed["first_ego_entry"] or observed["first_hold_observation"]
    return entry["officer_direction_observed"]


def measure_other_traffic(attempt, observed):
    entry = observed["first_ego_entry"] or observed["first_hold_observation"]
    sample = next(row for row in observed["samples"] if row["frame"] == entry["frame"])
    return {"frame": entry["frame"],
            "body_in_intersection": sample["other_body_in_intersection"],
            "approaching_observed": sample["other_approaching_observed"],
            "immediate_hazard_judgment": "unresolved"}


def measure_ego_response(attempt, observed):
    entry = observed["first_ego_entry"] or observed["first_hold_observation"]
    sample = next(row for row in observed["samples"] if row["frame"] == entry["frame"])
    return {"frame": entry["frame"], "body_in_intersection": sample["ego_body_in_intersection"],
            "speed_mps": sample["ego_speed_mps"], "caution_judgment": "unresolved"}


def finalize(attempt, output, *, assessor=None, writer=None):
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / "result.json").exists() or (attempt / "channels").exists():
        raise ValueError("Retain prior saved finalization; choose a new attempt")
    required = ("runner.py", "config.json", "construction.json", "officer-site.xodr",
                "capture-receipt.json", "officer_review.json", "source_review/source-packet.json",
                "trace.jsonl", "video_frames.jsonl", "capture/evidence.jsonl",
                *(name + ".mkv" for name in CAMERAS))
    for name in required:
        path = attempt / name
        if not path.is_file() or not path.stat().st_size:
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    if (config.get("assignment_id") != ASSIGNMENT or
            config.get("law_id") != "NRS-484B-257-2" or
            config.get("cell_id") != "C157964" or
            config.get("actor") != "motor_vehicle_driver" or
            config.get("case", {}).get("case_id") != config.get("selected_case_id")):
        raise ValueError("Exact saved subsection 2 case identity required")
    site = validate_site(attempt / "officer-site.xodr")
    if config["site"]["xodr_sha256"] != site["site_sha256"]:
        raise ValueError("Saved officer site source differs")
    capture = json.loads((attempt / "capture-receipt.json").read_text())
    if capture.get("case_id") != config["selected_case_id"]:
        raise ValueError("Saved capture case differs")
    observed = process(
        attempt / "capture-receipt.json", attempt / "officer_review.json",
        attempt / "source_review", attempt / "source_review/source-packet.json",
        attempt, native_map_id=config["site"]["native_map_id"],
        intersection_id=config["officer_context"]["intersection_id"],
    )
    frame_map = _rows(attempt / "video_frames.jsonl")
    trace = _rows(attempt / "trace.jsonl")
    events = _rows(attempt / "capture/evidence.jsonl")
    samples = observed["samples"]
    if len(frame_map) != len(trace) or len(trace) != len(events) or len(events) != len(samples):
        raise ValueError("Original graph, camera and officer source counts differ")
    for frame, motion, event, sample in zip(frame_map, trace, events, samples):
        if (motion.get("frame") != frame.get("carla_frame") or
                motion.get("time_s") != frame.get("time_s") or
                event.get("original_frame") != frame.get("carla_frame") or
                sample["frame"] != frame.get("carla_frame") or
                sample["time_s"] != frame.get("time_s")):
            raise ValueError("Original graph, camera and officer frame join differs")
    channels = attempt / "channels"
    channels.mkdir()
    channel_keys = dict(zip(CHANNELS, (
        "traffic_control_observed", "direction", "ego_body_in_intersection",
        "other_body_in_intersection", "other_approaching_observed",
        "ego_speed_mps", "other_speed_mps")))
    other_speeds = [row["native_actor_source"]["other"]["speed_mps"]
                    for row in capture["rows"]]
    sweep_measurements = config["case"].get("sweep_measurements", [])
    sweep_names = {axis["observable"] for axis in sweep_measurements}
    first_other_entry = next((sample["frame"] for sample in samples
                              if sample["other_body_in_intersection"]), None)
    if "other_first_body_entry_frame" in sweep_names:
        if first_other_entry is None:
            raise ValueError("Other complete body never entered the original intersection source")
        with (channels / "other_first_body_entry_frame.jsonl").open("x") as stream:
            for sample in samples:
                stream.write(json.dumps({"original_frame": sample["frame"],
                                         "time_s": sample["time_s"],
                                         "value": first_other_entry}, allow_nan=False) + "\n")
    for name, key in channel_keys.items():
        with (channels / (name + ".jsonl")).open("x") as stream:
            for index, sample in enumerate(samples):
                value = other_speeds[index] if name == "other_speed_mps" else sample[key]
                stream.write(json.dumps({"original_frame": sample["frame"],
                                         "time_s": sample["time_s"], "value": value},
                                        allow_nan=False) + "\n")
    source_names = required + ("officer_context.json", "officer_history.jsonl")
    sources = {name: _sha(attempt / name) for name in source_names}
    (channels / "officer_context.json").write_text(json.dumps({
        "officer_context": {
            "first_ego_entry": observed["first_ego_entry"],
            "first_hold_observation": observed["first_hold_observation"],
            "police_authority_judgment": observed["police_authority_judgment"],
            "legal_control_exception_judgment": "unresolved",
        },
        "case_id": config["selected_case_id"],
        "first_ego_entry": observed["first_ego_entry"],
        "first_hold_observation": observed["first_hold_observation"],
        "legal_control_exception_judgment": "unresolved",
        "police_authority_judgment": observed["police_authority_judgment"],
        "source_sha256": sources,
    }, indent=2, allow_nan=False) + "\n")
    checks = []
    for check in observed["target_checks"]:
        checks.append(dict(check,
                           method="Independent original-camera review joined to Native complete-body frame",
                           tolerance="exact categorical observation",
                           cause_evidence=["officer_review.json", "capture-receipt.json",
                                           "video_frames.jsonl"]))
    result = {
        "case_id": config["selected_case_id"],
        "measured_values": {"first_ego_entry": observed["first_ego_entry"],
                            "first_hold_observation": observed["first_hold_observation"],
                            "other_inside_at_ego_entry": observed["other_inside_at_ego_entry"],
                            "other_approaching_observed_at_ego_entry": observed["other_approaching_observed_at_ego_entry"],
                            "legal_control_exception_judgment": "unresolved"},
        "target_checks": checks,
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "Saved original-source assessment pending independent physical review",
        "physical_failure_flags": [],
        "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in CAMERAS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": [
            {"name": name, "unit": next(channel["unit"] for channel in
                                         config["recording_description"]["channels"] if channel["name"] == name),
             "reference": "channels/" + name + ".jsonl"}
            for name in CHANNELS + (("other_first_body_entry_frame",)
                                    if "other_first_body_entry_frame" in sweep_names else ())
        ] + [{"name": "officer_context", "unit": "structured record",
              "reference": "channels/officer_context.json"}],
        "source_evidence_hashes": sources,
        "realized_observables": {},
    }
    if assessor is None or writer is None:
        from worker_exchange.native_output import physical_result, write_result
        assessor = physical_result
        writer = write_result
    result = assessor(attempt, result)
    for axis in sweep_measurements:
        observable = axis["observable"]
        result.setdefault("realized_observables", {})[observable] = dict(
            axis["measurement"], unit=axis["unit"],
            reference="channels/" + observable + ".jsonl",
            value=(max(sample["ego_speed_mps"] for sample in samples)
                   if observable == "ego_speed_mps" else first_other_entry),
            sample_window_s=[samples[0]["time_s"], samples[-1]["time_s"]])
    writer(attempt, result)
    measurement_spec = {
        "signed_entrance": (measure_signed_entrance, ("source_review/source-packet.json",)),
        "officer_control": (measure_officer_control, ("officer_review.json", "capture-receipt.json")),
        "officer_direction": (measure_officer_direction, ("officer_review.json", "video_frames.jsonl")),
        "other_traffic": (measure_other_traffic, ("officer_review.json", "capture-receipt.json")),
        "ego_response": (measure_ego_response, ("capture-receipt.json", "video_frames.jsonl")),
    }
    measurements = {key: {"method": method.__name__, "value": method(attempt, observed),
                          "sources": {name: _sha(attempt / name) for name in inputs}}
                    for key, (method, inputs) in measurement_spec.items()}
    report = {"format": "worker-c157964-subsection-2-saved-analysis",
              "case_id": config["selected_case_id"],
              "source_report": observed,
              "source_sha256": sources,
              "measurements": measurements,
              "physical_checks": result.get("physical_checks", {}),
              "realized_observables": result.get("realized_observables", {}),
              "analysis_complete": True,
              "physical_acceptance_claimed": False,
              "legal_conclusion": "unresolved"}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = finalize(args.attempt, args.output)
    print(json.dumps({"case_id": report["case_id"], "analysis_complete": True,
                      "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
