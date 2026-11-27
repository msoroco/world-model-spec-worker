"""Independent source and full-media admission for one railway attempt."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from rail_diagnostic_measurement import verify_diagnostic
from rail_native_capture import CAMERAS
from rail_saved_measurement import _source, verify_saved


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def audit(attempt, case_id, diagnostic=False):
    attempt = Path(attempt).resolve()
    config = json.loads(required(attempt, "config.json").read_text())
    if config.get("selected_case_id") != case_id:
        raise ValueError("selected exact railway case differs")
    receipt = json.loads(required(attempt, "native-rail-receipt.json").read_text())
    packet = json.loads(_source(attempt, receipt.get("packet")).read_text())
    if diagnostic:
        if receipt.get("capture_kind") != "diagnostic_fixture":
            raise ValueError("rail diagnostic test requires synthetic fixture")
        saved = verify_diagnostic(attempt, receipt, packet, case_id)
    else:
        if receipt.get("capture_kind") != "original_native":
            raise ValueError("diagnostic fixture cannot establish Native delivery")
        saved = verify_saved(attempt, packet, case_id)
    trace = rows(required(attempt, "trace.jsonl"))
    mapped = rows(required(attempt, "video_frames.jsonl"))
    if len(trace) != len(mapped) or len(trace) != 900:
        raise ValueError("full original railway frame join missing")
    for index, (frame, camera) in enumerate(zip(trace, mapped)):
        if (frame.get("frame") != camera.get("carla_frame") or
                camera.get("native_frame") != frame.get("frame") or
                camera.get("video_frame") != index or
                abs(frame.get("time_s", -1) - camera.get("time_s", -2)) > 1e-6):
            raise ValueError("railway frame/video identity differs")
    media = {}
    for name, dimensions in CAMERAS.items():
        video = required(attempt, name + ".mkv")
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
            "-count_frames", "-show_entries",
            "stream=nb_read_frames,width,height,r_frame_rate,codec_name", "-of", "json",
            str(video)], capture_output=True, text=True, timeout=3600)
        if probe.returncode:
            raise ValueError("rail camera probe failed: " + name)
        streams = json.loads(probe.stdout).get("streams", [])
        if (len(streams) != 1 or
                int(streams[0].get("nb_read_frames") or -1) != 900 or
                [int(streams[0].get("width") or -1),
                 int(streams[0].get("height") or -1)] != list(dimensions) or
                streams[0].get("r_frame_rate") != "20/1"):
            raise ValueError("rail camera profile differs: " + name)
        decoded = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error",
            "-nostdin", "-i", str(video), "-f", "null", "-"],
            capture_output=True, timeout=7200)
        if decoded.returncode:
            raise ValueError("full rail camera decode failed: " + name)
        pixels = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error",
            "-nostdin", "-i", str(video), "-frames:v", "1", "-vf", "scale=16:16",
            "-f", "rawvideo", "-pix_fmt", "gray", "-"],
            capture_output=True, timeout=3600)
        if pixels.returncode or len(pixels.stdout) != 256:
            raise ValueError("rail camera pixel decode failed: " + name)
        if not diagnostic and max(pixels.stdout) == min(pixels.stdout):
            raise ValueError("original rail camera has no visual content: " + name)
        media[name] = {"sha256": sha(video), "frames": 900,
                       "pixel_range": [min(pixels.stdout), max(pixels.stdout)]}
    if not diagnostic:
        seal = json.loads(required(attempt, "capture-seal.json").read_text())
        if (seal.get("events") != ["capture_finished", "encoders_closed",
                                   "restoration_verified"] or
                seal.get("restoration", {}).get("restored") is not True):
            raise ValueError("rail Native lifecycle incomplete")
        for name in ("native-rail-receipt.json", "native-rail-frames.json",
                     "native-rail-camera-map.json", "trace.jsonl",
                     "video_frames.jsonl", *(name + ".mkv" for name in CAMERAS)):
            if seal.get("sources", {}).get(name) != sha(required(attempt, name)):
                raise ValueError("rail Native seal source changed: " + name)
        native = json.loads(required(attempt, "native-exit.json").read_text())
        owner = json.loads(required(attempt, "owner-release.json").read_text())
        if (native.get("capture_seal_sha256") != sha(attempt / "capture-seal.json") or
                owner.get("native_exit_sha256") != sha(attempt / "native-exit.json")):
            raise ValueError("rail Native ownership closure differs")
        result = json.loads(required(attempt, "result.json").read_text())
        if (result.get("maneuver_completed") is not True or
                result.get("setup_confirmed") is not True):
            raise ValueError("original rail physical maneuver not accepted")
    return {"format": "worker-rail-delivery-audit", "case_id": case_id,
            "passed": True, "diagnostic_only": diagnostic,
            "frame_count": 900, "original_sources_admitted": True,
            "all_participants_reviewed": bool(packet.get("railway_review_source")),
            "full_media_decoded": True, "actual_pixels_claimed": not diagnostic,
            "physical_acceptance": False, "legal_acceptance": False,
            "measurement": saved["observation"], "media": media}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.attempt, args.case_id, args.diagnostic)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"case_id": args.case_id, "diagnostic_only": args.diagnostic,
                      "passed": True}, sort_keys=True))


if __name__ == "__main__":
    main()
