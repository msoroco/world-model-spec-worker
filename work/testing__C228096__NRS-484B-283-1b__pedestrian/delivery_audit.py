"""Audit a released original curb-entry attempt without deciding the law."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from curb_entry import CASES, measure_original, validate_scene


ASSIGNMENT = "testing__C228096__NRS-484B-283-1b__pedestrian"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCES = ("pedestrian_identity", "curb_safety", "road_boundary",
           "vehicle_path", "vehicle_motion", "driver_control",
           "pedestrian_route", "departure_timing", "introductory_exceptions")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def linked(root: Path, ref: dict) -> Path:
    if not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or not ref.get("sha256"):
        raise ValueError("original source reference missing")
    candidate = root / ref["path"]
    path = candidate.resolve()
    if candidate.is_symlink() or not path.is_relative_to(root) or not path.is_file():
        raise ValueError("original source path missing or escaping root")
    if sha(path) != ref["sha256"]:
        raise ValueError("original source hash changed")
    return path


def probe_video(path: Path) -> dict:
    command = ["ffprobe", "-v", "error", "-select_streams", "v:0",
               "-count_frames", "-show_entries",
               "stream=nb_read_frames,r_frame_rate,width,height", "-of", "json", str(path)]
    output = subprocess.run(command, capture_output=True, text=True, check=True, timeout=120)
    streams = json.loads(output.stdout).get("streams", [])
    if len(streams) != 1:
        raise ValueError("one original video stream required")
    return streams[0]


def audit(root: Path, receipt: dict, probe=probe_video) -> dict:
    root = Path(root).resolve()
    case_id = receipt.get("case_id", "")
    case = next((item for item in CASES if case_id == ASSIGNMENT + "__" + item.name), None)
    if case is None:
        raise ValueError("exact assigned curb-entry case required")
    if (receipt.get("source_kind") != "original_native_attempt" or
            receipt.get("diagnostic_fixture") is True or
            receipt.get("owner_released") is not True or
            receipt.get("native_process_exit_code") != 0 or
            not receipt.get("attempt_id") or not receipt.get("recording_id")):
        raise ValueError("released original Native attempt required")
    site_path = linked(root, receipt.get("site_ref"))
    site = json.loads(site_path.read_text(encoding="utf-8"))
    if site.get("reviewed_original_site") is not True or site.get("diagnostic_fixture") is True:
        raise ValueError("reviewed original curb and roadway site required")
    scene = site.get("scenes", {}).get(case.name)
    if not isinstance(scene, dict):
        raise ValueError("reviewed exact scene missing")
    for name in SOURCES:
        source_ref = site.get("source_refs", {}).get(name)
        linked(root, source_ref)
        if scene.get(name + "_source_sha256") != source_ref["sha256"]:
            raise ValueError("reviewed scene source binding differs: " + name)
    validate_scene(scene, case)
    frame_path = linked(root, receipt.get("frame_map_ref"))
    trace_path = linked(root, receipt.get("trace_ref"))
    videos = receipt.get("video_refs")
    if not isinstance(videos, dict) or set(videos) != set(CAMERAS):
        raise ValueError("four original camera videos required")
    video_paths = {name: linked(root, videos[name]) for name in CAMERAS}
    seal_path = linked(root, receipt.get("capture_seal_ref"))
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    if (seal.get("source_kind") != "original_native_capture_seal" or
            seal.get("case_id") != case_id or
            seal.get("attempt_id") != receipt["attempt_id"] or
            seal.get("recording_id") != receipt["recording_id"]):
        raise ValueError("original capture seal identity differs")
    all_refs = [receipt["site_ref"], receipt["frame_map_ref"], receipt["trace_ref"]]
    all_refs.extend(videos.values())
    if any(seal.get("sources", {}).get(ref["path"]) != ref["sha256"] for ref in all_refs):
        raise ValueError("original capture seal source inventory differs")
    frame_map = json.loads(frame_path.read_text(encoding="utf-8"))
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    frames = frame_map.get("frames")
    rows = trace.get("frames")
    if (frame_map.get("source_kind") != "original_native_frame_map" or
            frame_map.get("case_id") != case_id or
            trace.get("case_id") != case_id or trace.get("diagnostic_fixture") is True or
            not isinstance(frames, list) or len(frames) != 900 or
            not isinstance(rows, list) or len(rows) != 900):
        raise ValueError("complete original frame map and motion required")
    if [row.get("frame") for row in frames] != list(range(900)):
        raise ValueError("original sequential frame map required")
    for index, frame in enumerate(frames):
        if (frame.get("native_frame") != rows[index].get("original_frame") or
                frame.get("time_s") != rows[index].get("time_s") or
                set(frame.get("camera_frames", {})) != set(CAMERAS) or
                any(value != frame["native_frame"]
                    for value in frame["camera_frames"].values())):
            raise ValueError("original four-camera time join differs")
    for name, path in video_paths.items():
        stream = probe(path)
        if (stream.get("nb_read_frames") != "900" or
                stream.get("r_frame_rate") != "20/1" or
                int(stream.get("width", 0)) < 640 or
                int(stream.get("height", 0)) < 360):
            raise ValueError("original camera decode or profile incomplete: " + name)
    measured = measure_original(rows, scene, case)
    return {"format": "c228096-original-delivery-audit-v1", "case_id": case_id,
            "attempt_id": receipt["attempt_id"], "recording_id": receipt["recording_id"],
            "source_kind": "original_native_attempt", "site_sha256": sha(site_path),
            "trace_sha256": sha(trace_path), "frame_map_sha256": sha(frame_path),
            "capture_seal_sha256": sha(seal_path),
            "video_sha256": {name: sha(path) for name, path in video_paths.items()},
            "frames_checked": 900, "measurement": measured,
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "physical_completion": "requires independent local review",
            "legal_suddenness_or_impossibility": "unresolved"}
