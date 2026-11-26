"""Saved-only school-bus speed and pupil-transport observations."""

import argparse
import hashlib
import json
from pathlib import Path

from package_spec import CAMERA_NAMES


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


def source_sealed_school_bus_measurement(value):
    return value


def analyze(attempt):
    root = Path(attempt).resolve()
    config = json.loads(source(root, "config.json").read_text())
    case = config["selected_case_id"]
    receipt = json.loads(source(root, "original-source-receipt.json").read_text())
    diagnostic = receipt.get("diagnostic_fixture") is True
    need(receipt.get("source_kind") == ("synthetic_diagnostic_fixture" if diagnostic else "original_native_capture") and receipt.get("case_id") == case,
         "exact original/diagnostic source receipt differs")
    history_path = source(root, "school-bus-history.json")
    trace_path = source(root, "trace.jsonl")
    frame_path = source(root, "video_frames.jsonl")
    measurement_path = source(root, "school-bus-measurement.json")
    for key, path in (("history_sha256", history_path), ("trace_sha256", trace_path),
                      ("frame_map_sha256", frame_path), ("measurement_sha256", measurement_path)):
        need(receipt.get(key) == sha(path), "sealed school-bus source differs: " + key)
    history = json.loads(history_path.read_text())
    rows = history["samples"]
    trace = [json.loads(line) for line in trace_path.read_text().splitlines()]
    frame_map = [json.loads(line) for line in frame_path.read_text().splitlines()]
    need(history.get("assignment_id") == config["assignment_id"] and history.get("case_id") == case and len(rows) == len(trace) == len(frame_map) and len(rows) >= 3,
         "school-bus source row identity/count differs")
    for index, (row, mapped, motion) in enumerate(zip(rows, frame_map, trace)):
        need(row["frame"] == mapped["video_frame"] == index and mapped["native_frame"] == mapped["carla_frame"] == motion["frame"] == row["native_frame"] and
             row["time_s"] == mapped["time_s"] == motion["time_s"] and abs(motion["speed_mps"] - row["bus_speed_mps"]) < 1e-6,
             "source frame, trace or bus speed differs")
        need(type(row.get("transporting_pupils_to_or_from_school")) is bool, "source transport phase missing")
    active = [row["bus_speed_mps"] * 2.2369362920544 for row in rows if row["transporting_pupils_to_or_from_school"]]
    values = {
        "school_bus_classification": history["school_bus_classification"],
        "driver_and_bus_identity": {"driver_actor_id": history["driver_actor_id"], "bus_actor_id": history["bus_actor_id"]},
        "pupil_transport_phase": {"direction": history["transport_direction"], "source": history["transport_source"],
                                  "active_frame_count": len(active)},
        "pupil_presence_count": {"count": history["pupil_count"], "source": history["pupil_presence_source"]},
        "bus_speed": {"maximum_active_mph": max(active, default=None),
                      "maximum_all_mph": max(row["bus_speed_mps"] * 2.2369362920544 for row in rows)},
        "bus_route_position": {"first_position_m": trace[0]["position_m"], "last_position_m": trace[-1]["position_m"]},
        "sidewalk_relation": {"source": history["sidewalk_source"]}}
    contract_sources = {name: sha(source(root, name)) for name in
                        ("school-bus-history.json", "original-source-receipt.json", "trace.jsonl")}
    measurements = {name: {"method": "source_sealed_school_bus_measurement", "value": source_sealed_school_bus_measurement(value),
                           "sources": contract_sources} for name, value in values.items()}
    evidence = []
    for channel in config["case"]["recording_description"]["channels"]:
        name = channel["name"]
        output = root / ("channel-" + name + ".jsonl")
        content = "".join(json.dumps({"time_s": row["time_s"], "value":
                                      row["bus_speed_mps"] * 2.2369362920544 if name == "bus_speed" else
                                      row["transporting_pupils_to_or_from_school"] if name == "pupil_transport_phase" else
                                      row["bus_position_xyz_m"] if name == "bus_route_position" else values[name]}, sort_keys=True) + "\n"
                          for row in rows)
        if output.exists():
            need(output.read_text() == content, "derived channel differs from saved source")
        else:
            output.write_text(content)
        evidence.append({"name": name, "unit": channel["unit"], "reference": output.name})
    context = root / "channel-reviewed_school_bus_trip.json"
    content = json.dumps({"reviewed_school_bus_trip": {"reviewed_site_sha256": history["reviewed_site_sha256"],
                                                     "transport_source": history["transport_source"],
                                                     "sidewalk_source": history["sidewalk_source"]}}, sort_keys=True) + "\n"
    if context.exists():
        need(context.read_text() == content, "reviewed bus trip context differs")
    else:
        context.write_text(content)
    evidence.append({"name": "reviewed_school_bus_trip", "unit": "source record", "reference": context.name})
    target = {"target": "source-specified school-bus speed interval",
              "requested": config["case"]["target_speed_mph"],
              "measured": values["bus_speed"]["maximum_all_mph"],
              "method": "original Native bus velocity norm and source-joined trip phase",
              "tolerance": 1.0,
              "matched": abs(values["bus_speed"]["maximum_all_mph"] - config["case"]["target_speed_mph"]) <= 1.0,
              "physical_cause_confirmed": False, "cause_evidence": contract_sources}
    from worker_exchange.native_output import physical_result, write_result
    result = {"case_id": case, "measured_values": values, "target_checks": [target],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False, "termination_reason": "saved physical and source review pending",
              "physical_failure_flags": ["physical_acceptance_unverified"],
              "trace_reference": "trace.jsonl", "video_references": [name + ".mkv" for name in CAMERA_NAMES],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config["case"]["recording_description"],
              "recording_evidence": evidence, "realized_observables": {},
              "diagnostic_fixture": diagnostic, "physical_acceptance_claimed": False,
              "legal_verdict_claimed": False}
    result = physical_result(root, result)
    write_result(root, result)
    return {"format": "worker-analysis-report", "case_id": case,
            "analysis_complete": True, "diagnostic_fixture": diagnostic,
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False,
            "measurements": measurements, "physical_checks": result["physical_checks"],
            "realized_observables": result["realized_observables"],
            "limitations": ["School-bus definition, pupil transport and any legal result require independent review."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior analysis report")
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + "\n")
