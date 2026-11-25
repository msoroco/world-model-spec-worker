"""CPU diagnostic source proof and original-delivery refusal for one exact case."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from access_measurement import measure
from production_delivery_audit import audit as production_audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--mode", choices=("diagnostic-positive", "delivery-negative"), required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    if root / ".runtime-work" not in args.attempt.resolve().parents:
        raise ValueError("Diagnostic attempt outside ignored scratch")
    source = args.attempt / "original-attempt"
    inventory = json.loads((source / "inventory.json").read_text())
    if inventory.get("diagnostic_fixture") is not True or inventory.get("case_id") != args.case:
        raise ValueError("Exact diagnostic source absent")
    if args.mode == "delivery-negative":
        production_audit(args.attempt, args.case, args.attempt / "independent-review.json")
        raise ValueError("Diagnostic source was accepted for delivery")
    measured = measure(source, inventory, args.case)
    if measured["original_frames"] != 9 or measured["statutory_blocking_judgment"] != "unresolved":
        raise ValueError("Diagnostic access measurement differs")
    mapping = [json.loads(line) for line in (args.attempt / "video_frames.jsonl").read_text().splitlines()]
    if len(mapping) != 9 or [r["video_frame"] for r in mapping] != list(range(9)):
        raise ValueError("Diagnostic video frame join incomplete")
    for camera in ("overview", "approach", "reference_corner", "driver_reference"):
        video = args.attempt / (camera + ".mkv")
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
                                "-show_entries", "stream=nb_read_frames", "-of", "json", str(video)],
                               check=True, capture_output=True, text=True)
        count = int(json.loads(probe.stdout)["streams"][0]["nb_read_frames"])
        if count != 9:
            raise ValueError("Diagnostic four-camera decode incomplete")
        decoded = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-f", "null", "-"],
                                 capture_output=True)
        if decoded.returncode != 0:
            raise ValueError("Diagnostic video pixel decode failed")
    result = json.loads((args.attempt / "result.json").read_text())
    if result["case_id"] != args.case or result.get("diagnostic_fixture") is not True:
        raise ValueError("Diagnostic analysis source differs")
    print(json.dumps({"case_id": args.case, "diagnostic_source_audit": True,
                      "decoded_camera_frames": 36, "delivery_accepted": False}, sort_keys=True))


if __name__ == "__main__":
    main()
