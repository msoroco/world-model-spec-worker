"""Finalize the basic-speed condition record from one closed Native attempt.

All values are descriptive engineering measurements. Reasonable or proper speed
remains an unresolved judgment for later review of original evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from native_camera import VIEWS
from native_scene import VARIABLES
from saved_conditions import FIELDS, measure


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _document(path: Path) -> dict:
    if not path.is_file():
        raise ValueError("Missing required source: " + path.name)
    return json.loads(path.read_text(encoding="utf-8"))


def _rows(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError("Missing required source: " + path.name)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _finite(value, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("invalid original " + name)
    return float(value)


def recording_description() -> dict:
    channels = []
    units = {"ego_speed_mps": "m/s", "leader_gap_m": "m", "highway_width_m": "m",
             "surface_wetness": "fraction", "precipitation_strength": "Native scale",
             "fog_density": "Native scale", "tire_friction": "Native tire friction"}
    for name in FIELDS:
        channels.append({"name": name, "unit": units[name],
                         "source": "original-conditions.jsonl", "field": name})
    return {"format": "c179789-basic-speed-recording-description-v1",
            "channels": channels, "context_inputs": [
                {"name": "authored_speed_conditions", "unit": "reviewed setup",
                 "source": "authored-setup.json"},
                {"name": "original_road_actor_ids", "unit": "Native source identities",
                 "source": "original-conditions.jsonl"}],
            "legal_judgment": "unresolved"}


def _source_bundle(attempt: Path) -> tuple[dict, dict, list[dict], dict]:
    setup_path = attempt / "authored-setup.json"
    setup = _document(setup_path)
    setup_seal = _document(attempt / "authored-setup-seal.json")
    if (setup_seal.get("format") != "c179789-authored-setup-v1" or
            setup_seal.get("case_id") != setup.get("case_id") or
            setup_seal.get("sha256") != sha(setup_path)):
        raise ValueError("authored setup seal differs")
    plan = _document(Path(__file__).resolve().parent / "case-plan.json")
    exact_cases = {item["case_id"] for item in plan["cases"]}
    if (setup.get("case_id") not in exact_cases or
            setup.get("paved_road") is not True or
            not setup.get("travel_direction") or
            not isinstance(setup.get("variables"), dict) or
            set(setup["variables"]) != set(VARIABLES)):
        raise ValueError("authored setup does not bind one exact paved-road case")
    if not (attempt / "original-conditions.jsonl").is_file():
        raise ValueError("Missing required source: original-conditions.jsonl")
    conditions = measure(attempt, setup["case_id"])
    rows = _rows(attempt / "trace.jsonl")
    mapping = _rows(attempt / "video_frames.jsonl")
    if len(rows) != 900 or len(mapping) != 900 or conditions["sample_count"] != 900:
        raise ValueError("original 900-frame duration differs")
    source_hash = setup.get("source_packet_sha256")
    if (not isinstance(source_hash, str) or len(source_hash) != 64 or
            conditions["source_ids"]["opendrive_sha256"] != setup.get("opendrive_sha256")):
        raise ValueError("reviewed setup and original OpenDRIVE source differ")
    for index, (row, mapped, condition) in enumerate(zip(rows, mapping,
                                                          conditions["full_history"])):
        frame, time_s = condition["frame"], condition["time_s"]
        if (row.get("frame") != frame or row.get("source_frame") != frame or
                row.get("time_s") != time_s or row.get("condition_sample_index") != index or
                row.get("source_packet_sha256") != source_hash or
                row.get("physical_acceptance_claimed") is not False or
                mapped.get("video_frame") != index or mapped.get("carla_frame") != frame or
                mapped.get("native_frame") != frame or mapped.get("time_s") != time_s):
            raise ValueError("original trace, condition and frame map join differs")
        camera = row.get("camera_sources")
        hashes = mapped.get("camera_source_sha256")
        if (not isinstance(camera, dict) or set(camera) != {name for name, _, _ in VIEWS} or
                not isinstance(hashes, dict) or set(hashes) != set(camera) or
                any(not isinstance(camera[name], dict) or
                    hashes[name] != camera[name].get("sha256") for name in camera)):
            raise ValueError("original camera/frame map hash join differs")
        position = row.get("position_m")
        if (not isinstance(position, list) or len(position) != 3 or
                any(type(value) not in (int, float) or not math.isfinite(value)
                    for value in position)):
            raise ValueError("original ego position missing")
    receipt = _document(attempt / "media-receipt.json")
    if (receipt.get("format") != "c179789-original-four-camera-media-v1" or
            receipt.get("frames") != 900 or
            receipt.get("source_packet_sha256") != source_hash or
            receipt.get("trace_sha256") != sha(attempt / "trace.jsonl") or
            receipt.get("frame_map_sha256") != sha(attempt / "video_frames.jsonl") or
            receipt.get("physical_acceptance_claimed") is not False):
        raise ValueError("original media source receipt differs")
    status = _document(attempt / "native-run-status.json")
    if (status.get("case_id") != setup["case_id"] or
            status.get("capture", {}).get("frames") != 900 or
            status.get("restoration", {}).get("restored") is not True or
            status.get("errors") != []):
        raise ValueError("original Native runner/restoration status differs")
    videos = receipt.get("video_sha256")
    if not isinstance(videos, dict) or set(videos) != {name for name, _, _ in VIEWS}:
        raise ValueError("original four-view media receipt differs")
    for name, _, _ in VIEWS:
        path = attempt / (name + ".mkv")
        if not path.is_file() or not path.stat().st_size or sha(path) != videos[name]:
            raise ValueError("original four-view video bytes differ")
    return setup, conditions, rows, receipt


def analyze(attempt: Path) -> tuple[dict, dict, dict]:
    """Read sealed sources and derive requested-versus-observed metrics."""
    attempt = Path(attempt).resolve()
    setup, conditions, rows, receipt = _source_bundle(attempt)
    suffix = conditions["full_history"][180:]
    steady = {name: sum(row[name] for row in suffix) / len(suffix) for name in FIELDS}
    first, last = rows[0]["position_m"], rows[-1]["position_m"]
    progress = math.dist(first, last)
    requested = setup.get("variables")
    if not isinstance(requested, dict):
        raise ValueError("authored speed/condition variables missing")
    targets = (
        ("ego_speed_mps", "ego_speed_request_mps", 1.0),
        ("leader_gap_m", "leader_initial_gap_m", 3.0),
        ("surface_wetness", "surface_wetness_request", .05),
        ("highway_width_m", "highway_width_m", .05),
        ("precipitation_strength", "native_precipitation_request", 2.0),
        ("fog_density", "native_fog_request", 2.0),
    )
    checks = []
    for observed, key, tolerance in targets:
        request = _finite(requested.get(key), key)
        value = steady[observed]
        checks.append({"target": observed, "requested": request, "measured": value,
                       "method": "mean original Native samples after first 180 of 900 frames",
                       "tolerance": tolerance, "matched": abs(value - request) <= tolerance,
                       "physical_cause_confirmed": False,
                       "cause_evidence": ["original-conditions.jsonl", "trace.jsonl"]})
    video_names = [name + ".mkv" for name, _, _ in VIEWS]
    recording = recording_description()
    evidence = []
    channel_values = {}
    for index, channel in enumerate(recording["channels"]):
        name = channel["name"]
        reference = f"channels/stream-{index:02d}.jsonl"
        channel_values[reference] = "".join(json.dumps({"time_s": row["time_s"],
                                                         "value": row[name]},
                                                        sort_keys=True) + "\n"
                                              for row in conditions["full_history"])
        evidence.append({"name": name, "unit": channel["unit"], "reference": reference})
    contexts = {"authored_speed_conditions": {"case_id": setup["case_id"],
                                                  "variables": requested,
                                                  "source_packet_sha256": setup["source_packet_sha256"]},
                "original_road_actor_ids": conditions["source_ids"]}
    for index, context in enumerate(recording["context_inputs"]):
        name = context["name"]
        reference = f"channels/context-{index:02d}.json"
        channel_values[reference] = json.dumps({name: contexts[name]}, sort_keys=True) + "\n"
        evidence.append({"name": name, "unit": context["unit"], "reference": reference})
    complete = progress >= .25
    native_result = {"case_id": setup["case_id"],
                     "measured_values": {"steady_means": steady,
                                         "travel_progress_m": progress,
                                         "conditions": conditions,
                                         "legal_judgment": "unresolved"},
                     "target_checks": checks,
                     "setup_confirmed": False,
                     "behavior_attempted": all(isinstance(row.get("control"), dict)
                                               for row in rows),
                     "maneuver_completed": complete,
                     "termination_reason": "planned 900-frame window",
                     "physical_failure_flags": [] if complete else ["travel progress under .25 m"],
                     "trace_reference": "trace.jsonl", "video_references": video_names,
                     "video_frame_map_reference": "video_frames.jsonl",
                     "recording_description": recording,
                     "recording_evidence": evidence, "realized_observables": {},
                     "physical_acceptance_claimed": False}
    hashes = {name: sha(attempt / name) for name in
              ("authored-setup.json", "authored-setup-seal.json",
               "original-conditions.jsonl", "original-conditions-seal.json",
               "trace.jsonl", "video_frames.jsonl", "media-receipt.json",
               "native-run-status.json", *video_names)}
    report = {"format": "c179789-saved-analysis-draft-v1", "case_id": setup["case_id"],
              "measurements": {name: {"method": "measure", "value": value,
                                      "sources": {"original-conditions.jsonl":
                                                  hashes["original-conditions.jsonl"]}}
                               for name, value in steady.items()},
              "target_checks": checks, "sources": hashes,
              "original_media_receipt": receipt,
              "legal_judgment": "unresolved", "physical_acceptance_claimed": False}
    report["measurements"]["basic_speed_observation"] = {
        "method": "measure", "value": {
            "case_id": setup["case_id"], "steady_means": steady,
            "travel_progress_m": progress,
            "source_ids": conditions["source_ids"],
            "legal_judgment": "unresolved"},
        "sources": {name: hashes[name] for name in
                    ("authored-setup.json", "original-conditions.jsonl", "trace.jsonl")}}
    return report, native_result, channel_values


def finalize_attempt(attempt: Path, output: Path) -> dict:
    """Write saved channels and result once, retaining any incomplete attempt."""
    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    if output != attempt / "analysis-report.json":
        raise ValueError("analysis report must stay in the original attempt")
    if output.exists() or (attempt / "result.json").exists() or (attempt / "channels").exists():
        raise ValueError("retain previous saved analysis")
    report, result, channels = analyze(attempt)
    folder = attempt / "channels"
    folder.mkdir()
    for name, content in channels.items():
        (attempt / name).write_text(content, encoding="utf-8")
    (attempt / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n",
                                         encoding="utf-8")
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(finalize_attempt(args.attempt, args.output), indent=2))
