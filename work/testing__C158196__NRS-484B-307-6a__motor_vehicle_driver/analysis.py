"""Saved-only signal and body-entry measurements; no legal verdict."""

import argparse
import hashlib
import json
from pathlib import Path

from package_spec import CAMERA_NAMES
from signal_measurement import measure


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def analyze(attempt):
    root = Path(attempt).resolve()
    config = json.loads(required(root, "config.json").read_text())
    case_id = config["selected_case_id"]
    slug = case_id.removeprefix(config["assignment_id"] + "__")
    packet_path = required(root, "original-signal-packet.json")
    packet = json.loads(packet_path.read_text())
    receipt_path = required(root, "original-source-receipt.json")
    receipt = json.loads(receipt_path.read_text())
    diagnostic = receipt.get("diagnostic_fixture") is True
    need((receipt.get("source_kind") == "synthetic_diagnostic_fixture" if diagnostic else
          receipt.get("source_kind") == "original_native_capture"),
         "source provenance differs from diagnostic/original claim")
    need(receipt.get("signal_packet_sha256") == sha(packet_path) and
         receipt.get("case") == slug, "signal source packet/receipt mismatch")
    required(root, "trace.jsonl")
    required(root, "video_frames.jsonl")
    profile = ("yellow_non_alone" if slug == "yellow_non_alone" else
               "red_other_route" if slug == "red_other_route" else
               "steady_yellow_alone")
    observed = measure(packet, expected_frames=len(packet["frames"]), case_profile=profile)
    sources = {name: sha(required(root, name)) for name in
               ("original-signal-packet.json", "original-source-receipt.json",
                "trace.jsonl", "video_frames.jsonl")}
    phase = observed["phase_transitions"]
    bracket = observed["entry_bracket"]
    values = {
        "selected_facing_signal_sequence": {"selected_route_id": observed["selected_route_id"],
                                            "selected_signal_id": observed["selected_signal_id"],
                                            "phase_transitions": phase,
                                            "yellow_alone_observed": observed["yellow_alone_observed"],
                                            "companion_indication_frames": observed["companion_indication_frames"]},
        "intersection_entry_bracket": {"entry_bracket": bracket,
                                       "entry_observation": observed["entry_observation"],
                                       "initially_inside": observed["initially_inside_intersection"]},
        "signal_vs_entry": {"phase_transitions": phase, "entry_bracket": bracket,
                            "entry_observation": observed["entry_observation"],
                            "legal_judgment": "unresolved"},
        "comparison_isolation": {"selected_route_id": observed["selected_route_id"],
                                 "other_route_red_frames": observed["other_route_red_frames"],
                                 "source_provenance": receipt["source_kind"]},
    }
    measurements = {name: {"method": "source_sealed_signal_measurement",
                           "value": value, "sources": sources}
                    for name, value in values.items()}
    evidence = []
    for channel in config["case"]["recording_description"]["channels"]:
        name = channel["name"]
        data = ([{"time_s": row["time_s"], "value": row.get("carla_frame")}
                 for row in (json.loads(line) for line in
                             required(root, "video_frames.jsonl").read_text().splitlines())]
                if name == "camera_frame_identity" else
                [{"time_s": row["time_s"], "value":
                  values[name] if name != "intersection_entry_bracket" else
                  {"signed_distance_m": row["ego_front_signed_distance_m"],
                   "entry_observation": observed["entry_observation"]}}
                 for row in packet["frames"]])
        target = root / ("channel-" + name + ".jsonl")
        encoded = "".join(json.dumps(row, sort_keys=True) + "\n" for row in data)
        if target.exists():
            need(target.read_text() == encoded, "derived channel differs from source replay")
        else:
            target.write_text(encoded)
        evidence.append({"name": name, "unit": channel["unit"], "reference": target.name})
    context = root / "channel-reviewed_native_signal_scene.json"
    content = json.dumps({"route": observed["selected_route_id"],
                          "signal": observed["selected_signal_id"],
                          "source_hashes": sources}, sort_keys=True) + "\n"
    if context.exists():
        need(context.read_text() == content, "reviewed source context changed")
    else:
        context.write_text(content)
    evidence.append({"name": "reviewed_native_signal_scene", "unit": "source record",
                     "reference": context.name})
    expected = ("no_entry" if slug in ("stops_red", "yellow_non_alone") else
                "red_both_samples" if slug == "enters_red" else
                "yellow_both_samples")
    matched = observed["entry_observation"] == expected
    from worker_exchange.native_output import physical_result, write_result
    target_check = {"target": "selected route signal and surveyed body entry",
                    "requested": expected, "measured": observed["entry_observation"],
                    "method": "original 20 Hz official head and front/polygon bracket",
                    "tolerance": 0, "matched": matched,
                    "physical_cause_confirmed": False, "cause_evidence": sources}
    result = {"case_id": case_id, "measured_values": values,
        "target_checks": [target_check], "setup_confirmed": False,
        "behavior_attempted": False, "maneuver_completed": False,
        "termination_reason": "saved source measurement; physical and legal review pending",
        "physical_failure_flags": ["physical_acceptance_unverified"],
        "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in CAMERA_NAMES],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["case"]["recording_description"],
        "recording_evidence": evidence, "realized_observables": {},
        "diagnostic_fixture": diagnostic, "physical_acceptance_claimed": False,
        "legal_verdict_claimed": False}
    result = physical_result(root, result)
    write_result(root, result)
    return {"format": "worker-analysis-report", "case_id": case_id,
            "analysis_complete": True, "diagnostic_fixture": diagnostic,
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False,
            "measurements": measurements, "physical_checks": result["physical_checks"],
            "realized_observables": result["realized_observables"],
            "limitations": ["Original phase and entry are observations, not legal findings."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior analysis report")
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + "\n")
