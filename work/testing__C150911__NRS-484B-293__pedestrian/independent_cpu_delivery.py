"""Independent original-source and four-video CPU audit for one saved attempt."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from crosswalk_delivery import measure
from delivery_audit import CAMERAS, audit_saved


def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s]


def audit(attempt, case_id, diagnostic=False):
    attempt = Path(attempt).resolve()
    receipt = json.loads(required(attempt, "original-receipt.json").read_text())
    if receipt.get("case_id") != case_id or receipt.get("fps") != 20:
        raise ValueError("original receipt identity differs")
    if bool(receipt.get("diagnostic_fixture")) != bool(diagnostic):
        raise ValueError("diagnostic provenance differs")
    names = ("original-site.json", "original-pedestrian.jsonl",
             "original-obstacles.jsonl", "original-participants.jsonl")
    for name in names:
        if receipt.get("sources", {}).get(name) != sha(required(attempt, name)):
            raise ValueError("original source hash differs: " + name)
    site = json.loads((attempt / names[0]).read_text())
    samples, obstacles, participants = [lines(attempt / name) for name in names[1:]]
    measurement = measure(site, samples, obstacles, participants)
    measurement["case_id"] = case_id
    mapping = lines(required(attempt, "video_frames.jsonl"))
    if len(mapping) != receipt["frame_count"] or len(samples) != len(mapping):
        raise ValueError("original frame count differs")
    for i, (sample, frame) in enumerate(zip(samples, mapping)):
        if frame.get("video_frame") != i or frame.get("carla_frame") != sample["frame"] or (
                abs(frame.get("time_s", -1) - sample["elapsed_s"]) > 1e-4):
            raise ValueError("original frame/time join differs")
    packet = {"case_id": case_id, "native_result_sha256": sha(required(attempt, "result.json")),
        "frame_map_sha256": sha(attempt / "video_frames.jsonl"),
        "frame_count": len(mapping), "fps": 20,
        "sources": {name: {"path": path, "sha256": sha(required(attempt, path))}
                    for name, path in (("native_result", "result.json"),
                                       ("frame_map", "video_frames.jsonl"),
                                       *((camera, camera + ".mkv") for camera in CAMERAS))}}
    result = audit_saved(packet, measurement, attempt)
    media = {}
    for camera in CAMERAS:
        path = attempt / (camera + ".mkv")
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
            "-count_frames", "-show_entries", "stream=nb_read_frames", "-of", "json", str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
        if probe.returncode:
            raise ValueError("four-camera ffprobe failed: " + camera)
        streams = json.loads(probe.stdout).get("streams", [])
        if len(streams) != 1 or int(streams[0]["nb_read_frames"]) != len(mapping):
            raise ValueError("four-camera decoded frame count differs: " + camera)
        decoded = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
            "-i", str(path), "-f", "null", "-"], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=120)
        if decoded.returncode:
            raise ValueError("four-camera full decode failed: " + camera)
        media[camera] = {"sha256": sha(path), "decoded_frames": len(mapping)}
    result.update({"format": "c150911-independent-cpu-delivery",
        "diagnostic_only": diagnostic, "full_video_decode": media,
        "physical_acceptance": False, "legal_practicability": "unresolved"})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    result = audit(args.attempt, args.case_id, args.diagnostic)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"case_id": args.case_id, "passed": True}))


if __name__ == "__main__":
    main()
