"""Source-bound saved measurements for the center turn lane rule.

This module reports observations and censoring, never a legal verdict.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from center_lane_measurement import measure_center_lane_distance
from center_lane_site import validate_site
from delivery_audit import audit_saved_delivery
from saved_finalizer import finalize_saved

SOURCES = ("original-attempt/native/capture-receipt.json",
           "original-attempt/native/site-packet.json",
           "original-attempt/native/trace.json")


def required(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + relative)
    return path


def bound(root, relative):
    path = required(root, relative)
    return json.loads(path.read_text())


def measure_lane_design(root, sources):
    site = validate_site(sources["site"])
    return {"center_lane_id": site["center_lane_id"],
            "receiving_lane_id": site["receiving_lane_id"],
            "opposing_lane_id": site["opposing_lane_id"],
            "reviewed_highway_source": site["highway_review_source"],
            "original_map_source": site["native_map_source"]}


def measure_turn_and_merge(root, sources):
    observed = sources["measured"]
    return {"turn_frame": observed["turn_frame"],
            "merge_frame": observed["merge_frame"],
            "merge_observed": observed["merge_observed"],
            "censored": observed["censored"]}


def measure_distance(root, sources):
    observed = sources["measured"]
    return {"distance_m": observed["distance_m"],
            "distance_ft": observed["distance_ft"],
            "measurement_convention": observed["measurement_convention"],
            "censored": observed["censored"]}


def finalize(root, expected_case):
    receipt = bound(root, SOURCES[0])
    site = bound(root, SOURCES[1])
    trace = bound(root, SOURCES[2])
    if receipt.get("case_id") != expected_case:
        raise ValueError("Original capture selects another exact case")
    if receipt.get("site_source", {}).get("sha256") != hashlib.sha256(required(root, SOURCES[1]).read_bytes()).hexdigest():
        raise ValueError("Original site source hash differs")
    if receipt.get("original_trace", {}).get("sha256") != hashlib.sha256(required(root, SOURCES[2]).read_bytes()).hexdigest():
        raise ValueError("Original trace source hash differs")
    provenance_path = Path(root) / "fixture-provenance.json"
    diagnostic = provenance_path.is_file() and json.loads(provenance_path.read_text()).get("diagnostic_fixture") is True
    original_root = Path(root) / "original-attempt"
    if diagnostic:
        audited = audit_saved_delivery(original_root, receipt)
        if audited["verified_frame_count"] != 900:
            raise ValueError("Diagnostic source requires 900 joined original frames")
    else:
        audited = finalize_saved(original_root, expected_case, 900)
        if audited["decoded_camera_images"] != 3600:
            raise ValueError("Original camera decode incomplete")
    measured = measure_center_lane_distance(trace)
    if diagnostic and audited["measured"] != measured:
        raise ValueError("Diagnostic saved trace differs from selected measurement")
    if measured != receipt.get("delivered_measurement"):
        raise ValueError("Delivered measurement differs from original trace")
    if expected_case.endswith("__no_merge") != measured["censored"]:
        raise ValueError("Exact merge/censor branch differs from original trace")
    sources = {"receipt": receipt, "site": site, "trace": trace, "measured": measured}
    rows = (("observed_lane_design", measure_lane_design, (SOURCES[0], SOURCES[1])),
            ("observed_turn_and_merge", measure_turn_and_merge, (SOURCES[0], SOURCES[2])),
            ("observed_center_lane_travel", measure_distance, (SOURCES[0], SOURCES[2])))
    values = {}
    for name, method, names in rows:
        values[name] = {"method": method.__name__, "value": method(root, sources),
                        "sources": {name: hashlib.sha256(required(root, name).read_bytes()).hexdigest() for name in names}}
    return {"format": "worker-analysis-report", "case_id": expected_case,
            "measurements": values, "legal_judgment": None,
            "physical_acceptance": None, "analysis_complete": True,
            "limitations": ["Public highway and lane dedication require original independent review.",
                            "The no-merge observation is censored, not a distance to merge."]}


def recording_evidence(root, description):
    """Project original trace and camera joins into the declared channels."""
    root = Path(root)
    trace = bound(root, SOURCES[2])
    site = bound(root, SOURCES[1])
    frame_map = bound(root, "original-attempt/native/frame_map.json")
    rows, maps = trace["samples"], frame_map["frames"]
    if len(rows) != 900 or len(maps) != 900 or [r["frame"] for r in rows] != [m["frame"] for m in maps]:
        raise ValueError("Original trace/camera map requires 900 joined frames")
    values = {
        "public_highway_context": lambda r, m: {"source": site["highway_review_source"],
                                                   "public_highway_confirmed": site["public_highway_confirmed"]},
        "center_turn_lane_design": lambda r, m: {"source": site["native_map_source"], "lane_id": r["lane_id"]},
        "turn_completion_event": lambda r, m: {"observed": r["left_turn_onto_highway_complete"], "frame": r["frame"]},
        "center_lane_body_history": lambda r, m: {"body_centre_xy_m": r["body_centre_xy_m"], "lane_id": r["lane_id"]},
        "through_lane_merge_event": lambda r, m: {"observed": r["merged_into_through_lane"], "frame": r["frame"]},
        "receiving_vehicle_history": lambda r, m: {"actor_id": r.get("receiving_vehicle_actor_id"),
                                                    "frame": r["frame"], "source_state": "original_trace"},
        "frame_and_camera_join": lambda r, m: {"frame": r["frame"], "camera_sources": m["camera_sources"]},
    }
    (root / "channels").mkdir(exist_ok=True)
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        if name not in values:
            raise ValueError("Unknown selected channel: " + name)
        reference = "channels/" + name + ".jsonl"
        with (root / reference).open("x") as stream:
            for index, (row, mapping) in enumerate(zip(rows, maps)):
                stream.write(json.dumps({"time_s": index / 20, "value": values[name](row, mapping)},
                                        allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": channel["unit"], "reference": reference})
    contexts = {
        "reviewed_highway_and_lane_site": {"site_source": SOURCES[1],
                                           "native_map_source": site["native_map_source"],
                                           "highway_review_source": site["highway_review_source"]},
        "reviewed_actor_and_route": {"entry_maneuver": site["entry_maneuver"],
                                     "entry_target_lane_id": site["entry_target_lane_id"],
                                     "merge_target_lane_id": site["merge_target_lane_id"]},
    }
    for context in description["context_inputs"]:
        name = context["name"]
        reference = "channels/" + name + ".json"
        (root / reference).write_text(json.dumps({name: contexts[name]}, allow_nan=False) + "\n")
        evidence.append({"name": name, "unit": context["unit"], "reference": reference})
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(required(args.attempt, "config.json").read_text())
    report = finalize(args.attempt, config["selected_case_id"])
    from worker_exchange.native_output import physical_result, validate_result
    observed = report["measurements"]["observed_center_lane_travel"]["value"]
    target = config["authored_target_distance_ft"]
    if target is None:
        check = {"target": "observed_merge", "requested": False,
                 "measured": not observed["censored"], "method": "original merge event and censoring",
                 "tolerance": 0, "matched": observed["censored"],
                 "physical_cause_confirmed": False,
                 "cause_evidence": "No-merge interval censored; original physical cause unreviewed"}
    else:
        measured = observed["distance_ft"]
        check = {"target": "authored_center_lane_distance_ft", "requested": target,
                 "measured": measured, "method": "original post-turn body-centre sampled path",
                 "tolerance": 0.5, "matched": abs(measured - target) <= 0.5,
                 "physical_cause_confirmed": False,
                 "cause_evidence": "Numeric probe is an engineering request; original cause unreviewed"}
    result = physical_result(args.attempt, {
        "case_id": config["selected_case_id"],
        "measured_values": {key: value["value"] for key, value in report["measurements"].items()},
        "target_checks": [check], "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False, "termination_reason": "Saved original source analyzed",
        "physical_failure_flags": {}, "trace_reference": "trace.jsonl",
        "video_references": ["raw.mkv"], "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": recording_evidence(args.attempt, config["recording_description"]),
        "realized_observables": {}})
    validate_result(result)
    (args.attempt / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    args.output.write_text(json.dumps(report, indent=2) + "\n")

if __name__ == "__main__":
    main()
