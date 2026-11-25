"""Exact source-gated Native entrypoint for C111706 U-turn deliveries."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ASSIGNMENT = "testing__C111706__NRS-484B-403-3__motor_vehicle_driver"
SUFFIXES = ("intersection_vehicle_near", "approach_before_intersection",
            "intersection_vehicle_far")
CASES = {ASSIGNMENT + "__" + suffix for suffix in SUFFIXES}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finish_original(attempt, site_path, selected, receipt):
    """Seal one restored Native capture and encode its original camera images."""
    from worker_exchange.native_output import seal_capture

    capture = attempt / "capture"
    native_path = capture / "native-uturn.json"
    camera_manifest = capture / "camera-originals" / "camera-manifest.json"
    packet = json.loads(native_path.read_text(encoding="utf-8"))
    camera = json.loads(camera_manifest.read_text(encoding="utf-8"))
    frames = packet["frames"]
    if (len(frames) != 900 or packet.get("case_id") != selected or
            packet.get("site_sha256") != sha(site_path) or
            camera.get("case_id") != selected or
            camera.get("native_sha256") != sha(native_path) or
            camera.get("frame_count") != 900):
        raise ValueError("original Native and camera capture incomplete")
    shutil.copyfile(site_path, capture / "site.json")
    index = {"format": "c111706-native-source-index-v1", "case_id": selected,
             "files": {name: {"source": "native_original", "sha256": sha(capture / name)}
                       for name in ("site.json", "native-uturn.json")}}
    (capture / "source-index.json").write_text(json.dumps(index, indent=2) + "\n")
    with (attempt / "video_frames.jsonl").open("x") as stream:
        for number, frame in enumerate(frames):
            stream.write(json.dumps({"video_frame": number,
                                     "carla_frame": frame["frame"],
                                     "time_s": frame["time_s"]}) + "\n")
    for view in ("overview", "approach", "reference_corner", "driver_reference"):
        view_rows = camera["views"][view]
        expected_dir = (capture / "camera-originals" / view).resolve()
        if ([row["frame"] for row in view_rows] != [frame["frame"] for frame in frames] or
                any(Path(row["path"]).resolve() != expected_dir / f'{row["frame"]:08d}.png'
                    or abs(row["time_s"] - frame["time_s"]) > 1e-6
                    or sha(Path(row["path"])) != row["sha256"]
                    for row, frame in zip(view_rows, frames))):
            raise ValueError("original camera image/frame binding differs: " + view)
        source_pattern = str(capture / "camera-originals" / view / "*.png")
        video = attempt / (view + ".mkv")
        subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                        "-framerate", "20", "-pattern_type", "glob", "-i", source_pattern,
                        "-frames:v", "900", "-an", "-c:v", "ffv1", "-pix_fmt", "yuv444p",
                        str(video)], check=True, timeout=3600)
        if not video.is_file() or video.stat().st_size == 0:
            raise ValueError("original camera video missing: " + view)
    (attempt / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "native", "diagnostic_fixture": False,
        "site_sha256": sha(capture / "site.json"),
        "native_sha256": sha(native_path)}, indent=2) + "\n")
    seal_capture(attempt, frames=900, restoration=receipt["restoration"],
                 errors=[], encoder_exit_codes={view: 0 for view in camera["views"]},
                 context={"site_sha256": sha(capture / "site.json"),
                          "native_sha256": sha(native_path),
                          "camera_manifest_sha256": sha(camera_manifest)})


def check(root=ROOT):
    root = Path(root)
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    if (config.get("assignment_id"), config.get("law_id"),
            config.get("cell_id"), config.get("actor")) != (
            ASSIGNMENT, "NRS-484B-403-3", "C111706", "motor_vehicle_driver"):
        raise ValueError("wrong exact U-turn package identity")
    selected = config.get("selected_case_id")
    if selected not in CASES or set(config.get("supported_case_ids", [])) != CASES:
        raise ValueError("exact U-turn case selection differs")
    if (config.get("rate_hz"), config.get("duration_s"),
            config.get("frame_count")) != (20, 45, 900):
        raise ValueError("exact U-turn capture timebase differs")
    cameras = config.get("cameras", [])
    if [(c.get("name"), c.get("width"), c.get("height")) for c in cameras] != [
            ("overview", 1920, 1080), ("approach", 1280, 720),
            ("reference_corner", 1280, 720),
            ("driver_reference", 1280, 720)]:
        raise ValueError("four original cameras required")
    return selected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args(argv)
    selected = check()
    if args.check:
        return 0
    if args.output_dir is None:
        raise ValueError("new Native output directory required")
    site_root = os.environ.get("C111706_SITE_ROOT")
    if not site_root:
        raise ValueError("C111706_SITE_ROOT reviewed site directory required")
    site_path = Path(site_root) / (selected.split("__")[-1] + ".json")
    if not site_path.is_file() or site_path.is_symlink():
        raise ValueError("exact reviewed site packet required")
    from live_entrypoint import run
    try:
        receipt = run(host=args.host, port=args.port, site_path=site_path,
                      case_id=selected, output=args.output_dir / "capture" / "native-uturn.json")
        finish_original(args.output_dir, site_path, selected, receipt)
    except Exception as error:
        (args.output_dir / "native-run-status.json").write_text(json.dumps({
            "errors": [str(error)], "capture_complete": False,
            "selected_case_id": selected}, indent=2) + "\n")
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
