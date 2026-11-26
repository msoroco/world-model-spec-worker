"""Independent source and four-view decode audit for an exact door episode.

Fixture media and source packets are checked separately. Only a later original
Native capture with joined 900-frame histories can establish physical delivery.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from door_measurement import ASSIGNMENT, measure

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _decode(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("original camera video missing")
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                            "-show_entries", "stream=codec_name,width,height,nb_read_frames,avg_frame_rate",
                            "-of", "json", str(path)], capture_output=True, text=True, check=True)
    streams = json.loads(probe.stdout).get("streams", [])
    if len(streams) != 1:
        raise ValueError("original camera stream missing")
    stream = streams[0]
    if int(stream.get("nb_read_frames", -1)) < 1 or stream.get("codec_name") != "ffv1":
        raise ValueError("camera full decode profile differs")
    decoded = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(path),
                              "-map", "0:v:0", "-f", "null", "-"], capture_output=True, text=True)
    if decoded.returncode:
        raise ValueError("camera full decode failed: " + decoded.stderr[-300:])
    return {"sha256": _sha(path), "decoded_frames": int(stream["nb_read_frames"]),
            "dimensions": [stream["width"], stream["height"]], "fps": stream["avg_frame_rate"]}


def audit(attempt: Path, case_id: str, plan: Path) -> dict:
    attempt = Path(attempt)
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("exact delivery case differs")
    inventory_path = attempt / "inventory.json"
    inventory = json.loads(inventory_path.read_text())
    measurement = measure(attempt, inventory, case_id, plan)
    mapping = _rows(attempt / "video_frames.jsonl")
    trace = _rows(attempt / "trace.jsonl")
    evidence = _rows(attempt / "capture" / "evidence.jsonl")
    if not mapping or len(mapping) != len(trace) or len(mapping) != len(evidence):
        raise ValueError("capture video and actor frame counts differ")
    frame_ids = [row.get("carla_frame") for row in mapping]
    if any(row.get("frame") != frame or ev.get("original_frame") != frame
           for row, ev, frame in zip(trace, evidence, frame_ids)):
        raise ValueError("capture video and actor frame join differs")
    videos = {name: _decode(attempt / (name + ".mkv")) for name in VIEWS}
    if any(row["decoded_frames"] != len(mapping) for row in videos.values()):
        raise ValueError("camera full decode frame count differs")
    packet_frames = json.loads((attempt / inventory["sources"]["frame_map"]["path"]).read_text())["frames"]
    joined_native = len(packet_frames) == len(mapping) and all(
        packet["frame"] == mapped["carla_frame"] and abs(packet["time_s"] - mapped["time_s"]) < .005
        for packet, mapped in zip(packet_frames, mapping))
    fixture = (attempt / "fixture-provenance.json").exists()
    if not fixture and (not joined_native or len(mapping) != 900):
        raise ValueError("original Native source/video frame join incomplete")
    return {"format": "c135087-independent-door-delivery-audit-v1", "case_id": case_id,
            "inventory_sha256": _sha(inventory_path), "source_measurement": measurement,
            "capture_frames": len(mapping), "packet_frames": len(packet_frames),
            "source_video_join": joined_native, "four_view_full_decode": videos,
            "diagnostic_fixture": fixture, "actual_pixels_verified": False,
            "physical_acceptance": False, "legal_necessity_or_immediacy": "unresolved"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite independent audit")
    result = audit(args.attempt, args.case_id, args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
