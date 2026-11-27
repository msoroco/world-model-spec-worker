"""Independent saved-source walking delivery audit; no legal verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from walking_measure import measure

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
DIMS = {"overview": (1920, 1080), "approach": (1280, 720),
        "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def required(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def audit(attempt: Path, case_id: str, diagnostic: bool = False) -> dict:
    attempt = Path(attempt).resolve()
    config = json.loads(required(attempt, "config.json").read_text(encoding="utf-8"))
    spec = json.loads(required(attempt, "case-spec.json").read_text(encoding="utf-8"))
    if config.get("selected_case_id") != case_id or spec.get("case_id") != case_id:
        raise ValueError("selected walking case identity differs")
    source = required(attempt, "original-walking-observations.json")
    receipt = json.loads(required(attempt, "original-walking-receipt.json").read_text(encoding="utf-8"))
    packet = json.loads(source.read_text(encoding="utf-8"))
    if (receipt.get("case_id") != case_id or packet.get("case_id") != case_id
            or receipt.get("source_sha256") != sha(source)
            or receipt.get("diagnostic_fixture") is not diagnostic
            or packet.get("diagnostic_fixture") is not diagnostic
            or receipt.get("fps") != 20):
        raise ValueError("original walking source receipt or provenance differs")
    measurements = measure(packet)
    frames = packet["frames"]
    mapping = rows(required(attempt, "video_frames.jsonl"))
    trace = rows(required(attempt, "trace.jsonl"))
    if len(frames) != receipt.get("frame_count") or len(mapping) != len(frames) or len(trace) != len(frames) or (not diagnostic and len(frames) != 900):
        raise ValueError("original walking frame count or stream join differs")
    for index, (frame, mapped, native) in enumerate(zip(frames, mapping, trace)):
        if (mapped.get("video_frame") != index or mapped.get("carla_frame") != frame.get("frame")
                or mapped.get("native_frame") != frame.get("frame") or native.get("frame") != frame.get("frame")
                or abs(mapped.get("time_s", -1) - frame["time_s"]) > 1e-4
                or abs(native.get("time_s", -1) - frame["time_s"]) > 1e-4):
            raise ValueError("original walking frame/time join differs")
        expected_source = "synthetic_diagnostic" if diagnostic else "original_native_snapshot"
        if frame.get("observation_source") != expected_source:
            raise ValueError("original walking transform source differs")
    if not diagnostic:
        review = json.loads(required(attempt, "reviewed-site-receipt.json").read_text(encoding="utf-8"))
        if review.get("packet", {}).get("sha256") != packet.get("site_source_sha256"):
            raise ValueError("reviewed original site packet binding differs")
        for ref in [review["packet"], *review.get("sources", {}).values()]:
            if sha(required(attempt, ref["path"])) != ref.get("sha256"):
                raise ValueError("reviewed original site source changed")
    if measurements["pedestrian_progress_m"] < 5:
        raise ValueError("original pedestrian did not complete walking motion")
    if not measurements["any_frame_vehicle_approaching"]:
        raise ValueError("original approaching vehicle motion missing")
    expected_side = "center_right" if (spec["approach_direction"] == "east") == (spec["pedestrian_highway_side"] == "left") else "center_left"
    if set(measurements["pedestrian_side_history"]) != {expected_side}:
        raise ValueError("original pedestrian highway side differs")
    if measurements["all_frames_facing"] != (spec["pedestrian_heading"] == "facing"):
        raise ValueError("original pedestrian facing contrast differs")
    media = {}
    for camera in CAMERAS:
        path = required(attempt, camera + ".mkv")
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
            "-count_frames", "-show_entries", "stream=nb_read_frames,codec_name,width,height,r_frame_rate",
            "-of", "json", str(path)], capture_output=True, text=True, timeout=60)
        if probe.returncode:
            raise ValueError("four-camera ffprobe failed: " + camera)
        streams = json.loads(probe.stdout).get("streams", [])
        if len(streams) != 1 or int(streams[0].get("nb_read_frames", -1)) != len(frames):
            raise ValueError("four-camera frame count differs: " + camera)
        stream = streams[0]
        if not diagnostic and (stream.get("codec_name") != "ffv1"
                or (stream.get("width"), stream.get("height")) != DIMS[camera]
                or stream.get("r_frame_rate") != "20/1"):
            raise ValueError("original video codec, size or rate differs: " + camera)
        decoded = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
            "-i", str(path), "-f", "null", "-"], capture_output=True, timeout=120)
        if decoded.returncode:
            raise ValueError("four-camera full decode failed: " + camera)
        media[camera] = {"sha256": sha(path), "frames": len(frames), "codec": stream.get("codec_name")}
    if not diagnostic:
        pixels = json.loads(required(attempt, "original-pixel-review.json").read_text(encoding="utf-8"))
        if pixels.get("case_id") != case_id or not pixels.get("reviewer") or pixels.get("all_participants_visible") is not True:
            raise ValueError("original participant pixel review missing")
        if pixels.get("video_sha256") != {camera: media[camera]["sha256"] for camera in CAMERAS}:
            raise ValueError("original pixel review video bytes differ")
    return {"format": "worker-independent-walking-delivery", "case_id": case_id,
        "passed": True, "diagnostic_only": diagnostic, "physical_acceptance": False,
        "frame_count": len(frames), "source_sha256": sha(source),
        "measurement": measurements, "full_video_decode": media}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    result = audit(args.attempt, args.case_id, args.diagnostic)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"case_id": args.case_id, "passed": True}))


if __name__ == "__main__":
    main()
