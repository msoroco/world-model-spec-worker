"""Saved-only barrier and driving observations without an imprudence verdict."""

import argparse
import hashlib
import json
from pathlib import Path

from barrier_route import measure
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


def source_sealed_barrier_measurement(value):
    return value


def analyze(attempt):
    root = Path(attempt).resolve()
    config = json.loads(source(root, "config.json").read_text())
    case = config["selected_case_id"]
    profile = case.removeprefix(config["assignment_id"] + "__")
    packet_path = source(root, "barrier-packet.json")
    receipt_path = source(root, "original-source-receipt.json")
    receipt = json.loads(receipt_path.read_text())
    diagnostic = receipt.get("diagnostic_fixture") is True
    need(receipt.get("source_kind") == ("synthetic_diagnostic_fixture" if diagnostic else
                                       "original_native_capture") and
         receipt.get("case_id") == case and receipt.get("packet_sha256") == sha(packet_path),
         "original barrier source receipt differs")
    packet = json.loads(packet_path.read_text())
    need(packet.get("case_id") == case and
         packet.get("route_candidate") == ("wide" if profile == "wide_clearance" else "near"),
         "exact source route differs")
    trace_path = source(root, "trace.jsonl")
    frame_path = source(root, "video_frames.jsonl")
    need(receipt.get("trace_sha256") == sha(trace_path) and
         receipt.get("frame_map_sha256") == sha(frame_path),
         "original trace or frame-map source differs")
    trace = [json.loads(line) for line in trace_path.read_text().splitlines()]
    frame_map = [json.loads(line) for line in frame_path.read_text().splitlines()]
    need(len(trace) == len(frame_map) == len(packet["frames"]) and len(trace) >= 3,
         "source body/trace/frame count differs")
    for index, (row, mapped, motion) in enumerate(zip(packet["frames"], frame_map, trace)):
        need(mapped.get("video_frame") == index and
             mapped.get("carla_frame") == mapped.get("native_frame") ==
             motion.get("frame") == row.get("frame") and
             mapped.get("time_s") == motion.get("time_s") == row.get("time_s"),
             "source body/trace/frame identity differs")
    measured = measure(packet_path)
    obs = measured["observations"]
    values = {
        "ego_body_motion": {"ego_actor_id": measured["ego_actor_id"],
                            "driver_actor_id": measured["driver_actor_id"],
                            "speed_mps": [row["speed_mps"] for row in obs],
                            "frame_count": len(obs)},
        "highway_city_context": {"highway_id": measured["highway_id"],
                                 "city_highway_status": measured["city_highway_status"],
                                 "surrounding_conditions_source": measured["surrounding_conditions_source"]},
        "barrier_body_clearance": {"barrier_id": measured["barrier_id"],
                                   "minimum_vertex_distance_m": min(
                                       row["minimum_vertex_to_barrier_m"] for row in obs),
                                   "reported_contact_frames": [row["frame_index"] for row in obs
                                                               if row["barrier_contact_reported"]]},
        "route_realization": {"route_candidate": packet["route_candidate"],
                              "first_position_m": trace[0].get("position_m"),
                              "last_position_m": trace[-1].get("position_m")},
        "camera_frame_identity": {"frame_count": len(frame_map),
                                  "first_native_frame": frame_map[0]["native_frame"],
                                  "last_native_frame": frame_map[-1]["native_frame"]}}
    sources = {name: sha(source(root, name)) for name in
               ("barrier-packet.json", "original-source-receipt.json", "trace.jsonl",
                "video_frames.jsonl")}
    contract_sources = {name: sources[name] for name in
                        ("barrier-packet.json", "original-source-receipt.json", "trace.jsonl")}
    measurements = {name: {"method": "source_sealed_barrier_measurement",
                           "value": source_sealed_barrier_measurement(value),
                           "sources": contract_sources}
                    for name, value in values.items()}
    evidence = []
    for channel in config["case"]["recording_description"]["channels"]:
        name = channel["name"]
        output = root / ("channel-" + name + ".jsonl")
        content = "".join(json.dumps({"time_s": row["time_s"], "value":
                                       values[name] if name == "highway_city_context" else
                                       row.get("frame") if name == "camera_frame_identity" else
                                       row.get("speed_mps") if name == "ego_body_motion" else
                                       obs[index].get("minimum_vertex_to_barrier_m") if
                                       name == "barrier_body_clearance" else
                                       trace[index].get("position_m")}, sort_keys=True) + "\n"
                          for index, row in enumerate(packet["frames"]))
        if output.exists():
            need(output.read_text() == content, "derived channel differs from saved source")
        else:
            output.write_text(content)
        evidence.append({"name": name, "unit": channel["unit"], "reference": output.name})
    context = root / "channel-reviewed_native_barrier_site.json"
    content = json.dumps({"reviewed_native_barrier_site": {
                          "highway_id": packet["highway_id"],
                          "barrier_id": packet["barrier_id"],
                          "reviewed_site_sha256": packet["reviewed_site_sha256"]}}, sort_keys=True) + "\n"
    if context.exists():
        need(context.read_text() == content, "reviewed site context differs")
    else:
        context.write_text(content)
    evidence.append({"name": "reviewed_native_barrier_site", "unit": "source record",
                     "reference": context.name})
    target = {"target": "selected connected route beside source barrier",
              "requested": profile, "measured": packet["route_candidate"],
              "method": "original driver/vehicle/route and barrier source readback",
              "tolerance": 0, "matched": True,
              "physical_cause_confirmed": False, "cause_evidence": sources}
    from worker_exchange.native_output import physical_result, write_result
    result = {"case_id": case, "measured_values": values,
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
    write_result(root, result)
    return {"format": "worker-analysis-report", "case_id": case,
            "analysis_complete": True, "diagnostic_fixture": diagnostic,
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False,
            "measurements": measurements,
            "physical_checks": result["physical_checks"],
            "realized_observables": result["realized_observables"],
            "limitations": ["Barrier spacing and motion do not define careless or imprudent."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior analysis report")
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + "\n")
