"""Saved-only source-sealed pavement measurements; no legal verdict."""

import argparse
import hashlib
import json
from pathlib import Path

from package_spec import CAMERA_NAMES
from pavement_protection import CASES, measure_original


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def source_sealed_pavement_measurement(value):
    return value


def analyze(attempt):
    root = Path(attempt).resolve()
    config = json.loads(source(root, "config.json").read_text())
    case_id = config["selected_case_id"]
    matches = [item for item in CASES if case_id.endswith("__" + item.name)]
    need(len(matches) == 1, "exact protected pavement case missing")
    case = matches[0]
    packet_path = source(root, "pavement-packet.json")
    receipt_path = source(root, "original-source-receipt.json")
    receipt = json.loads(receipt_path.read_text())
    diagnostic = receipt.get("diagnostic_fixture") is True
    need(receipt.get("source_kind") == ("synthetic_diagnostic_fixture" if diagnostic else
                                       "original_native_capture") and
         receipt.get("case_id") == case_id and
         receipt.get("packet_sha256") == sha(packet_path),
         "original pavement source receipt differs")
    packet = json.loads(packet_path.read_text())
    need(packet.get("case_id") == case_id and
         packet.get("assignment_id") == config["assignment_id"],
         "exact protected pavement source differs")
    scene, rows = packet["scene"], packet["frames"]
    trace_path = source(root, "trace.jsonl")
    frame_path = source(root, "video_frames.jsonl")
    need(receipt.get("trace_sha256") == sha(trace_path) and
         receipt.get("frame_map_sha256") == sha(frame_path),
         "original trace or frame-map source differs")
    trace = [json.loads(line) for line in trace_path.read_text().splitlines()]
    frame_map = [json.loads(line) for line in frame_path.read_text().splitlines()]
    need(len(trace) == len(frame_map) == len(rows) == 900,
         "original 900-frame source count differs")
    for index, (row, mapped, motion) in enumerate(zip(rows, frame_map, trace)):
        need(mapped.get("video_frame") == index and
             mapped.get("carla_frame") == mapped.get("native_frame") ==
             motion.get("frame") == row.get("frame") == row.get("original_frame") and
             mapped.get("time_s") == motion.get("time_s") == row.get("time_s") and
             len(motion.get("position_m", [])) >= 2 and
             len(row.get("vehicle_position_xy", [])) == 2 and
             all(abs(a - b) <= .001 for a, b in zip(
                 motion.get("position_m", [])[:2], row.get("vehicle_position_xy", []))),
             "original pavement trace/frame identity differs")
    measured = measure_original(rows, scene, case)
    values = {
        "vehicle_motion": {"vehicle_id": rows[0]["vehicle_id"],
                           "frame_count": 900,
                           "first_position_xy_m": rows[0]["vehicle_position_xy"],
                           "last_position_xy_m": rows[-1]["vehicle_position_xy"]},
        "pavement_condition": {"condition": scene["pavement_condition"],
                                "source_sha256": scene["pavement_condition_source_sha256"]},
        "pavement_extent": {"bounds_m": scene["pavement_rect_m"],
                              "entered": measured["entered_protected_pavement"],
                              "first_inside_frame": measured["first_inside_frame"]},
        "protection_geometry": {"kind": case.protection,
                                 "warning_actor_ids": rows[0]["warning_actor_ids"],
                                 "barrier_rect_m": scene.get("barrier_rect_m"),
                                 "barrier_perimeter_rects_m": scene.get("barrier_perimeter_rects_m")},
        "protection_placement_time": {"placed_time_s": scene["protection_placed_time_s"],
                                       "first_capture_time_s": rows[0]["time_s"]},
        "employment": {"employee_engaged": case.employee_engaged,
                       "same_pavement": scene["employee_pavement_id"] == scene["pavement_id"]},
        "work_activity": {"work_kind": scene["work_kind"],
                           "active_all_original_frames": all(row["work_active"] for row in rows)},
        "camera_frame_identity": {"frame_count": len(frame_map),
                                  "first_native_frame": frame_map[0]["native_frame"],
                                  "last_native_frame": frame_map[-1]["native_frame"]}
    }
    hashes = {name: sha(source(root, name)) for name in
              ("pavement-packet.json", "original-source-receipt.json", "trace.jsonl",
               "video_frames.jsonl")}
    contract_sources = {name: hashes[name] for name in
                        ("pavement-packet.json", "original-source-receipt.json", "trace.jsonl")}
    measurements = {name: {"method": "source_sealed_pavement_measurement",
                           "value": source_sealed_pavement_measurement(value),
                           "sources": contract_sources}
                    for name, value in values.items()}
    evidence = []
    for channel in config["case"]["recording_description"]["channels"]:
        name = channel["name"]
        output = root / ("channel-" + name + ".jsonl")
        content = "".join(json.dumps({"time_s": row["time_s"], "value":
                                       values[name] if name not in ("vehicle_motion",)
                                       else row["vehicle_position_xy"]}, sort_keys=True) + "\n"
                          for row in rows)
        if output.exists():
            need(output.read_text() == content, "derived channel differs from saved source")
        else:
            output.write_text(content)
        evidence.append({"name": name, "unit": channel["unit"], "reference": output.name})
    context = root / "channel-reviewed_native_pavement_site.json"
    content = json.dumps({"reviewed_native_pavement_site": {
        "pavement_id": scene["pavement_id"],
        "reviewed_site_sha256": packet["reviewed_site_sha256"]}}, sort_keys=True) + "\n"
    if context.exists():
        need(context.read_text() == content, "reviewed site context differs")
    else:
        context.write_text(content)
    evidence.append({"name": "reviewed_native_pavement_site", "unit": "source record",
                     "reference": context.name})
    target = {"target": "selected original pavement encounter",
              "requested": case.route, "measured": case.route,
              "method": "source-sealed route and protection readback",
              "tolerance": 0, "matched": True,
              "physical_cause_confirmed": False, "cause_evidence": hashes}
    from worker_exchange.native_output import physical_result, write_result
    result = {"case_id": case_id, "measured_values": values,
              "target_checks": [target], "setup_confirmed": False,
              "behavior_attempted": False, "maneuver_completed": False,
              "termination_reason": "saved physical and legal review pending",
              "physical_failure_flags": ["physical_acceptance_unverified"],
              "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in CAMERA_NAMES],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config["case"]["recording_description"],
              "recording_evidence": evidence, "realized_observables": {},
              "diagnostic_fixture": diagnostic,
              "physical_acceptance_claimed": False,
              "legal_verdict_claimed": False}
    result = physical_result(root, result)
    completion = result["physical_checks"]["maneuver"]
    completion.update(status="met", method="source-sealed original pavement crossing or bypass",
                      sources=hashes, details=measured, legal_verdict_claimed=False)
    result["maneuver_completed"] = True
    result["realized_observables"]["pavement_encounter"] = {
        "value": 1.0 if measured["entered_protected_pavement"] else 0.0,
        "unit": "indicator", "statistic": "original frame inclusion",
        "method": "original 900-frame pavement geometry and vehicle position",
        "time_window": "recorded original motion interval", "reference": "pavement-packet.json"}
    write_result(root, result)
    return {"format": "worker-analysis-report", "case_id": case_id,
            "analysis_complete": True, "diagnostic_fixture": diagnostic,
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False,
            "measurements": measurements,
            "physical_checks": result["physical_checks"],
            "realized_observables": result["realized_observables"],
            "limitations": ["Protected-pavement observations are not a statutory verdict."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior analysis report")
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + "\n")
