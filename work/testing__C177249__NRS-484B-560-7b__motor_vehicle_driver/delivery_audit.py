"""Independent original railway instruction, body and full-decode audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from analysis import measure
from native_capture import VIEWS

ASSIGNMENT = "testing__C177249__NRS-484B-560-7b__motor_vehicle_driver"


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
                            "-of", "json", str(path)], capture_output=True, text=True, check=True)
    streams = json.loads(probe.stdout).get("streams", [])
    if len(streams) != 1 or streams[0].get("codec_name") != "ffv1" or int(streams[0].get("nb_read_frames", -1)) < 1:
        raise ValueError("original railway camera full decode profile differs")
    done = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror",
                           "-i", str(path), "-map", "0:v:0", "-f", "null", "-"],
                          capture_output=True, text=True)
    if done.returncode:
        raise ValueError("original railway camera full decode failed: " + done.stderr[-300:])
    return {"sha256": sha(path), "decoded_frames": int(streams[0]["nb_read_frames"]),
            "dimensions": [streams[0]["width"], streams[0]["height"]],
            "fps": streams[0]["avg_frame_rate"]}


def audit(attempt, case_id, plan):
    attempt = Path(attempt)
    planned = json.loads(Path(plan).read_text())
    if case_id not in {row["case_id"] for row in planned["cases"]} or not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("exact railway delivery case differs")
    inventory = attempt / "inventory.json"
    if not inventory.is_file():
        raise ValueError("original railway inventory missing")
    actual_case, measured, history, site, fixture = measure(attempt)
    if actual_case != case_id:
        raise ValueError("original railway attempt case identity differs")
    mapping = rows(attempt / "video_frames.jsonl")
    trace = rows(attempt / "trace.jsonl")
    evidence = rows(attempt / "capture/evidence.jsonl")
    if not mapping or len(mapping) != len(trace) or len(mapping) != len(evidence):
        raise ValueError("original railway video and actor frame counts differ")
    numbers = [row.get("carla_frame") for row in mapping]
    if any(row.get("frame") != number or ev.get("original_frame") != number
           for row, ev, number in zip(trace, evidence, numbers)):
        raise ValueError("original railway video and actor frame join differs")
    videos = {view: decode(attempt / (view + ".mkv")) for view in VIEWS}
    if any(item["decoded_frames"] != len(mapping) for item in videos.values()):
        raise ValueError("original railway four-view full-decode frame count differs")
    joined = len(history) == len(mapping) and all(
        packet["time_s"] == mapped["time_s"] and
        packet["source_frame"] == mapped["carla_frame"]
        for packet, mapped in zip(history, mapping))
    if not fixture and (not joined or len(mapping) != 900):
        raise ValueError("original Native railway source/video join incomplete")
    original_actor_id = history[0].get("vehicle_actor_id")
    if type(original_actor_id) is not int:
        raise ValueError("original driver actor identity missing")
    if any(packet.get("source_site_sha256") != site["_packet_sha256"] or
           packet.get("vehicle_actor_id") != original_actor_id or
           packet.get("vehicle_blueprint_id") != site["vehicle"]["blueprint_id"] or
           not packet.get("device_indication_source_ref") or
           (case_id.endswith(("officer_stop_halt", "officer_stop_cross")) and
            not packet.get("officer_direction_source_ref"))
           for packet in history):
        raise ValueError("original railway site, device, officer or driver identity differs")
    return {"format": "c177249-independent-railway-7b-delivery-audit-v1",
            "case_id": case_id, "inventory_sha256": sha(inventory),
            "source_measurement": measured, "capture_frames": len(mapping),
            "packet_frames": len(history), "source_video_join": joined,
            "four_view_full_decode": videos, "diagnostic_fixture": fixture,
            "actual_pixels_verified": False, "physical_acceptance": False,
            "instruction_authenticity": "requires independent source review",
            "legal_judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite independent railway audit")
    result = audit(args.attempt, args.case_id, args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
