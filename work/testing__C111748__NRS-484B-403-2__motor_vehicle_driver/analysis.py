"""Saved-only exact U-turn device measurement from original Native readbacks.

Diagnostic materializations exercise software compatibility. They do not
establish a legally official device, actual pixels, or physical acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("device_native_for_analysis", ROOT / "native_device.py")
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError("Missing required source: " + path.name)
    return [json.loads(row) for row in path.read_text().splitlines() if row.strip()]


def measure_device_duty(attempt: Path, case_id: str) -> tuple[dict, list[dict]]:
    source = attempt / "device-native.json"
    if not source.is_file():
        raise ValueError("Missing required source: device-native.json")
    packet = json.loads(source.read_text())
    measurement = native.analyze(source, case_id=case_id, sha256=sha(source))
    mapping = read_rows(attempt / "video_frames.jsonl")
    trace = read_rows(attempt / "trace.jsonl")
    rows = packet["frames"]
    if len(mapping) != len(trace) or len(rows) != len(trace):
        raise ValueError("Native, trace and video frame counts differ")
    for index, (native_row, point, camera) in enumerate(zip(rows, trace, mapping)):
        if (native_row["frame"] != point["frame"] or
                native_row["frame"] != camera["carla_frame"] or
                abs(native_row["time_s"] - point["time_s"]) > 1e-6 or
                abs(native_row["time_s"] - camera["time_s"]) > 1e-6 or
                camera["video_frame"] != index):
            raise ValueError("original Native and video trace frame join changed")
    if packet.get("diagnostic") is False and len(rows) != 900:
        raise ValueError("production source needs 900 original frames")
    return measurement, rows


def analyze(attempt: Path, output: Path) -> dict:
    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    if attempt != output.parent:
        raise ValueError("analysis report must stay in the same saved attempt")
    config = json.loads((attempt / "config.json").read_text())
    case_id = config["selected_case_id"]
    measurement, rows = measure_device_duty(attempt, case_id)
    expected = config["case"]
    if (measurement["prohibits_u_turn"] != expected["device_prohibits_u_turn"] or
            measurement["turn_observed"] != expected["driver_turn_target"]):
        raise ValueError("exact device or driver action differs from selected case")
    source_sha = sha(attempt / "device-native.json")
    report = {"format": "worker-analysis-report", "measurements": {
        "official_device_obedience": {
            "method": "measure_device_duty", "sources": {"device-native.json": source_sha},
            "value": {"device_prohibits_u_turn": measurement["prohibits_u_turn"],
                      "turn_observed": measurement["turn_observed"],
                      "first_visible_frame": measurement["first_visible_frame"],
                      "first_turn_frame": measurement["first_turn_frame"],
                      "legal_device_status": "unresolved"}}},
        "limitations": ["Device legality, actual sign pixels and realized turn require original independent review."],
        "analysis_complete": True, "legal_verdict_claimed": False}
    output.write_text(json.dumps(report, indent=2) + "\n")
    channels = attempt / "channels"
    channels.mkdir(exist_ok=True)
    evidence = []
    observations = {
        "official_device_context": lambda row: {
            "authority_source_sha256": json.loads((attempt / "device-native.json").read_text())["device"]["authority_source_sha256"],
            "prohibits_u_turn": row["device_readback"]["prohibits_u_turn"]},
        "display_and_observation": lambda row: {
            "device_id": row["device_readback"]["device_id"],
            "visible_to_ego_readback": row["device_readback"]["visible_to_ego"]},
        "u_turn_action": lambda row: {
            "ego": row["ego"], "original_frame": row["frame"]}}
    for channel in config["recording_description"]["channels"]:
        name = channel["name"]
        if name not in observations:
            raise ValueError("unsupported exact observation channel: " + name)
        path = channels / (name + ".jsonl")
        with path.open("x") as stream:
            for row in rows:
                stream.write(json.dumps({"time_s": row["time_s"],
                                         "value": observations[name](row)}) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": path.relative_to(attempt).as_posix()})
    context = channels / "context.json"
    packet = json.loads((attempt / "device-native.json").read_text())
    context.write_text(json.dumps({"reviewed_original_site": {
        "site_sha256": packet.get("site_sha256"),
        "review_binding": packet.get("site_review_binding"),
        "diagnostic": bool(packet.get("diagnostic"))}}, indent=2) + "\n")
    evidence.append({"name": "reviewed_original_site", "unit": "metadata",
                     "reference": context.relative_to(attempt).as_posix()})
    checks = []
    for target, requested, measured in (
        ("device_prohibits_u_turn", expected["device_prohibits_u_turn"], measurement["prohibits_u_turn"]),
        ("driver_turn_target", expected["driver_turn_target"], measurement["turn_observed"])):
        checks.append({"target": target, "requested": requested, "measured": measured,
                       "method": "sealed original Native device/ego readbacks",
                       "tolerance": 0, "matched": requested == measured,
                       "physical_cause_confirmed": False,
                       "cause_evidence": {"native_sha256": source_sha, "physical_review": "pending"}})
    result = {"case_id": case_id, "measured_values": report["measurements"],
              "target_checks": checks, "setup_confirmed": False,
              "behavior_attempted": False, "maneuver_completed": False,
              "termination_reason": "Saved source measurement; independent physical review pending",
              "physical_failure_flags": {"physical_review_pending": True},
              "trace_reference": "trace.jsonl",
              "video_references": [camera["name"] + ".mkv" for camera in config["cameras"]],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config["recording_description"],
              "recording_evidence": evidence,
              "realized_observables": {},
              "legal_judgment": "unresolved",
              "diagnostic_fixture": bool(packet.get("diagnostic")),
              "source_sha256": {"device-native.json": source_sha}}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    target = attempt / "result.json"
    if target.exists():
        raise ValueError("prior saved result exists")
    target.write_text(json.dumps(result, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.attempt, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
