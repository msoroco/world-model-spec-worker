"""Independent original right-lane source and four-view full-decode audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from analysis import measure
from native_capture import ASSIGNMENT, VIEWS


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    if not Path(path).is_file() or Path(path).is_symlink():
        raise ValueError("original source missing: " + Path(path).name)
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def _decode(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("original camera video missing")
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                            "-select_streams", "v:0",
                            "-show_entries", "stream=codec_name,width,height,nb_read_frames,avg_frame_rate",
                            "-of", "json", str(path)], capture_output=True, text=True, check=True)
    streams = json.loads(probe.stdout).get("streams", [])
    if len(streams) != 1:
        raise ValueError("original camera stream missing")
    stream = streams[0]
    if int(stream.get("nb_read_frames", -1)) < 1 or stream.get("codec_name") != "ffv1":
        raise ValueError("camera full decode profile differs")
    decoded = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror",
                              "-i", str(path), "-map", "0:v:0", "-f", "null", "-"],
                             capture_output=True, text=True)
    if decoded.returncode:
        raise ValueError("camera full decode failed: " + decoded.stderr[-300:])
    return {"sha256": _sha(path), "decoded_frames": int(stream["nb_read_frames"]),
            "dimensions": [stream["width"], stream["height"]],
            "fps": stream["avg_frame_rate"]}


def audit(attempt, case_id, plan):
    attempt = Path(attempt)
    if case_id not in {row["case_id"] for row in json.loads(Path(plan).read_text())["cases"]}:
        raise ValueError("exact delivery case differs")
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("exact assignment differs")
    inventory_path = attempt / "inventory.json"
    if not inventory_path.is_file():
        raise ValueError("original inventory missing")
    inventory = json.loads(inventory_path.read_text())
    measured = measure(attempt)
    mapping = _rows(attempt / "video_frames.jsonl")
    trace = _rows(attempt / "trace.jsonl")
    evidence = _rows(attempt / "capture/evidence.jsonl")
    if not mapping or len(mapping) != len(trace) or len(mapping) != len(evidence):
        raise ValueError("original video and actor frame counts differ")
    numbers = [row.get("carla_frame") for row in mapping]
    if any(row.get("frame") != number or ev.get("original_frame") != number
           for row, ev, number in zip(trace, evidence, numbers)):
        raise ValueError("original video and actor frame join differs")
    videos = {name: _decode(attempt / (name + ".mkv")) for name in VIEWS}
    if any(item["decoded_frames"] != len(mapping) for item in videos.values()):
        raise ValueError("camera full-decode frame count differs")
    history = json.loads((attempt / inventory["sources"]["history"]["path"]).read_text())
    source_frames = history["frames"]
    joined = len(source_frames) == len(mapping) and all(
        abs(packet["time_s"] - mapped["time_s"]) < .005 and
        packet.get("source_frame_id", mapped["carla_frame"]) == mapped["carla_frame"]
        for packet, mapped in zip(source_frames, mapping))
    fixture = (attempt / "fixture-provenance.json").is_file()
    if not fixture and (not joined or len(mapping) != 900):
        raise ValueError("original Native source/video frame join incomplete")
    return {"format": "c240647-independent-right-lane-delivery-audit-v1",
            "case_id": case_id, "inventory_sha256": _sha(inventory_path),
            "source_measurement": measured, "capture_frames": len(mapping),
            "packet_frames": len(source_frames), "source_video_join": joined,
            "four_view_full_decode": videos, "diagnostic_fixture": fixture,
            "actual_pixels_verified": False, "physical_acceptance": False,
            "legal_lane_judgment": "unresolved"}


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
