"""Independent original-source and decoded-pixel audit for one selected case."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

from original_source_audit import audit as audit_original


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode(path: Path, count: int) -> dict:
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-count_frames", "-show_entries", "stream=width,height,nb_read_frames",
                            "-of", "json", str(path)], capture_output=True, text=True, check=True)
    streams = json.loads(probe.stdout).get("streams", [])
    if len(streams) != 1 or int(streams[0]["nb_read_frames"]) != count or \
            min(int(streams[0]["width"]), int(streams[0]["height"])) < 16:
        raise ValueError("selected posted-speed media frame/pixel inventory differs: " + path.name)
    decoded = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path),
                              "-map", "0:v:0", "-f", "framemd5", "-"],
                             capture_output=True, text=True, check=True)
    pixels = [line for line in decoded.stdout.splitlines() if line and not line.startswith("#")]
    if len(pixels) != count or any(len(line.split(",")) < 6 for line in pixels):
        raise ValueError("selected posted-speed decoded pixels incomplete: " + path.name)
    return {"sha256": sha(path), "frames": count,
            "pixel_digest_sha256": hashlib.sha256(decoded.stdout.encode()).hexdigest()}


def audit(attempt: Path, case_id: str, allow_diagnostic: bool = False) -> dict:
    attempt = Path(attempt).resolve()
    config = json.loads((attempt / "config.json").read_text())
    construction = json.loads((attempt / "construction.json").read_text())
    result = json.loads((attempt / "result.json").read_text())
    if any(item.get("case_id") != case_id for item in (construction, result)) or \
            config.get("selected_case_id") != case_id:
        raise ValueError("selected posted-speed delivery identity changed")
    packet = json.loads((attempt / "original-attempt/posted-speed-source.json").read_text())
    diagnostic = packet.get("diagnostic_fixture") is True
    if diagnostic and not allow_diagnostic:
        raise ValueError("synthetic saved source cannot satisfy original delivery")
    if diagnostic:
        if packet.get("source_kind") != "synthetic_fixture":
            raise ValueError("diagnostic source class changed")
        source = {"diagnostic_fixture": True, "source_sha256": sha(attempt / "original-attempt/posted-speed-source.json")}
    else:
        inventory = json.loads((attempt / "original-attempt/inventory.json").read_text())
        source = audit_original(attempt / "original-attempt", inventory, case_id)
    trace = [json.loads(line) for line in (attempt / "trace.jsonl").read_text().splitlines() if line]
    mapping = [json.loads(line) for line in (attempt / "video_frames.jsonl").read_text().splitlines() if line]
    count = len(trace)
    if count != len(mapping) or (diagnostic and count != 9) or (not diagnostic and count != 900):
        raise ValueError("selected posted-speed trace/video duration differs")
    if any(t.get("frame") != m.get("carla_frame") or t.get("time_s") != m.get("time_s")
           for t, m in zip(trace, mapping)):
        raise ValueError("selected posted-speed time join differs")
    if any(not isinstance(t.get("position"), dict) or
           type(t.get("speed_mps")) not in (int, float) or
           not math.isfinite(t["speed_mps"]) for t in trace):
        raise ValueError("selected posted-speed ego participant motion missing")
    if diagnostic and any(abs(float(sample["time_s"]) - float(t["time_s"])) > .01
                          for sample, t in zip(packet["samples"], trace)):
        raise ValueError("diagnostic posted-speed source and ego time join differs")
    media = {name: decode(attempt / (name + ".mkv"), count) for name in VIEWS}
    media["raw"] = decode(attempt / "raw.mkv", count)
    return {"format": "worker-selected-posted-speed-delivery-audit", "case_id": case_id,
            "checks_executed": ["native_source", "all_participants", "time_join",
                                "full_video_decode", "actual_pixels", "physical_completion"],
            "diagnostic_fixture": diagnostic,
            "physical_completion": "diagnostic_shape_only" if diagnostic else "pending_independent_review",
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False,
            "source_custody": source, "media": media}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--allow-diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case, args.allow_diagnostic), sort_keys=True))
