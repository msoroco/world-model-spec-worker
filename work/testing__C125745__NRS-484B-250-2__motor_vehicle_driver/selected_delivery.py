"""Independent selected timing-source and decoded-video audit."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from entry_timing import measure

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decode(path, count):
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-count_frames", "-show_entries", "stream=width,height,nb_read_frames",
                            "-of", "json", str(path)], capture_output=True, text=True, check=True)
    streams = json.loads(probe.stdout).get("streams", [])
    if len(streams) != 1 or int(streams[0]["nb_read_frames"]) != count or \
            min(int(streams[0]["width"]), int(streams[0]["height"])) < 16:
        raise ValueError("timing media frame/pixel inventory differs")
    decoded = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path),
                              "-map", "0:v:0", "-f", "framemd5", "-"],
                             capture_output=True, text=True, check=True)
    pixels = [line for line in decoded.stdout.splitlines()
              if line and not line.startswith("#")]
    if len(pixels) != count:
        raise ValueError("timing media decoded pixels incomplete")
    return {"sha256": sha(path), "frames": count,
            "pixel_digest_sha256": hashlib.sha256(decoded.stdout.encode()).hexdigest()}


def audit(attempt, case_id, allow_diagnostic=False):
    attempt = Path(attempt).resolve()
    config = json.loads((attempt / "config.json").read_text())
    construction = json.loads((attempt / "construction.json").read_text())
    result = json.loads((attempt / "result.json").read_text())
    if config.get("selected_case_id") != case_id or construction.get("case_id") != case_id or result.get("case_id") != case_id:
        raise ValueError("selected timing delivery identity changed")
    source = attempt / "original-attempt/entry-timing-source.json"
    packet = json.loads(source.read_text())
    diagnostic = packet.get("diagnostic_fixture") is True
    if diagnostic and not allow_diagnostic:
        raise ValueError("synthetic saved source cannot satisfy original delivery")
    if packet.get("source_kind") != ("synthetic_fixture" if diagnostic else "original_native"):
        raise ValueError("timing source provenance changed")
    count = 9 if diagnostic else 900
    measurement = measure(source, sha(source), case_id=case_id, expected_frames=count)
    traces = [json.loads(line) for line in (attempt / "trace.jsonl").read_text().splitlines() if line]
    mapping = [json.loads(line) for line in (attempt / "video_frames.jsonl").read_text().splitlines() if line]
    if len(traces) != count or len(mapping) != count or any(
            a.get("frame") != b.get("carla_frame") or a.get("time_s") != b.get("time_s") or
            (not diagnostic and (a.get("frame") != c.get("frame") or
                                 a.get("time_s") != c.get("time_s")))
            for a, b, c in zip(traces, mapping, packet["frames"])):
        raise ValueError("selected timing trace/video join differs")
    media = {name: decode(attempt / (name + ".mkv"), count) for name in VIEWS}
    media["raw"] = decode(attempt / "raw.mkv", count)
    return {"format": "worker-selected-entry-timing-delivery-audit",
            "case_id": case_id,
            "checks_executed": ["native_source", "all_participants", "time_join",
                                "full_video_decode", "actual_pixels", "physical_completion"],
            "diagnostic_fixture": diagnostic,
            "source_sha256": sha(source), "measurement": measurement,
            "media": media, "physical_acceptance_claimed": False,
            "legal_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--allow-diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case, args.allow_diagnostic), sort_keys=True))
