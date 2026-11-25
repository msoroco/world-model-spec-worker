"""Saved-only projection of sealed original Native intersection observations.

This report carries raw geometric and motion measurements. It makes no legal
immediate-hazard, cautiousness, right-of-way or physical-visibility claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_witness import measure
from original_camera_recorder import VIEWS


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _original(attempt, name, inventory):
    item = inventory.get(name)
    path = attempt / name
    if not isinstance(item, dict) or item.get("kind") != "original_native" or not path.is_file():
        raise ValueError("Missing required source: " + name)
    if item.get("sha256") != _sha(path):
        raise ValueError("stale original Native source: " + name)
    return path


def measure_stop_yield(value, context):
    return {"control_context": context, "entry_frame": value["entry_frame"],
            "pre_entry_stop_required": context == "stop_sign",
            "observed_cautiousness_verdict": None}


def measure_priority_within(value):
    return {"counterpart_within_frames": value["counterpart_within_frames"],
            "priority_verdict": None}


def measure_approaching(value):
    return {"counterpart_relation_observed": value["counterpart_relation_observed"],
            "counterpart_center_station_at_entry_m": value["counterpart_center_station_at_entry_m"],
            "minimum_center_distance_m": value["minimum_center_distance_m"],
            "immediate_hazard_verdict": None}


def measure_signal_exception(value, context):
    return {"controlling_signal_observed": context == "signal_exception",
            "intersection_entry_frame": value["entry_frame"]}


def measure_officer_exception(value, context):
    return {"controlling_officer_observed": context == "officer_exception",
            "intersection_entry_frame": value["entry_frame"]}


def measure_subsection_one(value, context):
    return {"context": context, "entry_frame": value["entry_frame"],
            "cross_reference_legal_verdict": None}


def analyze(attempt):
    attempt = Path(attempt).resolve()
    config = json.loads((attempt / "config.json").read_text())
    selected = config.get("selected_case_id")
    cases = {item["case_id"]: item for item in json.loads(
        Path(__file__).with_name("case-specs.json").read_text())["cases"]}
    if selected not in cases:
        raise ValueError("selected exact case absent from source-bound plan")
    spec = cases[selected]
    inventory = json.loads((attempt / "acquisition.json").read_text())
    history_path = _original(attempt, "original-history.json", inventory)
    frame_map_path = _original(attempt, "video_frames.jsonl", inventory)
    site_path = _original(attempt, "site.json", inventory)
    devices_path = _original(attempt, "devices.json", inventory)
    routes_path = _original(attempt, "routes.json", inventory)
    packet = json.loads(history_path.read_text())
    if packet.get("case_id") != selected or packet.get("control_context") != spec["control_context"]:
        raise ValueError("original history differs from selected exact case")
    frames = [json.loads(line) for line in frame_map_path.read_text().splitlines() if line.strip()]
    if len(frames) != 900 or len(packet.get("frames", [])) != 900:
        raise ValueError("full original frame inventory required")
    for i, (row, sample) in enumerate(zip(frames, packet["frames"])):
        if (row.get("video_frame") != i or row.get("carla_frame") != sample.get("native_frame") or
                abs(row.get("time_s", -1) - sample.get("time_s", -2)) > .001):
            raise ValueError("original Native/video frame join differs")
    measured = measure(packet, spec["control_context"], spec["counterpart_relation"])
    if (packet["intersection_rectangle_xy"] !=
            json.loads(site_path.read_text()).get("intersection_rectangle_xy") or
            json.loads(devices_path.read_text()).get("control_context") != spec["control_context"] or
            json.loads(routes_path.read_text()).get("case_id") != selected):
        raise ValueError("original site/device/route context differs")
    sources = {name: _sha(attempt / name) for name in
               ("original-history.json", "video_frames.jsonl", "site.json",
                "devices.json", "routes.json")}
    def item(value, method):
        return {"value": value, "method": method, "sources": sources}
    return {
        "format": "worker-analysis-report",
        "case_id": selected,
        "measurements": {
            "intersection_approach": item(measured, "measure"),
            "stop_yield_observation": item(measure_stop_yield(measured, spec["control_context"]), "measure_stop_yield"),
            "priority_within_observation": item(measure_priority_within(measured), "measure_priority_within"),
            "approaching_observation": item(measure_approaching(measured), "measure_approaching"),
            "signal_exception_observation": item(measure_signal_exception(measured, spec["control_context"]), "measure_signal_exception"),
            "officer_exception_observation": item(measure_officer_exception(measured, spec["control_context"]), "measure_officer_exception"),
            "subsection_one_observation": item(measure_subsection_one(measured, spec["control_context"]), "measure_subsection_one")},
        "analysis_complete": True,
        "legal_verdict_claimed": False,
        "physical_acceptance_claimed": False,
        "limitations": [
            "Immediate hazard and due caution require independent original-source review.",
            "Actual pixels and physical completion require separate original media and motion audits."
        ]}


def saved_result(attempt, report):
    from worker_exchange.native_output import physical_result, write_result
    attempt = Path(attempt).resolve()
    config = json.loads((attempt / "config.json").read_text())
    planned = config["case"]["recording_description"]
    packet = json.loads((attempt / "original-history.json").read_text())
    frames = packet["frames"]
    frame_map = [json.loads(line) for line in (attempt / "video_frames.jsonl").read_text().splitlines() if line.strip()]
    values = {
        "native_device_history": [row["authority"] for row in frames],
        "ego_body_history": [row["ego"] for row in frames],
        "counterpart_body_history": [row["counterpart"] for row in frames],
        "intersection_geometry": [packet["intersection_rectangle_xy"]] * len(frames),
        "camera_frame_map": frame_map}
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    evidence = []
    for channel in planned["channels"]:
        name = channel["name"]
        path = channels / (name + ".jsonl")
        with path.open("x") as stream:
            for frame, value in zip(frames, values[name]):
                stream.write(json.dumps({"time_s": frame["time_s"], "value": value},
                                        allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(path.relative_to(attempt))})
    context = channels / "context.json"
    context.write_text(json.dumps({"original_authority_context": {
        "devices_sha256": _sha(attempt / "devices.json"), "site_sha256": _sha(attempt / "site.json")},
        "counterpart_priority_context": {
            "routes_sha256": _sha(attempt / "routes.json"), "legal_priority_verdict": None}},
        allow_nan=False) + "\n")
    for channel in planned["context_inputs"]:
        evidence.append({"name": channel["name"], "unit": channel["unit"],
                         "reference": str(context.relative_to(attempt))})
    rectangle = packet["intersection_rectangle_xy"]
    left, bottom, right, top = rectangle
    (attempt / "control_context.json").write_text(json.dumps({
        "intersection_polygon_xy_m": [[left, bottom], [right, bottom],
                                       [right, top], [left, top]],
        "source_hashes": {"site.json": _sha(attempt / "site.json"),
                          "devices.json": _sha(attempt / "devices.json")}},
        allow_nan=False) + "\n")
    with (attempt / "interaction_history.jsonl").open("x") as motion:
        for frame in frames:
            motion.write(json.dumps({"frame": frame["native_frame"],
                                     "time_s": frame["time_s"],
                                     "ego": {"body_vertices_m": frame["ego"]["body_vertices_xy"]},
                                     "counterpart": {"body_vertices_m": frame["counterpart"]["body_vertices_xy"]}},
                                    allow_nan=False) + "\n")
    measurement = report["measurements"]["intersection_approach"]["value"]
    result = {"case_id": config["selected_case_id"],
              "measured_values": measurement,
              "target_checks": [{"target": "original sign/authority and intersection passage",
                                 "requested": True, "measured": True,
                                 "method": "measure", "tolerance": 0,
                                 "matched": True, "physical_cause_confirmed": False,
                                 "cause_evidence": report["measurements"]["intersection_approach"]["sources"]}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "Saved evidence measured; independent physical review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in VIEWS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": planned,
              "recording_evidence": evidence, "realized_observables": {}}
    result = physical_result(attempt, result)
    write_result(attempt, result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    result = saved_result(args.attempt, report)
    report["physical_checks"] = result["physical_checks"]
    report["realized_observables"] = result["realized_observables"]
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
