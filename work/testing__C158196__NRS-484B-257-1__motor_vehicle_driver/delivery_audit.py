"""Independent C158196 saved-source audit.

Diagnostic mode proves joins and decoding. Delivery mode requires original Native
provenance, measured pixels, and physical completion; synthetic fixtures fail.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

PREFIX = "testing__C158196__NRS-484B-257-1__motor_vehicle_driver__"
VARIANTS = {"nearest_view_hold", "nearest_view_continue", "nearest_view_clear", "active_signal_exception"}
CAMERAS = {"approach", "driver_reference", "overview", "reference_corner"}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bound(base: Path, binding: dict) -> Path:
    if not isinstance(binding, dict) or set(binding) != {"path", "sha256"}:
        raise ValueError("source binding incomplete")
    name = binding["path"]
    if Path(name).is_absolute() or ".." in Path(name).parts:
        raise ValueError("source escapes attempt")
    path = base / name
    if not path.is_file() or digest(path) != binding["sha256"]:
        raise ValueError("source hash differs")
    return path


def audit(case_id: str, attempt: Path, diagnostic: bool = False) -> dict:
    if not case_id.startswith(PREFIX) or case_id[len(PREFIX):] not in VARIANTS:
        raise ValueError("wrong exact case")
    original = read(attempt / "nearest-view-original.json")
    if original.get("case_id") != case_id:
        raise ValueError("original source selects another case")
    frames = original.get("frames")
    raw = original.get("raw_frames")
    if not isinstance(frames, list) or len(frames) != 900 or not isinstance(raw, list) or len(raw) != 900:
        raise ValueError("original frame coverage incomplete")
    for i, (row, observation) in enumerate(zip(frames, raw)):
        if row.get("frame") != 100 + i or observation.get("frame") != 100 + i or row.get("time_s") != observation.get("time_s"):
            raise ValueError("original observation frame/time join differs")
        if not observation.get("ego_body_xy_m") or not observation.get("through_body_xy_m"):
            raise ValueError("participant body source missing")
    sources = original.get("sources", {})
    required = {"crosswalk_survey", "native_map", "officer_observation", "sidewalk_survey", "signal_state_readback", "stop_line_survey", "through_highway_survey", "view_raycast"}
    if not required <= set(sources):
        raise ValueError("source inventory incomplete")
    for name in required:
        bound(attempt, sources[name])
    native = attempt / "capture"
    manifest = read(native / "manifest.json")
    if manifest.get("case_id") != case_id or manifest.get("frames") != 900:
        raise ValueError("Native capture manifest differs")
    for name, expected in manifest.get("sources", {}).items():
        source = attempt / name
        if not source.is_file() or digest(source) != expected:
            raise ValueError("Native source hash differs: " + name)
    bound(native, manifest.get("native_map_facts"))
    evidence = [json.loads(line) for line in (native / "evidence.jsonl").read_text().splitlines()]
    native_frames = [json.loads(line) for line in (native / "native/frames.jsonl").read_text().splitlines()]
    trace = [json.loads(line) for line in (attempt / "trace.jsonl").read_text().splitlines()]
    if not all(len(rows) == 900 for rows in (evidence, native_frames, trace)):
        raise ValueError("Native source frame count differs")
    for i, (packet, graph, motion) in enumerate(zip(evidence, native_frames, trace)):
        frame = 100 + i
        if packet.get("original_frame") != frame or graph.get("frame") != frame or motion.get("frame") != frame or packet.get("recording_time_s") != motion.get("time_s") or graph.get("simulation_time") != motion.get("time_s"):
            raise ValueError("Native source frame/time join differs")
        adapter = graph.get("adapter_graph", "")
        if Path(adapter).is_absolute() or ".." in Path(adapter).parts or not (native / "native" / adapter).is_file():
            raise ValueError("Native graph projection missing")
    camera = read(attempt / "camera-sources.json")
    if camera.get("case_id") != case_id or set(camera.get("sources", {})) != CAMERAS:
        raise ValueError("four-camera inventory incomplete")
    frame_map_path = attempt / "camera-frame-map.json"
    frame_map = read(frame_map_path)
    if camera.get("frame_map_sha256") != digest(frame_map_path) or len(frame_map) != 900:
        raise ValueError("camera frame map hash or count differs")
    zero = "0" * 64
    all_pixels = True
    for i, row in enumerate(frame_map):
        hashes = row.get("pixel_sha256", {})
        if row.get("frame") != 100 + i or set(hashes) != CAMERAS:
            raise ValueError("camera frame join differs")
        all_pixels &= all(isinstance(h, str) and len(h) == 64 and h != zero for h in hashes.values())
    for name, source in camera["sources"].items():
        path = attempt / source["path"]
        if path.is_symlink() or not path.is_file() or source.get("frame_count") != 900:
            raise ValueError("camera source missing: " + name)
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries", "stream=nb_read_frames", "-of", "default=noprint_wrappers=1:nokey=1", str(path)], capture_output=True, text=True)
        if probe.returncode != 0 or probe.stdout.strip() != "900":
            raise ValueError("camera decode count differs: " + name)
        decode = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"], capture_output=True, text=True)
        if decode.returncode != 0:
            raise ValueError("full video decode failed: " + name)
    if not diagnostic:
        if original.get("diagnostic_fixture") is True or manifest.get("acquisition") == "diagnostic_fixture" or camera.get("diagnostic") is True:
            raise ValueError("diagnostic fixture cannot establish Native delivery")
        if not all_pixels:
            raise ValueError("actual camera pixels unverified")
        physical = read(attempt / "physical-result.json")
        if physical.get("physical_checks", {}).get("maneuver", {}).get("status") != "met" or physical.get("diagnostic_fixture") is True:
            raise ValueError("physical completion unverified")
    return {"case_id": case_id, "frames": 900, "cameras": sorted(CAMERAS), "source_join": "passed", "full_decode": "passed", "actual_pixels": all_pixels, "diagnostic": diagnostic, "delivery_accepted": not diagnostic}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("case_id")
    parser.add_argument("attempt", type=Path)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.case_id, args.attempt, args.diagnostic), sort_keys=True))
