"""Independent saved-source review for a right-arm cycle signal.

Diagnostic fixtures exercise this checker only. Original delivery additionally
requires complete Native evidence, decoded camera bytes and a bound pixel review.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from signal_measurements import measure


ASSIGNMENT = "testing__C229813__NRS-484B-769__cycle_or_scooter_operator"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def audit_media(path, count):
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-count_frames", "-show_entries", "stream=nb_read_frames,r_frame_rate",
                            "-of", "json", str(path)], text=True, capture_output=True)
    if probe.returncode:
        raise ValueError("original camera probe failed")
    stream = json.loads(probe.stdout)["streams"][0]
    if int(stream["nb_read_frames"]) != count or stream["r_frame_rate"] != "20/1":
        raise ValueError("original camera frame count or cadence differs")
    decode = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
                             "-map", "0:v:0", "-f", "null", "-"], capture_output=True)
    if decode.returncode:
        raise ValueError("original camera full decode failed")
    return sha(path)


def audit_saved(attempt, case_id, review=None, diagnostic=False):
    attempt = Path(attempt)
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("exact cycle signal case required")
    provenance = json.loads((attempt / "fixture-provenance.json").read_text()) if (
        attempt / "fixture-provenance.json").is_file() else None
    if provenance is not None and not diagnostic:
        raise ValueError("original saved acquisition required for physical review")
    result = json.loads((attempt / "result.json").read_text())
    if result.get("case_id") != case_id:
        raise ValueError("saved result case mismatch")
    signal = measure(case_id=case_id, context_path=attempt / "signal-context.json",
                     trace_path=attempt / "signal-readback.jsonl",
                     receipt_path=attempt / "signal-receipt.json",
                     allow_diagnostic=diagnostic)
    frame_map = rows(attempt / "video_frames.jsonl")
    trace = rows(attempt / "trace.jsonl")
    count = len(signal["observations"])
    if count != len(frame_map) or count != len(trace) or (not diagnostic and count != 900):
        raise ValueError("original full frame count missing")
    if any(frame_map[i]["carla_frame"] != trace[i]["frame"] or
           trace[i]["frame"] != signal["observations"][i]["frame"] for i in range(count)):
        raise ValueError("original signal/trace/camera frame join failed")
    source_evidence = rows(attempt / "capture/evidence.jsonl")
    if len(source_evidence) != count:
        raise ValueError("original participant census lacks full frame coverage")
    if not diagnostic and any(len(row.get("original_observations", {}).get("participants", [])) < 2
                              for row in source_evidence):
        raise ValueError("original rider and cycle participant census incomplete")
    camera_sha = {}
    for name in CAMERAS:
        path = attempt / (name + ".mkv")
        if not path.is_file():
            raise ValueError("original camera missing: " + name)
        camera_sha[name] = audit_media(path, count)
    if not diagnostic:
        positions = [row.get("position_m") for row in trace]
        if any(not isinstance(point, list) or len(point) < 2 for point in positions) or \
                math.dist(positions[0][:2], positions[-1][:2]) < 5.0:
            raise ValueError("original physical completion not established")
        if review is None:
            raise ValueError("independent original pixel review required")
        review_doc = json.loads(Path(review).read_text())
        if review_doc.get("case_id") != case_id or review_doc.get("camera_sha256") != camera_sha or \
                review_doc.get("kind") != "independent_original_pixels" or \
                not review_doc.get("reviewer") or \
                len(review_doc.get("right_arm_visible_frames", [])) < 3:
            raise ValueError("independent original pixel review is incomplete or stale")
    return {"format": "worker-cycle-signal-source-audit", "case_id": case_id,
            "diagnostic_fixture": diagnostic, "frame_count": count,
            "signal_source_bindings": signal["source_bindings"], "camera_sha256": camera_sha,
            "checks": {"native_source": not diagnostic, "all_participants": not diagnostic,
                       "time_join": True, "full_video_decode": True,
                       "actual_pixels": not diagnostic, "physical_completion": not diagnostic},
            "legal_judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--review")
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit_saved(args.attempt, args.case, args.review, args.diagnostic),
                     sort_keys=True))


if __name__ == "__main__":
    main()
