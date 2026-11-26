"""Saved-only door observations for the exact selected NRS 484B.153(2) case.

The diagnostic input is synthetic. A Native input must retain the same
source joins and cannot inherit a legal conclusion from this finalizer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from delivery_measure import measure, _outline_gap


INPUTS = ("door-source.json", "native-trace.json")


def source(root: Path, name: str) -> tuple[dict, str]:
    path = root / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def original_measurement(root: Path) -> tuple[dict, dict]:
    intent, intent_sha = source(root, "door-source.json")
    trace, trace_sha = source(root, "native-trace.json")
    if intent.get("source_trace_sha256") != trace_sha:
        raise ValueError("Original door source does not bind this Native trace")
    result = measure(trace, expected_case_id=intent["case_id"],
                     expected_act=intent["selected_act"],
                     expected_side=intent["selected_side"])
    return result, {"door-source.json": intent_sha, "native-trace.json": trace_sha}


def measure_observed_action(root: Path) -> dict:
    observed, sources = original_measurement(root)
    return {"method": "measure_observed_action", "sources": sources,
            "value": {"act": observed["observed_act"],
                      "side": observed["act_side"],
                      "frame_ids": observed["act_frame_ids"]}}


def measure_closest_side(root: Path) -> dict:
    observed, sources = original_measurement(root)
    return {"method": "measure_closest_side", "sources": sources,
            "value": {"act_side": observed["act_side"],
                      "passing_side": observed["passing_side"],
                      "same_side": observed["act_on_closest_side"]}}


def measure_moving_interaction(root: Path) -> dict:
    observed, sources = original_measurement(root)
    return {"method": "measure_moving_interaction", "sources": sources,
            "value": {"moving_frame_ids": observed["moving_frame_ids"],
                      "body_gap_by_frame_m": observed["body_gap_by_frame_m"],
                      "minimum_body_gap_m": observed["minimum_body_gap_m"],
                      "passing_response": observed["passing_response"],
                      "legal_interference": "unresolved_judgment"}}


def native_result(root: Path, observed: dict) -> dict:
    construction = json.loads((root / "construction.json").read_text())
    description = construction["recording_description"]
    trace = json.loads((root / "native-trace.json").read_text())
    frames = trace["frames"]
    context, _ = source(root, "door-source.json")
    projections = {
        "original_interaction": lambda r: {"act": r["observed_act"],
                                            "passing_center_xy": r["passing_center_xy"]},
        "observed_driver_act": lambda r: {"act": r["observed_act"],
                                          "side": r.get("act_side"),
                                          "driver_id": r["selected_driver_id"]},
        "door_envelope_xy": lambda r: {"vertices": r.get("act_envelope_xy")},
        "passing_body_xy": lambda r: {"vertices": r["passing_body_xy"]},
        "passing_speed_mps": lambda r: r["passing_speed_mps"],
        "passing_response": lambda r: r["passing_response"],
        "camera_frame_join": lambda r: {"frame_ids": r["camera_frames"],
                                          "pixel_sha256": r["camera_sha256"]},
        "hill_crest_loading_site": lambda r: context.get("site_survey", {}),
        "parked_vehicle_pose": lambda r: {
            "center_xy": trace["parked_center_xy"],
            "heading_xy": trace["parked_heading_xy"],
            "position_m": r.get("parked_position_m")},
        "driver_act_and_side": lambda r: {"act": r["observed_act"],
                                          "side": r.get("act_side"),
                                          "driver_id": r["selected_driver_id"]},
        "door_vertices": lambda r: {"vertices_xy": r.get("act_envelope_xy")},
        "passing_traffic_body": lambda r: {"vertices_xy": r["passing_body_xy"],
                                           "speed_mps": r["passing_speed_mps"]},
        "traffic_response": lambda r: r["passing_response"],
        "camera_frame_map": lambda r: {"frame_ids": r["camera_frames"],
                                       "pixel_sha256": r["camera_sha256"]},
        "door_body_clearance_m": lambda r: _outline_gap(
            r["act_envelope_xy"], r["passing_body_xy"]),
    }
    channels = root / "channels"
    channels.mkdir(exist_ok=False)
    evidence = []
    for item in description["channels"]:
        name = item["name"]
        if name not in projections:
            raise ValueError("selected channel lacks original projection: " + name)
        relative = "channels/" + name + ".jsonl"
        with (root / relative).open("x") as output:
            for row in frames:
                output.write(json.dumps({"time_s": row["sim_time_s"],
                                         "value": projections[name](row)},
                                        separators=(",", ":"), allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": item["unit"], "reference": relative})
    for item in description["context_inputs"]:
        if item["name"] != "hill_crest_loading_site":
            raise ValueError("unknown selected site context")
        relative = "channels/hill_crest_loading_site.json"
        (root / relative).write_text(json.dumps({item["name"]: context},
                                                separators=(",", ":")) + "\n")
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": relative})
    realized = {}
    if any(item["name"] == "door_body_clearance_m" for item in description["channels"]):
        best = min(observed["body_gap_by_frame_m"], key=lambda row: row["body_gap_m"])
        frame = next(row for row in frames if row["frame_id"] == best["frame_id"])
        realized["door_body_clearance_m"] = {
            "value": best["body_gap_m"], "unit": "m",
            "method": "same-frame original door and moving-body polygon distance",
            "time_window": "minimum-gap original act and moving-traffic overlap frame",
            "statistic": "min", "sample_window_s": [frame["sim_time_s"], frame["sim_time_s"]],
            "reference": "channels/door_body_clearance_m.jsonl"}
    return {"case_id": observed["case_id"], "measured_values": observed,
            "target_checks": [{"target": "original door and moving-traffic source join",
                               "requested": True, "measured": True,
                               "method": "original_measurement", "tolerance": 0,
                               "matched": True, "physical_cause_confirmed": False,
                               "cause_evidence": ["native-trace.json", "door-source.json"]}],
            "setup_confirmed": False, "behavior_attempted": False,
            "maneuver_completed": False,
            "termination_reason": "Saved source measurement; physical review pending",
            "physical_failure_flags": [], "trace_reference": "trace.jsonl",
            "video_references": [name + ".mkv" for name in
                                 ("overview", "approach", "reference_corner", "driver_reference")],
            "video_frame_map_reference": "video_frames.jsonl",
            "recording_description": description, "recording_evidence": evidence,
            "realized_observables": realized}


def analyze(root: Path, output: Path, report_only: bool = False) -> dict:
    root = Path(root)
    observed, _ = original_measurement(root)
    measurements = {"observed_action": measure_observed_action(root),
                    "closest_side": measure_closest_side(root),
                    "moving_interaction": measure_moving_interaction(root)}
    report = {"format": "worker-analysis-report", "case_id": observed["case_id"],
              "measurements": measurements,
              "limitations": ["Physical visibility and legal interference require independent review."]}
    if not report_only:
        (root / "result.json").write_text(json.dumps(native_result(root, observed),
                                                   indent=2, allow_nan=False) + "\n")
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    analyze(args.attempt, args.output, args.report_only)


if __name__ == "__main__":
    main()
