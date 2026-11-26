"""Independent source, Native frame join and full four-video decode audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from analysis import measure
from native_capture import ASSIGNMENT, VIEWS


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("original source missing: " + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def decode(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("camera video missing")
    probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                            "-show_entries", "stream=codec_name,width,height,nb_read_frames,avg_frame_rate",
                            "-of", "json", str(path)], capture_output=True, text=True, check=True)
    streams = json.loads(probe.stdout).get("streams", [])
    if len(streams) != 1 or streams[0].get("codec_name") != "ffv1" or \
            int(streams[0].get("nb_read_frames", -1)) < 1:
        raise ValueError("original camera full-decode profile differs")
    decoded = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i",
                              str(path), "-map", "0:v:0", "-f", "null", "-"],
                             capture_output=True, text=True)
    if decoded.returncode:
        raise ValueError("camera video full decode failed")
    return {"sha256": sha(path), "decoded_frames": int(streams[0]["nb_read_frames"]),
            "dimensions": [streams[0]["width"], streams[0]["height"]],
            "fps": streams[0]["avg_frame_rate"]}


def audit(attempt, case_id, plan):
    attempt = Path(attempt)
    planned = json.loads(Path(plan).read_text())
    if not case_id.startswith(ASSIGNMENT + "__") or \
            case_id not in {row["case_id"] for row in planned["cases"]}:
        raise ValueError("exact center-lane delivery case differs")
    actual_case, measured, history, site, fixture, refs = measure(attempt)
    if actual_case != case_id:
        raise ValueError("attempt case identity differs")
    mapping = rows(attempt / "video_frames.jsonl")
    trace = rows(attempt / "trace.jsonl")
    evidence = rows(attempt / "capture/evidence.jsonl")
    if not mapping or len(mapping) != len(trace) or len(mapping) != len(evidence):
        raise ValueError("original camera and actor frame counts differ")
    numbers = [row.get("carla_frame") for row in mapping]
    if any(row.get("frame") != number or ev.get("original_frame") != number
           for row, ev, number in zip(trace, evidence, numbers)):
        raise ValueError("original camera and actor frame join differs")
    videos = {view: decode(attempt / (view + ".mkv")) for view in VIEWS}
    if any(row["decoded_frames"] != len(mapping) for row in videos.values()):
        raise ValueError("four-view decoded frame count differs")
    joined = len(history) == len(mapping) and all(
        row["original_frame"] == mapped["carla_frame"] and
        abs(row["time_s"] - mapped["time_s"]) < .005
        for row, mapped in zip(history, mapping))
    if not joined or (not fixture and len(mapping) != 900):
        raise ValueError("original Native route/video join incomplete")
    return {"format": "c382162-independent-center-lane-delivery-audit-v1",
            "case_id": case_id, "inventory_sha256": sha(attempt / "native/inventory.json"),
            "source_measurement": measured, "source_refs": refs,
            "capture_frames": len(mapping), "packet_frames": len(history),
            "source_video_join": joined, "four_view_full_decode": videos,
            "diagnostic_fixture": fixture, "actual_pixels_verified": False,
            "physical_acceptance": False, "legal_purpose_judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite independent delivery audit")
    value = audit(args.attempt, args.case_id, args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
