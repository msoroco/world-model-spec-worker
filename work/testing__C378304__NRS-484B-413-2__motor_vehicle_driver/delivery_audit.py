"""Independent exact-case audit of original signal, camera and motion sources."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from native_capture_contract import CAMERAS
from source_audit import audit as audit_png_sources


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(attempt: str | Path, case_id: str, *, diagnostic_test: bool = False) -> dict:
    from worker_exchange.media import audit as audit_video
    from worker_exchange.native_output import assess_physical

    root = Path(attempt)
    original = audit_png_sources(root, case_id, allow_diagnostic=diagnostic_test)
    if original["diagnostic_fixture"] is not diagnostic_test:
        raise ValueError("original or diagnostic provenance differs")
    packet = json.loads((root / "original-turn-signal.json").read_text())
    rows = packet["samples"]
    mapping = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
    trace = [json.loads(line) for line in (root / "trace.jsonl").read_text().splitlines()]
    if len(rows) != len(mapping) or len(trace) != len(rows):
        raise ValueError("original frame count or trace join differs")
    for index, (row, frame, state) in enumerate(zip(rows, mapping, trace)):
        if (frame.get("video_frame") != index or frame.get("carla_frame") != row["frame"] or
                state.get("frame") != row["frame"] or
                not math.isclose(frame.get("time_s", math.inf), row["time_s"], abs_tol=1e-4) or
                not math.isclose(state.get("time_s", math.inf), row["time_s"], abs_tol=1e-4)):
            raise ValueError("original frame/time identity differs")
    acquisition = json.loads((root / "acquisition.json").read_text())
    for name in ("original-site.json", "original-turn-signal.json", "trace.jsonl",
                 "video_frames.jsonl", "body_history.jsonl", *[view + ".mkv" for view in CAMERAS]):
        if acquisition.get(name, {}).get("sha256") != sha(root / name):
            raise ValueError("missing or stale original source: " + name)
    video = {}
    for name in CAMERAS:
        source = root / (name + ".mkv")
        decoded = audit_video(source, len(rows), mapping_sha256=sha(root / "video_frames.jsonl"))
        if decoded.get("passed") is not True:
            raise ValueError("full video decode failed: " + name)
        video[name] = {"sha256": sha(source), "frames": decoded["frames"],
                       "rgb_sequence_sha256": decoded["rgb_sequence_sha256"]}
    config = json.loads((root / "config.json").read_text())
    if config.get("selected_case_id") != case_id:
        raise ValueError("exact case configuration differs")
    motion = assess_physical(root, config)["physical_checks"]["maneuver"]
    if not diagnostic_test:
        seal = json.loads((root / "capture-seal.json").read_text())
        if (seal.get("format") != "worker-sealed-capture" or
                seal.get("provenance_kind") != "native" or seal.get("frames") != len(rows) or
                seal.get("restoration", {}).get("restored") is not True):
            raise ValueError("original capture seal or restoration differs")
        for name, expected in seal.get("sources", {}).items():
            if sha(root / name) != expected:
                raise ValueError("sealed original source changed: " + name)
        if motion["status"] != "met":
            raise ValueError("original physical right turn incomplete or unverified")
    return {"format": "worker-delivery-audit", "case_id": case_id,
            "checks": ["native_source", "all_participants", "time_join", "full_video_decode",
                       "actual_pixels", "physical_completion"],
            "original_source_audit": original, "frame_count": len(rows),
            "video_sources": video, "physical_completion": motion,
            "diagnostic_fixture": diagnostic_test, "physical_acceptance_claimed": False,
            "legal_verdict_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--diagnostic-test", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case, diagnostic_test=args.diagnostic_test),
                     sort_keys=True))
