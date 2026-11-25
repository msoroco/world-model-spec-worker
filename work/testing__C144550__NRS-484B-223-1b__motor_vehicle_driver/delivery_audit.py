"""Independent exact-case saved-source and original-pixel acceptance audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from PIL import Image

from camera_capture import SIZES
from native_construction import ASSIGNMENT


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def video_decode(path, frames, size):
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
        "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames,width,height",
        "-of", "json", str(path)], capture_output=True, text=True)
    if probe.returncode:
        raise ValueError("saved video probe failed")
    streams = json.loads(probe.stdout).get("streams", [])
    if (len(streams) != 1 or int(streams[0].get("nb_read_frames", -1)) != frames or
            (streams[0].get("width"), streams[0].get("height")) != size):
        raise ValueError("saved video frame count or dimensions differ")
    decoded = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
                              "-map", "0:v:0", "-f", "null", "-"],
                             capture_output=True, text=True)
    if decoded.returncode:
        raise ValueError("saved full video pixel decode failed")


def audit(attempt, case, *, diagnostic=False, owner_receipt=None):
    root = Path(attempt).resolve()
    if not case.startswith(ASSIGNMENT + "__"):
        raise ValueError("exact lane-change case required")
    config = json.loads(required(root, "config.json").read_text())
    result = json.loads(required(root, "result.json").read_text())
    report = json.loads(required(root, "analysis-report.json").read_text())
    if (result.get("case_id") != case or report.get("case_id") != case or
            config.get("selected_case_id") != case):
        raise ValueError("saved exact case identity differs")
    if (report.get("format") != "c144550-saved-lane-change-report-v1" or
            report.get("analysis_complete") is not True or
            report.get("legal_verdict_claimed") is not False or
            report.get("physical_acceptance_claimed") is not False):
        raise ValueError("saved independent law analysis incomplete")
    source_hashes = report.get("original_source_hashes", {})
    for name, digest in source_hashes.items():
        if sha(required(root, name)) != digest:
            raise ValueError("saved original source SHA256 differs: " + name)
    provenance = json.loads(required(root, "acquisition-provenance.json").read_text())
    kind = "synthetic_fixture" if diagnostic else "native"
    if provenance.get("provenance_kind") != kind or provenance.get("diagnostic_fixture") is not diagnostic:
        raise ValueError("saved acquisition provenance differs")
    capture = json.loads(required(root, "lane-change-capture-receipt.json").read_text())
    if capture.get("native_frame_count") != 900:
        raise ValueError("original 900-frame acquisition incomplete")
    clock = json.loads(required(root, "frame_map.json").read_text())["samples"]
    cameras = json.loads(required(root, "original-camera-frames/camera-manifest.json").read_text())
    trace = [json.loads(line) for line in required(root, "trace.jsonl").read_text().splitlines()]
    frame_map = [json.loads(line) for line in required(root, "video_frames.jsonl").read_text().splitlines()]
    if any(len(value) != 900 for value in (clock, cameras, trace, frame_map)):
        raise ValueError("saved original Native frame count differs")
    for index, (original, camera, actor, mapping) in enumerate(zip(clock, cameras, trace, frame_map)):
        if (camera.get("frame") != index or
                camera.get("native_frame") != original.get("frame") or
                camera.get("native_elapsed_s") != original.get("t_s") or
                actor.get("frame") != mapping.get("carla_frame") or
                actor.get("time_s") != mapping.get("time_s") or
                mapping.get("carla_frame") != original.get("frame") or
                mapping.get("time_s") != original.get("t_s")):
            raise ValueError("saved original frame/time joins differ")
        views = camera.get("views", {})
        if set(views) != set(SIZES):
            raise ValueError("four saved original views missing")
        for name, size in SIZES.items():
            entry = views[name]
            if entry.get("path") != f"{name}-{index:06d}.png":
                raise ValueError("saved original camera path differs")
            png = required(root, "original-camera-frames/" + entry["path"])
            if sha(png) != entry.get("sha256"):
                raise ValueError("saved original camera SHA256 differs")
            with Image.open(png) as image:
                image.load()
                if image.format != "PNG" or image.size != size:
                    raise ValueError("saved original camera pixel decode differs")
    if set(result.get("video_references", [])) != {name + ".mkv" for name in SIZES}:
        raise ValueError("saved four-view references differ")
    for name, size in SIZES.items():
        video_decode(required(root, name + ".mkv"), 900, size)
    original_review = None
    if not diagnostic:
        seal_path = required(root, "capture-seal.json")
        exit_path = required(root, "native-exit.json")
        if owner_receipt is None:
            raise ValueError("original owner-release receipt required")
        owner = json.loads(Path(owner_receipt).read_text())
        seal = json.loads(seal_path.read_text())
        native_exit = json.loads(exit_path.read_text())
        if (seal.get("events") != ["capture_finished", "encoders_closed", "restoration_verified"] or
                native_exit.get("event") != "native_exit" or
                native_exit.get("capture_seal_sha256") != sha(seal_path) or
                owner.get("event") != "owner_released" or
                owner.get("operator_attested") is not True or
                owner.get("native_exit_sha256") != sha(exit_path) or
                owner.get("native_construction_sha256") != sha(required(root, "construction.json"))):
            raise ValueError("original Native closure and owner release absent")
        review_path = required(root, "original-source-review.json")
        if sha(review_path) != provenance.get("original_source_review_sha256"):
            raise ValueError("separately reviewed original site/pixels SHA256 absent")
        original_review = json.loads(review_path.read_text())
        if (original_review.get("case_id") != case or
                not original_review.get("reviewer") or
                original_review.get("reviewed_site_sha256") != sha(required(root, "reviewed-site.json")) or
                original_review.get("camera_manifest_sha256") != sha(required(root, "original-camera-frames/camera-manifest.json")) or
                original_review.get("target_traffic_sha256") != sha(required(root, "target-traffic-history.jsonl")) or
                original_review.get("ego_pose_sha256") != sha(required(root, "ego_pose.json")) or
                original_review.get("physical_pixel_review") != "reviewed_original_pixels" or
                result.get("physical_checks", {}).get("maneuver", {}).get("status") != "met"):
            raise ValueError("independent original site, pixel and physical review absent")
    return {"format": "worker-delivery-audit-diagnostic" if diagnostic else "worker-delivery-audit",
            "case_id": case, "passed": True, "frame_count": 900,
            "decoded_original_png_frames": 3600, "decoded_original_video_frames": 3600,
            "source_hashes": source_hashes,
            "physical_acceptance_claimed": bool(original_review),
            "legal_verdict_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--owner-release-receipt")
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case, diagnostic=args.diagnostic,
                           owner_receipt=args.owner_release_receipt), sort_keys=True))


if __name__ == "__main__":
    main()
