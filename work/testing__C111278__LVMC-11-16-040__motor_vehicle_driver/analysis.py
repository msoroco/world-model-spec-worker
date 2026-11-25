"""Saved-only source-bound C111278 sight and traversal observations."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from saved_sight import verify as verify_saved
from sight_measurement import evaluate


def source_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report(attempt: Path) -> dict:
    attempt = Path(attempt).resolve()
    config = json.loads((attempt / "config.json").read_text())
    case_id = config["selected_case_id"]
    site_path = attempt / "site.json"
    if not site_path.is_file():
        raise ValueError("Missing required source: site.json")
    site = json.loads(site_path.read_text())
    source = attempt / "native-sight.json"
    receipt = attempt / "native-sight-receipt.json"
    for path in (source, receipt):
        if not path.is_file():
            raise ValueError("Missing required source: " + path.name)
    packet = json.loads(source.read_text())
    expected = hashlib.sha256((json.dumps(site, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False) + "\n").encode()).hexdigest()
    if packet.get("site_source_sha256") != expected:
        raise ValueError("reviewed site and original capture hash differ")
    if site.get("selected_case_id") != case_id:
        raise ValueError("reviewed site selects another case")
    for key, config_key in (("ego_road_through", "through_designation"),
                            ("traffic_controlled_intersection", "traffic_controlled_intersection")):
        if site.get(key) != config.get(config_key):
            raise ValueError("selected exception context differs from reviewed source")
    provenance_path = attempt / "fixture-provenance.json"
    diagnostic = provenance_path.is_file()
    if diagnostic:
        provenance = json.loads(provenance_path.read_text())
        capture_receipt = json.loads(receipt.read_text())
        if (provenance.get("diagnostic_fixture") is not True or
                provenance.get("physical_acceptance_claimed") is not False or
                capture_receipt.get("capture_kind") != "synthetic_fixture"):
            raise ValueError("untrusted diagnostic fixture provenance")
        if source_hash(source) != capture_receipt.get("source_sha256"):
            raise ValueError("diagnostic sight source changed")
        measured = evaluate(packet)
        frames = packet["frames"]
        mapping = [json.loads(line) for line in (attempt / "video_frames.jsonl").read_text().splitlines()]
        if len(mapping) != len(frames) or any(
                (row.get("carla_frame"), row.get("time_s")) != (frame["frame"], frame["time_s"])
                for row, frame in zip(mapping, frames)):
            raise ValueError("diagnostic original-shaped frame join differs")
        camera_capture = {"camera_images_decoded": 0, "diagnostic_video_frames": len(mapping)}
    else:
        saved = verify_saved(attempt, case_id)
        measured = saved["measurement"]
        if saved["camera_capture"] == "unverified":
            raise ValueError("original four-camera capture missing")
        camera_capture = saved["camera_capture"]
    sources = {name: source_hash(attempt / name) for name in
               ("site.json", "native-sight.json", "native-sight-receipt.json")}
    values = {
        "qualifying_intersection_context": {"map_hash": measured["map_hash"],
            "case_id": case_id, "entering_arms": packet["entering_arms"],
            "jurisdiction": site.get("jurisdiction"), "road_kind": site.get("road_kind")},
        "last_100ft_sight_observation": {"approach_frame_ids": measured["approach_frame_ids"],
            "blocked_rays": measured["blocked_rays"], "all_views_clear": measured["all_views_clear"],
            "camera_images_decoded": camera_capture["camera_images_decoded"]},
        "traversal_speed_observation": {"traversal_frame_ids": measured["traversal_frame_ids"],
            "minimum_mps": measured["traversal_speed_min_mps"],
            "maximum_mps": measured["traversal_speed_max_mps"],
            "prima_facie_value_mps": measured["prima_facie_value_mps"]},
        "through_street_exception": {"designation": measured["through_designation"],
            "source_sha256": measured["source_sha256"]["through_source_sha256"]},
        "traffic_control_exception": {"controlled": measured["traffic_controlled"],
            "source_sha256": measured["source_sha256"]["control_source_sha256"]},
    }
    return {"format": "worker-analysis-report", "case_id": case_id,
            "measurements": {key: {"method": "report", "value": value, "sources": sources}
                             for key, value in values.items()},
            "analysis_complete": True, "physical_acceptance": False,
            "diagnostic_fixture": diagnostic,
            "legal_verdict_claimed": False,
            "limitations": ["Virtual rays are an engineering proxy, not a legal driver-view finding.",
                            "Physical visibility and municipal authority require independent review."]}


def saved_result(attempt: Path, report_value: dict) -> dict:
    from worker_exchange.native_output import physical_result, validate_result

    attempt = Path(attempt)
    config = json.loads((attempt / "config.json").read_text())
    construction = json.loads((attempt / "construction.json").read_text())
    planned = construction["recording_description"]
    packet = json.loads((attempt / "native-sight.json").read_text())
    frames = packet["frames"]
    mapping = [json.loads(line) for line in (attempt / "video_frames.jsonl").read_text().splitlines()]
    if len(frames) != len(mapping) or any(
            (frame["frame"], frame["time_s"]) != (row.get("carla_frame"), row.get("time_s"))
            for frame, row in zip(frames, mapping)):
        raise ValueError("sight and camera frame map differ")
    streams = {
        "ego_body_speed_history": [f["ego_speed_mps"] for f in frames],
        "approach_route_station": [f["approach_distance_m"] for f in frames],
        "entering_arm_sight_rays": [f.get("rays") for f in frames],
        "exception_source_context": [{"through_designation": packet["through_designation"],
                                       "traffic_controlled": packet["traffic_controlled"]} for _ in frames],
        "camera_frame_map": mapping,
    }
    output = attempt / "channels"
    output.mkdir(exist_ok=False)
    evidence = []
    for channel in planned["channels"]:
        name = channel["name"]
        if name not in streams:
            raise ValueError("unsupported channel: " + name)
        path = output / (name + ".jsonl")
        path.write_text("".join(json.dumps({"time_s": f["time_s"], "value": value}, allow_nan=False) + "\n"
                                for f, value in zip(frames, streams[name])))
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(path.relative_to(attempt))})
    context = output / "context.json"
    context.write_text(json.dumps({"municipal_site_context": json.loads((attempt / "site.json").read_text()),
                                   "diagnostic_fixture": report_value["diagnostic_fixture"]},
                                  allow_nan=False) + "\n")
    for item in planned["context_inputs"]:
        evidence.append({"name": item["name"], "unit": item["unit"],
                         "reference": str(context.relative_to(attempt))})
    observed = report_value["measurements"]["traversal_speed_observation"]["value"]
    result = {"case_id": config["selected_case_id"], "measured_values": observed,
              "target_checks": [{"target": "observed traversal-speed probe",
                                 "requested": config["requested_traversal_speed_mph"],
                                 "measured": observed["maximum_mps"],
                                 "method": "saved source-bound speed observation",
                                 "tolerance": 0.5, "matched": False,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": "diagnostic or original source review required"}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "Saved evidence assessed; legal visibility unresolved",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": ["overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv"],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": planned, "recording_evidence": evidence,
              "realized_observables": {}}
    result = physical_result(attempt, result)
    validate_result(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = report(args.attempt)
    if args.output.exists():
        raise ValueError("analysis output already exists")
    result_path = args.attempt / "result.json"
    if result_path.exists():
        raise ValueError("saved result already exists")
    result_path.write_text(json.dumps(saved_result(args.attempt, value), indent=2) + "\n")
    args.output.write_text(json.dumps(value, indent=2) + "\n")


if __name__ == "__main__":
    main()
