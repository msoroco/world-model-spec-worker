"""Source-only finalization of exact C111125 bicycle red-signal measurements.

The diagnostic Native/Core conversion bridge supplies original text streams and
four FFV1 views. This analyzer never assigns legal or physical acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


BASE = Path(__file__).resolve().parent


def _need(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def _load_trial():
    spec = importlib.util.spec_from_file_location("c111125_8d_analysis_trial", BASE / "signal_trial.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def measure_actor(measured):
    return {"blueprint_class": "bicycle", "blueprint_sha256": measured["blueprint_sha256"]}


def measure_subject_signal(measured):
    return {"red_held_to_entry": measured["red_held_to_entry"],
            "device_sha256": measured["device_sha256"]}


def measure_prior_stop(measured):
    return {"prior_stop_observed": measured["prior_stop_observed"],
            "entry_frame": measured["entry_frame"]}


def measure_complete_cycles(measured):
    return {"complete_device_cycles_before_entry": measured["complete_device_cycles_before_entry"],
            "completed_cycle_window_frames": measured["completed_cycle_window_frames"]}


def measure_detector_link(measured):
    return {"detector_occupied_through_completed_cycles": measured["detector_occupied_through_completed_cycles"],
            "detector_failure_observed": measured["detector_failure_observed"],
            "detector_sha256": measured["detector_sha256"]}


def measure_yield_and_entry(measured):
    return {"conflict_at_entry": measured["conflict_at_entry"],
            "straight_route_observed": measured["straight_route_observed"],
            "entry_frame": measured["entry_frame"]}


ROWS = (("bicycle_actor", measure_actor),
        ("official_subject_signal", measure_subject_signal),
        ("antecedent_stop", measure_prior_stop),
        ("complete_device_cycles", measure_complete_cycles),
        ("failed_detection", measure_detector_link),
        ("yield_and_straight_entry", measure_yield_and_entry))

SOURCE_NAMES = ("native-site.json", "packet.json", "native.json", "device.json",
                "detector.json", "geometry.json", "source/map.json",
                "source/device.json", "source/detector.json", "source/blueprint.json")


def analyze_measurements(root):
    """Measure the six exact source requirements from hashed original packets."""
    root = Path(root).resolve()
    config = json.loads(_need(root, "config.json").read_text(encoding="utf-8"))
    site = json.loads(_need(root, "native-site.json").read_text(encoding="utf-8"))
    packet = json.loads(_need(root, "packet.json").read_text(encoding="utf-8"))
    case_id = config["selected_case_id"]
    if site.get("case_id") != case_id or packet.get("case_suffix") != config.get("case_suffix"):
        raise ValueError("Exact original case identity changed")
    if config.get("source_inventory") != list(SOURCE_NAMES):
        raise ValueError("Exact original source inventory changed")
    for name in SOURCE_NAMES:
        _need(root, name)
    trial = _load_trial()
    plan = trial.construct_plan(site, root, config["case_suffix"])
    measured = trial.measure_attempt(packet, root, plan)
    declared = [item["path"] for item in
                [site[key] for key in ("map_ref", "device_ref", "detector_ref", "blueprint_ref")] +
                [packet[key] for key in ("native_trace_ref", "device_trace_ref", "detector_trace_ref", "geometry_ref")]]
    if set(declared) != set(SOURCE_NAMES) - {"native-site.json", "packet.json"}:
        raise ValueError("Original source references differ from exact inventory")
    sources = {name: hashlib.sha256(_need(root, name).read_bytes()).hexdigest()
               for name in SOURCE_NAMES}
    return {"format": "worker-analysis-report", "case_id": case_id,
            "analysis_complete": True,
            "measurements": {key: {"method": method.__name__, "value": method(measured),
                                   "sources": sources} for key, method in ROWS},
            "measured_values": measured,
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False,
            "limitations": ["Original device causality, bicycle rider visibility and physical motion require independent review."]}


def finalize(root):
    """Build canonical Native result from saved originals, without verdicts."""
    root = Path(root).resolve()
    report = analyze_measurements(root)
    config = json.loads(_need(root, "config.json").read_text(encoding="utf-8"))
    packet = json.loads(_need(root, "packet.json").read_text(encoding="utf-8"))
    frames = packet["frames"]
    trace = [json.loads(line) for line in _need(root, "trace.jsonl").read_text().splitlines()]
    mapping = [json.loads(line) for line in _need(root, "video_frames.jsonl").read_text().splitlines()]
    if len(frames) != 900 or len(trace) != 900 or len(mapping) != 900:
        raise ValueError("Original Native/Core/four-camera 900-frame join missing")
    for index, (row, motion, video) in enumerate(zip(frames, trace, mapping)):
        if motion.get("frame") != row["frame"] or video.get("carla_frame") != row["frame"] or \
                video.get("video_frame") != index or abs(motion.get("time_s", -1) - row["timestamp_s"]) > 1e-6 or \
                abs(video.get("time_s", -1) - row["timestamp_s"]) > 1e-6:
            raise ValueError("Original Native/Core/four-camera frame join differs")
    cameras = ("overview", "approach", "reference_corner", "driver_reference")
    for name in cameras:
        _need(root, name + ".mkv")
    description = config["case"]["recording_description"]
    if len(description["channels"]) != 7 or len(description["context_inputs"]) != 1:
        raise ValueError("Selected recording description changed")
    channels = []
    for index, channel in enumerate(description["channels"]):
        path = root / ("recording-channel-" + str(index) + ".jsonl")
        path.write_text("".join(json.dumps({"time_s": row["timestamp_s"],
                                             "value": {"frame": row["frame"],
                                                       "source": channel["name"],
                                                       "readback": row}}) + "\n"
                                for row in frames), encoding="utf-8")
        channels.append({"name": channel["name"], "unit": channel["unit"],
                         "reference": path.name})
    context = description["context_inputs"][0]
    context_path = root / "recording-site-context.json"
    context_path.write_text(json.dumps({context["name"]: {"source_hashes": report["measurements"]["bicycle_actor"]["sources"]}}) + "\n")
    channels.append({"name": context["name"], "unit": context["unit"],
                     "reference": context_path.name})
    measured = report["measured_values"]
    targets = (("complete_device_cycles", {"one_cycle": 1, "three_cycles": 3}.get(config["case_suffix"], 2),
                measured["complete_device_cycles_before_entry"]),
               ("prior_stop", config["case_suffix"] != "no_prior_stop",
                measured["prior_stop_observed"]),
               ("detector_failure", config["case_suffix"] != "signal_changes",
                measured["detector_failure_observed"]),
               ("participant_conflict", config["case_suffix"] == "fails_to_yield",
                measured["conflict_at_entry"]))
    from worker_exchange.native_output import provenance_record, write_result
    provenance = provenance_record(root)
    result = {"case_id": report["case_id"], "measured_values": measured,
              "target_checks": [{"target": name, "requested": expected, "measured": actual,
                                  "method": "source-hashed original Native packet and frame join",
                                  "tolerance": 0, "matched": expected == actual,
                                  "physical_cause_confirmed": False,
                                  "cause_evidence": "independent original-source review pending"}
                                 for name, expected, actual in targets],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "source-only diagnostic finalization; physical completion unverified",
              "physical_failure_flags": ["physical_completion_unverified"],
              "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in cameras],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": channels,
              "realized_observables": {},
              "provenance_kind": provenance["provenance_kind"],
              "diagnostic_fixture": provenance["diagnostic_fixture"],
              "legal_verdict_claimed": False, "physical_acceptance_claimed": False}
    write_result(root, result)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = finalize(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError("Analysis output already exists")
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
