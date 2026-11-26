"""Independently decode all four views and rejoin original signal/vehicle packets."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from analysis import measure
import native_signal as signal


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("original source missing: " + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def decode(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("original camera video missing")
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
                            "-select_streams", "v:0", "-show_entries",
                            "stream=codec_name,width,height,nb_read_frames,avg_frame_rate",
                            "-of", "json", str(path)], capture_output=True,
                           text=True, check=True)
    streams = json.loads(probe.stdout).get("streams", [])
    if len(streams) != 1 or streams[0].get("codec_name") != "ffv1" or \
            int(streams[0].get("nb_read_frames", -1)) < 1:
        raise ValueError("camera full decode profile differs")
    decoded = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror",
                              "-i", str(path), "-map", "0:v:0", "-f", "null", "-"],
                             capture_output=True, text=True)
    if decoded.returncode:
        raise ValueError("camera full decode failed: " + decoded.stderr[-300:])
    return {"sha256": sha(path),
            "decoded_frames": int(streams[0]["nb_read_frames"]),
            "dimensions": [streams[0]["width"], streams[0]["height"]],
            "fps": streams[0]["avg_frame_rate"]}


def audit(attempt, case_id, plan):
    attempt = Path(attempt)
    planned = json.loads(Path(plan).read_text())
    if case_id not in {row["case_id"] for row in planned["cases"]} or \
            not case_id.startswith(signal.ASSIGNMENT + "__"):
        raise ValueError("exact inoperative-signal delivery case differs")
    inventory = attempt / "inventory.json"
    if not inventory.is_file():
        raise ValueError("original signal inventory missing")
    actual, measured, site, ego, other, fixture = measure(attempt)
    if actual != case_id:
        raise ValueError("attempt case identity differs")
    mapping = rows(attempt / "video_frames.jsonl")
    trace = rows(attempt / "trace.jsonl")
    evidence = rows(attempt / "capture/evidence.jsonl")
    if not mapping or len(mapping) != len(trace) or len(mapping) != len(evidence):
        raise ValueError("original video and two-vehicle frame counts differ")
    numbers = [row.get("carla_frame") for row in mapping]
    if any(row.get("frame") != number or ev.get("original_frame") != number
           for row, ev, number in zip(trace, evidence, numbers)):
        raise ValueError("original video/actor frame join differs")
    videos = {view: decode(attempt / (view + ".mkv")) for view in signal.VIEWS}
    if any(item["decoded_frames"] != len(mapping) for item in videos.values()):
        raise ValueError("four-view full-decode frame count differs")
    joined = len(ego) == len(other) == len(mapping) and all(
        erow["original_frame"] == orow["original_frame"] == mapped["carla_frame"]
        and abs(erow["time_s"] - mapped["time_s"]) <= .005
        and abs(orow["time_s"] - mapped["time_s"]) <= .005
        for erow, orow, mapped in zip(ego, other, mapping))
    if not fixture and (not joined or len(mapping) != signal.FULL_FRAMES):
        raise ValueError("original Native signal source/video join incomplete")
    return {"format": "c376646-independent-signal-delivery-audit-v1",
            "case_id": case_id, "inventory_sha256": sha(inventory),
            "source_measurement": measured,
            "signal_id": site["signal_id"],
            "capture_frames": len(mapping), "ego_packet_frames": len(ego),
            "other_packet_frames": len(other), "source_video_join": joined,
            "four_view_full_decode": videos, "diagnostic_fixture": fixture,
            "actual_pixels_verified": False, "physical_acceptance": False,
            "cautious_proceeding_judgment": "unresolved"}


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
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
