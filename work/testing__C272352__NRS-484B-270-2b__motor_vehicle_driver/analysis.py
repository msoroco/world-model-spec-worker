"""Saved source-bound NRS 484B.270(2)(b) measurements, without legal verdict."""

import argparse
import hashlib
import json
from pathlib import Path

from passing_probe import measure_pass


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def required(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def measure_activation(observed, context, case, rows):
    return {"qualifying_kind": context["bicycle_kind"],
            "participant_ids": [context["vehicle_id"], context["bicycle_id"]],
            "first_frame": rows[0]["frame"],
            "passing_frames": observed["passing_original_frames"]}


def measure_due_care_sources(observed, context, case, rows):
    return {"motor_vehicle_speed_mps": [row["vehicle_speed_mps"] for row in rows],
            "qualifying_rider_speed_mps": [row["bicycle_speed_mps"] for row in rows],
            "sampled_original_frames": [row["frame"] for row in rows],
            "legal_due_care": None}


def measure_one_lane(observed, context, case, rows):
    return {"same_direction_lane_count": context["lane_count_same_direction"],
            "highway_source": context["highway_source"],
            "centerline_y": context["centerline_y"]}


def measure_left_clearance(observed, context, case, rows):
    return {"minimum_body_gap_m": observed["minimum_body_gap_m"],
            "three_foot_floor_observed": observed["three_foot_floor_observed"],
            "left_during_overlap": observed["left_during_overlap"],
            "legal_safe_distance": None}


def measure_return_order(observed, context, case, rows):
    return {"first_return_original_frame": observed["first_return_original_frame"],
            "longitudinal_clear_before_return": observed["longitudinal_clear_before_return"],
            "legal_safely_clear": None}


def measure_special_authorization(observed, context, case, rows):
    return {"route_request": case["route_request"],
            "reviewed_packet_sha256": context["reviewed_packet_sha256"],
            "centerline_source": context["centerline_source"],
            "zone_source": context["zone_source"],
            "exception_213_217_source": context["exception_213_217_source"],
            "observed_centerline_crossing_frames": [row["frame"] for row in rows
                                                    if row["vehicle_box"][3] > context["centerline_y"]],
            "opposing_traffic_sources": [row.get("opposing_traffic_source") for row in rows],
            "incorporated_exceptions": None, "legal_safety": None}


METHODS = (measure_activation, measure_due_care_sources, measure_one_lane,
           measure_left_clearance, measure_return_order,
           measure_special_authorization)
KEYS = ("activation", "due_care_sources", "one_lane", "left_clearance",
        "return_order", "special_authorization")


def analyze(attempt):
    root = Path(attempt).resolve()
    config = json.loads(required(root, "config.json").read_text(encoding="utf-8"))
    case = config["case"]
    context_path = required(root, "original-context.json")
    trace_path = required(root, "original-trace.jsonl")
    receipt_path = required(root, "original-source-receipt.json")
    mapping_path = required(root, "video_frames.jsonl")
    context = json.loads(context_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    diagnostic = receipt.get("diagnostic_fixture") is True
    if receipt.get("source_kind") != ("synthetic_diagnostic_fixture" if diagnostic else
                                      "original_native_capture"):
        raise ValueError("original source provenance mismatch")
    if context.get("case_id") != case["case_id"] or receipt.get("case_id") != case["case_id"] or \
            context.get("bicycle_kind") != case["control_kind"]:
        raise ValueError("exact saved case/source mismatch")
    if sha(context_path) != receipt.get("context_sha256") or \
            sha(trace_path) != receipt.get("trace_sha256"):
        raise ValueError("saved original context/trace source changed")
    if len(mapping_path.read_text(encoding="utf-8").splitlines()) != receipt["frame_count"]:
        raise ValueError("saved original frame map incomplete")
    rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    if len(rows) != receipt["frame_count"]:
        raise ValueError("saved original body history incomplete")
    frames = [{"original_frame": row["frame"], **row} for row in rows]
    site = {key: context[key] for key in ("highway_source", "lane_count_same_direction",
            "centerline_y", "right_side_y", "vehicle_id", "bicycle_id", "bicycle_kind")}
    observed = measure_pass(site, frames)
    sources = {name: sha(root / name) for name in
               ("original-context.json", "original-trace.jsonl",
                "original-source-receipt.json", "video_frames.jsonl")}
    if context.get("reviewed_packet_sha256") != receipt.get("reviewed_packet_sha256"):
        raise ValueError("reviewed Native site packet binding changed")
    values = {
        "body_envelopes": lambda row: {"vehicle_box": row["vehicle_box"],
                                       "bicycle_box": row["bicycle_box"]},
        "passing_clearance": lambda row: {"minimum_body_gap_m": observed["minimum_body_gap_m"],
                                           "three_foot_floor_observed": observed["three_foot_floor_observed"]},
        "return_order": lambda row: {"first_return_original_frame": observed["first_return_original_frame"],
                                      "longitudinal_clear_before_return": observed["longitudinal_clear_before_return"]},
        "lane_controls": lambda row: {"same_direction_lane_count": 1,
                                       "centerline_y": context["centerline_y"],
                                       "right_side_y": context["right_side_y"]},
        "opposing_traffic": lambda row: {"source": row.get("opposing_traffic_source")},
    }
    evidence = []
    for channel in case["recording_description"]["channels"]:
        name = channel["name"]
        if name == "camera_identity":
            data = "".join(json.dumps({"time_s": item["time_s"],
                                       "value": {"frame": item["carla_frame"]}}) + "\n"
                           for item in (json.loads(line) for line in
                                        mapping_path.read_text(encoding="utf-8").splitlines()))
        else:
            if name not in values:
                raise ValueError("unknown passing measurement channel: " + name)
            data = "".join(json.dumps({"time_s": row["time_s"],
                                       "value": values[name](row)}) + "\n" for row in rows)
        target = root / ("channel-" + name + ".jsonl")
        if target.exists() and target.read_text(encoding="utf-8") != data:
            raise ValueError("derived channel differs from original replay")
        if not target.exists():
            target.write_text(data, encoding="utf-8")
        evidence.append({"name": name, "unit": channel["unit"], "reference": target.name})
    context_channel = root / "channel-reviewed_native_site_packet.json"
    data = json.dumps({"reviewed_native_site_packet": receipt["reviewed_packet_sha256"],
                       "reviewed_packet_sha256": receipt["reviewed_packet_sha256"],
                       "context_sha256": sources["original-context.json"]}, sort_keys=True) + "\n"
    if context_channel.exists() and context_channel.read_text(encoding="utf-8") != data:
        raise ValueError("derived site context differs from original replay")
    if not context_channel.exists():
        context_channel.write_text(data, encoding="utf-8")
    evidence.append({"name": "reviewed_native_site_packet", "unit": "source record",
                     "reference": context_channel.name})
    requested = {"target_clearance_m": case["target_clearance_m"],
                 "return_after_clear": case["return_request"] != "early"}
    measured = {"minimum_body_gap_m": observed["minimum_body_gap_m"],
                "return_after_clear": observed["longitudinal_clear_before_return"]}
    check = {"target": "original requested pass clearance and return ordering",
             "requested": requested, "measured": measured,
             "method": "source-sealed original body-envelope and frame-order history",
             "tolerance": 0.05,
             "matched": abs(measured["minimum_body_gap_m"] - requested["target_clearance_m"]) <= .05 and
             measured["return_after_clear"] == requested["return_after_clear"],
             "physical_cause_confirmed": False, "cause_evidence": sources}
    from worker_exchange.native_output import physical_result, write_result
    result = {"case_id": case["case_id"], "measured_values": observed,
              "target_checks": [check], "setup_confirmed": False,
              "behavior_attempted": False, "maneuver_completed": False,
              "termination_reason": "saved source assessment; physical and legal review pending",
              "physical_failure_flags": ["physical_acceptance_unverified"],
              "trace_reference": "trace.jsonl", "video_references": [name + ".mkv" for name in CAMERAS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": case["recording_description"],
              "recording_evidence": evidence, "realized_observables": {},
              "diagnostic_fixture": diagnostic, "physical_acceptance_claimed": False,
              "legal_verdict_claimed": False}
    result = physical_result(root, result)
    write_result(root, result)
    measurements = {key: {"method": method.__name__,
                          "value": method(observed, context, case, rows),
                          "sources": sources}
                    for key, method in zip(KEYS, METHODS)}
    return {"format": "worker-analysis-report", "case_id": case["case_id"],
            "analysis_complete": True, "diagnostic_fixture": diagnostic,
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False,
            "measurements": measurements,
            "physical_checks": result["physical_checks"],
            "realized_observables": result["realized_observables"],
            "limitations": ["Original measurements do not decide due care, safe distance, safely clear or incorporated exceptions."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior analysis report")
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + "\n",
                           encoding="utf-8")
