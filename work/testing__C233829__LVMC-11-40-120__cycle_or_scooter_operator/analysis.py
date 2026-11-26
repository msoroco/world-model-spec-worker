"""Saved rider facility measurement; path usability and law remain unresolved."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from path_observation import ASSIGNMENT, measure_packet
from source_deferred_runner import CAMERAS, FRAMES, _case_parts
from source_site import load_reviewed_site, sha


def required(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def _rows(path: Path) -> list:
    return [json.loads(line) for line in path.read_text().splitlines()]


def _original(root: Path, case_id: str, device: str, target: str,
              condition: str) -> tuple[dict, list, dict]:
    seal_path = required(root, "capture-seal.json")
    seal = json.loads(seal_path.read_text())
    if (seal.get("format") != "adjacent-path-original-native-seal-v1" or
            seal.get("case_id") != case_id or seal.get("provenance_kind") != "native" or
            seal.get("diagnostic_fixture") is not False or seal.get("frames") != FRAMES or
            seal.get("capture_rate_hz") != 20 or
            seal.get("restoration", {}).get("restored") is not True):
        raise ValueError("sealed original Native rider capture required")
    files = seal.get("sources", {})
    mandatory = {"rider-history.jsonl", "camera-frame-map.jsonl", "video_frames.jsonl",
                 "reviewed-site/source-manifest.json", "reviewed-site/site-context.json",
                 "reviewed-site/native-adapter.py", *[name + ".mkv" for name in CAMERAS]}
    if not isinstance(files, dict) or not mandatory <= set(files):
        raise ValueError("sealed original rider source inventory incomplete")
    for relative, digest in files.items():
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or sha(required(root, relative)) != digest:
            raise ValueError("sealed original source changed: " + relative)
    for name in ("construction.json", "config.json", "runner.py"):
        if seal.get("native_revision", {}).get(name) != sha(required(root, name)):
            raise ValueError("sealed Native implementation changed: " + name)
    manifest_path = required(root, "reviewed-site/source-manifest.json")
    site_path = required(root, "reviewed-site/site-context.json")
    if (seal.get("reviewed_manifest_sha256") != sha(manifest_path) or
            seal.get("reviewed_site_sha256") != sha(site_path)):
        raise ValueError("reviewed site source changed")
    reviewed = load_reviewed_site(manifest_path, site_path, case_id,
                                  device, target, condition)
    rows = _rows(required(root, "rider-history.jsonl"))
    cameras = _rows(required(root, "camera-frame-map.jsonl"))
    video = _rows(required(root, "video_frames.jsonl"))
    if len(rows) != FRAMES or len(cameras) != FRAMES or len(video) != FRAMES:
        raise ValueError("full 900-frame original rider and camera history required")
    first_frame = rows[0].get("native_frame")
    for i, (row, camera, frame) in enumerate(zip(rows, cameras, video)):
        if (row.get("frame_index") != i or row.get("native_frame") != first_frame + i or
                camera.get("frame_index") != i or camera.get("native_frame") != first_frame + i or
                camera.get("camera_frames") != {name: first_frame + i for name in CAMERAS} or
                frame.get("video_frame") != i or frame.get("carla_frame") != first_frame + i or
                frame.get("native_frame") != first_frame + i or
                abs(row.get("time_s", -100) - i / 20) > 1e-5 or
                abs(camera.get("time_s", -100) - row["time_s"]) > 1e-5 or
                abs(frame.get("time_s", -100) - row["time_s"]) > 1e-5 or
                row.get("ego_device_type") != device or not row.get("ego_actor_id")):
            raise ValueError("original rider/camera/native frame join changed")
    source = {"rider-history.jsonl": sha(root / "rider-history.jsonl"),
              "capture-seal.json": sha(seal_path),
              "reviewed-site/source-manifest.json": sha(manifest_path),
              "reviewed-site/site-context.json": sha(site_path)}
    return reviewed["site"], rows, source


def _diagnostic(root: Path, case_id: str, device: str,
                target: str, condition: str) -> tuple[dict, list, dict]:
    note_path = required(root, "diagnostic-source-note.json")
    note = json.loads(note_path.read_text())
    if (note.get("source_kind") != "synthetic_diagnostic_fixture" or
            note.get("accepted_original_source") is not False or
            note.get("case_id") != case_id):
        raise ValueError("explicit synthetic diagnostic provenance required")
    site_path = required(root, "site.json")
    site = json.loads(site_path.read_text())
    if (site.get("case_id") != case_id or site.get("ego_device_type") != device or
            site.get("path_usability_status") != condition):
        raise ValueError("diagnostic rider site identity mismatch")
    rows_path = required(root, "rider-history.jsonl")
    rows = _rows(rows_path)
    if len(rows) != FRAMES:
        raise ValueError("900 source-specific diagnostic rider frames required")
    return site, rows, {"rider-history.jsonl": sha(rows_path),
                        "site.json": sha(site_path),
                        "diagnostic-source-note.json": sha(note_path)}


def analyze(root: str | Path) -> dict:
    root = Path(root)
    config = json.loads(required(root, "config.json").read_text())
    case_id = config.get("selected_case_id")
    device, target, condition = _case_parts(case_id)
    if config.get("assignment_id") != ASSIGNMENT:
        raise ValueError("saved exact assignment identity mismatch")
    original = (root / "capture-seal.json").is_file()
    if original:
        site, rows, sources = _original(root, case_id, device, target, condition)
    else:
        site, rows, sources = _diagnostic(root, case_id, device, target, condition)
    packet = {"assignment_id": ASSIGNMENT, "original_trace_id": sources["rider-history.jsonl"],
              "ego_device_type": device, "ego_actor_id": rows[0]["ego_actor_id"],
              "roadway_id": site["roadway_id"], "path_id": site["path_id"],
              "path_designation_source": site["path_designation_source"],
              "path_adjacent_to_roadway": site["path_adjacent_to_roadway"],
              "sidewalk_status": site["sidewalk_status"],
              "path_usability_status": site["path_usability_status"],
              "path_condition_source": site.get("path_condition_source", sources.get("reviewed-site/source-manifest.json")),
              "access_restrictions_source": site.get("access_restrictions_source", sources.get("reviewed-site/source-manifest.json")),
              "frames": rows}
    measured = measure_packet(packet, {"path": "rider-history.jsonl",
                                       "sha256": sources["rider-history.jsonl"]})
    if len(measured["observations"]) != FRAMES:
        raise ValueError("full rider facility measurement required")
    channels = {
        "rider_facility": lambda row: {"roadway": row["ego_body_on_roadway"],
                                        "designated_path": row["ego_body_on_designated_path"]},
        "path_context": lambda row: {"path_id": site["path_id"],
                                      "roadway_id": site["roadway_id"],
                                      "usability_status": site["path_usability_status"]},
        "device_classification": lambda row: {"actor_id": row["ego_actor_id"],
                                               "device_type": row["ego_device_type"]},
        "camera_frame_identity": lambda row: {"native_frame": row.get("native_frame")},
    }
    description = config["case"]["recording_description"]
    evidence = []
    for channel in description["channels"]:
        name = channel["name"]
        if name not in channels:
            raise ValueError("unknown adjacent-path recording channel: " + name)
        output = root / ("channel-" + name + ".jsonl")
        output.write_text("".join(json.dumps({"time_s": row["time_s"],
                                              "value": channels[name](row)}) + "\n" for row in rows))
        evidence.append({"name": name, "unit": channel["unit"], "reference": output.name})
    from worker_exchange.native_output import physical_result, write_result
    result = {"case_id": case_id, "measured_values": {
                  "roadway_use_observed": measured["roadway_use_observed"],
                  "path_use_observed": measured["path_use_observed"]},
              "target_checks": [{"target": "source-measured rider facility",
                                 "requested": target, "measured": "roadway" if measured["roadway_use_observed"] else "path",
                                 "method": "900 sealed original body rows" if original else "900 synthetic body rows",
                                 "tolerance": 0, "matched": False if original else True,
                                 "physical_cause_confirmed": False, "cause_evidence": sources}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "original saved measurement; physical review pending" if original else "synthetic compatibility only",
              "physical_failure_flags": [] if original else ["original_rider_and_path_source_absent"],
              "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in CAMERAS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": description, "recording_evidence": evidence,
              "realized_observables": {}, "diagnostic_fixture": not original,
              "physical_acceptance_claimed": False, "legal_verdict_claimed": False}
    result = physical_result(root, result)
    write_result(root, result)
    return {"format": "worker-analysis-report", "case_id": case_id,
            "analysis_complete": True, "diagnostic_fixture": not original,
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False,
            "measurements": {"rider_facility_use": {"method": "measure_packet",
                "value": {"roadway_use_observed": measured["roadway_use_observed"],
                          "path_use_observed": measured["path_use_observed"],
                          "frame_count": FRAMES,
                          "path_usability_status": measured["path_usability_status"]},
                "sources": sources}},
            "physical_checks": result["physical_checks"],
            "realized_observables": result["realized_observables"],
            "limitations": ["Path usability, access and legal compliance require independent original source review."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior rider analysis report")
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + "\n")
