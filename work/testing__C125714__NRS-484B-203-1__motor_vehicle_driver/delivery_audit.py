"""Independent saved-source audit for an exact opposing-pass recording."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from PIL import Image

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError("missing saved source: " + name)
    return path


def decoded_frames(path):
    completed = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
        "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
        "-of", "json", str(path)], capture_output=True, text=True)
    if completed.returncode != 0:
        raise ValueError("saved video probe failed")
    streams = json.loads(completed.stdout).get("streams", [])
    if len(streams) != 1:
        raise ValueError("saved video stream missing")
    count = int(streams[0].get("nb_read_frames", -1))
    decoded = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
                              "-map", "0:v:0", "-f", "null", "-"],
                             capture_output=True, text=True)
    if decoded.returncode != 0:
        raise ValueError("saved full video pixel decode failed: " + decoded.stderr.strip())
    return count


def audit(attempt, case, *, diagnostic=False):
    root = Path(attempt).resolve()
    config = json.loads(required(root, "config.json").read_text())
    result = json.loads(required(root, "result.json").read_text())
    receipt = json.loads(required(root, "opposing-capture-receipt.json").read_text())
    trace_path = required(root, "opposing-actor-trace.json")
    map_path = required(root, "reviewed-map.json")
    manifest_path = required(root, "opposing-camera-frames/camera-manifest.json")
    if config.get("selected_case_id") != case or result.get("case_id") != case:
        raise ValueError("exact saved case differs")
    if sha(trace_path) != receipt.get("sha256"):
        raise ValueError("actor source hash mismatch")
    if sha(manifest_path) != receipt.get("camera_manifest", {}).get("sha256"):
        raise ValueError("camera source hash mismatch")
    trace = json.loads(trace_path.read_text())
    if sha(map_path) != trace.get("map_sha256"):
        raise ValueError("map source hash mismatch")
    rows = trace.get("samples")
    if not isinstance(rows, list) or not rows or len(rows) != receipt.get("frame_count"):
        raise ValueError("actor source frame count mismatch")
    provenance = json.loads(required(root, "acquisition-provenance.json").read_text())
    expected_kind = "synthetic_fixture" if diagnostic else "native"
    if provenance.get("provenance_kind") != expected_kind or trace.get("diagnostic_fixture") is not diagnostic:
        raise ValueError("original Native provenance differs")
    original_review = None
    if not diagnostic:
        review_path = required(root, "original-source-review.json")
        if sha(review_path) != provenance.get("original_source_review_sha256"):
            raise ValueError("original site review hash mismatch")
        original_review = json.loads(review_path.read_text())
        if (original_review.get("case_id") != case or
                not original_review.get("site_source_id") or
                not original_review.get("reviewer") or
                original_review.get("actor_trace_sha256") != sha(trace_path) or
                original_review.get("camera_manifest_sha256") != sha(manifest_path) or
                original_review.get("map_sha256") != sha(map_path) or
                original_review.get("physical_pixel_review") != "reviewed_original_pixels"):
            raise ValueError("original site acquisition and pixel review absent")
        seal_path = required(root, "capture-seal.json")
        native_exit_path = required(root, "native-exit.json")
        owner_path = required(root, "owner-release.json")
        seal = json.loads(seal_path.read_text())
        native_exit = json.loads(native_exit_path.read_text())
        owner = json.loads(owner_path.read_text())
        if (seal.get("events") != ["capture_finished", "encoders_closed", "restoration_verified"] or
                native_exit.get("event") != "native_exit" or
                native_exit.get("capture_seal_sha256") != sha(seal_path) or
                owner.get("event") != "owner_released" or
                owner.get("operator_attested") is not True or
                owner.get("native_exit_sha256") != sha(native_exit_path) or
                owner.get("native_construction_sha256") != sha(required(root, "construction.json"))):
            raise ValueError("Native closure and owner release receipt absent")
    manifest = json.loads(manifest_path.read_text())
    png_count = 0
    if diagnostic:
        if not isinstance(manifest, dict) or manifest.get("format") != "diagnostic-video-join":
            raise ValueError("diagnostic camera source missing")
        cameras = manifest.get("rows")
        if manifest.get("videos") != {name: name + ".mkv" for name in CAMERAS}:
            raise ValueError("four diagnostic views missing")
    else:
        if not isinstance(manifest, list) or len(rows) != 900:
            raise ValueError("original Native camera history incomplete")
        cameras = manifest
    if not isinstance(cameras, list) or len(cameras) != len(rows):
        raise ValueError("camera and actor histories differ")
    for index, (actor, camera) in enumerate(zip(rows, cameras)):
        if any(actor.get(key) != camera.get(key) for key in
               ("frame", "time_s", "native_frame", "native_elapsed_s")):
            raise ValueError("camera and actor original clock differ")
        if not diagnostic:
            views = camera.get("views")
            if not isinstance(views, dict) or set(views) != set(CAMERAS):
                raise ValueError("four original views missing")
            for name in CAMERAS:
                entry = views[name]
                expected = f"{name}-{index:06d}.png"
                if entry.get("path") != expected:
                    raise ValueError("original camera path changed")
                image = required(root, "opposing-camera-frames/" + expected)
                if sha(image) != entry.get("sha256"):
                    raise ValueError("original camera source hash mismatch")
                with Image.open(image) as decoded:
                    decoded.load()
                    if decoded.format != "PNG" or decoded.width <= 0 or decoded.height <= 0:
                        raise ValueError("original camera pixel decode failed")
                png_count += 1
    trace_rows = [json.loads(line) for line in required(root, "trace.jsonl").read_text().splitlines()]
    mapping = [json.loads(line) for line in required(root, "video_frames.jsonl").read_text().splitlines()]
    if len(trace_rows) != len(rows) or len(mapping) != len(rows):
        raise ValueError("saved trace and video frame counts differ")
    if any(t["frame"] != m["carla_frame"] or t["time_s"] != m["time_s"]
           for t, m in zip(trace_rows, mapping)):
        raise ValueError("saved trace/video time join differs")
    if set(result.get("video_references", [])) != {name + ".mkv" for name in CAMERAS}:
        raise ValueError("saved four-view references differ")
    for name in CAMERAS:
        if decoded_frames(required(root, name + ".mkv")) != len(rows):
            raise ValueError("saved full video decode count differs")
    report = json.loads(required(root, "analysis-report.json").read_text())
    if report.get("case_id") != case or report.get("analysis_complete") is not True:
        raise ValueError("saved law analysis incomplete")
    physical = report.get("physical_checks", {}).get("maneuver", {})
    if not diagnostic and (physical.get("status") != "met" or
                           report.get("maneuver_completed") is not True):
        raise ValueError("original physical completion absent")
    return {"format": "worker-delivery-audit-diagnostic" if diagnostic else "worker-delivery-audit",
            "case_id": case, "passed": True, "frame_count": len(rows),
            "decoded_original_png_frames": png_count,
            "source_hashes": {"opposing-actor-trace.json": sha(trace_path),
                              "reviewed-map.json": sha(map_path),
                              "opposing-camera-frames/camera-manifest.json": sha(manifest_path)},
            "physical_acceptance_claimed": bool(original_review),
            "legal_verdict": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case, diagnostic=args.diagnostic), sort_keys=True))


if __name__ == "__main__":
    main()
