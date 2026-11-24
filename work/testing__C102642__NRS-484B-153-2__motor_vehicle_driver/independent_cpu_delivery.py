"""Independently inspect a saved diagnostic attempt and decoded RGB streams.

This CPU proof validates packaging and source joins. A synthetic attempt can
never establish real door motion or statutory interference.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from delivery_measure import measure


KINDS = {"open_near_overlap": ("open", "left"),
         "open_near_clear": ("open", "left"),
         "open_far_side": ("open", "right"),
         "board_near": ("board", "left"),
         "alight_near": ("alight", "left")}
VIDEOS = ("overview.mkv", "approach.mkv", "reference_corner.mkv",
          "driver_reference.mkv")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit(attempt: Path, case_id: str) -> dict:
    attempt = Path(attempt)
    kind = case_id.rsplit("__", 1)[-1]
    if kind not in KINDS:
        raise ValueError("unknown exact case")
    door = attempt / "door-source.json"
    if not door.is_file():
        raise ValueError("Missing required source: door-source.json")
    intent = json.loads(door.read_text())
    original = attempt / "native-trace.json"
    if not original.is_file():
        raise ValueError("Missing required source: native-trace.json")
    trace = json.loads(original.read_text())
    if (intent.get("case_id") != case_id or
            intent.get("source_trace_sha256") != sha(original) or
            (intent.get("selected_act"), intent.get("selected_side")) != KINDS[kind]):
        raise ValueError("door action is not source-bound to the exact case")
    measured = measure(trace, expected_case_id=case_id,
                       expected_act=intent["selected_act"],
                       expected_side=intent["selected_side"])
    result = json.loads((attempt / "result.json").read_text())
    report = json.loads((attempt / "analysis-report.json").read_text())
    if (result.get("case_id") != case_id or
            result.get("measured_values") != measured or
            report.get("case_id") != case_id or
            result.get("maneuver_completed") is not False or
            result.get("setup_confirmed") is not False):
        raise ValueError("saved result changed the original measurement or physical scope")
    ordinary = rows(attempt / "trace.jsonl")
    mapping = rows(attempt / "video_frames.jsonl")
    evidence = rows(attempt / "capture/evidence.jsonl")
    native = rows(attempt / "capture/native/frames.jsonl")
    count = len(trace["frames"])
    if count < 3 or any(len(items) != count for items in (ordinary, mapping, evidence, native)):
        raise ValueError("saved Native, telemetry, evidence and video frame counts differ")
    for index, (source, telemetry, video, proof, frame) in enumerate(
            zip(trace["frames"], ordinary, mapping, evidence, native)):
        original_id = source["frame_id"]
        if (telemetry["frame"] != original_id or
                video["carla_frame"] != original_id or
                video["native_frame"] != original_id or
                video["video_frame"] != index or
                proof["original_frame"] != original_id or
                proof["replay_frame"] != original_id or
                frame["frame"] != original_id or
                abs(telemetry["time_s"] - source["sim_time_s"]) > 1e-6 or
                abs(video["time_s"] - source["sim_time_s"]) > 1e-6 or
                abs(proof["recording_time_s"] - source["sim_time_s"]) > 1e-6 or
                abs(frame["simulation_time"] - source["sim_time_s"]) > 1e-6):
            raise ValueError("saved original frame join differs")
        graph = attempt / "capture/native" / frame["adapter_graph"]
        if not graph.is_file():
            raise ValueError("saved original adapter graph is missing")
    decoded = {}
    for video in VIDEOS:
        path = attempt / video
        command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                   "-i", str(path), "-f", "framemd5", "-"]
        process = subprocess.run(command, capture_output=True, text=True, timeout=120)
        if process.returncode:
            raise ValueError("video pixel decoding failed: " + video)
        pixels = [line for line in process.stdout.splitlines()
                  if line and not line.startswith("#")]
        if len(pixels) != count:
            raise ValueError("decoded camera count differs: " + video)
        decoded[video] = hashlib.sha256("\n".join(pixels).encode()).hexdigest()
    provenance = json.loads((attempt / "acquisition-provenance.json").read_text())
    return {"format": "worker-independent-diagnostic-delivery-audit",
            "case_id": case_id, "source_sha256": {"door-source.json": sha(door),
                                               "native-trace.json": sha(original)},
            "frame_count": count, "decoded_rgb_streams": decoded,
            "source_join_checked": True,
            "physical_completion_checked": True,
            "physical_completion_status": "unverified_synthetic_fixture",
            "diagnostic_fixture": bool(provenance.get("diagnostic_fixture")),
            "legal_interference": "unresolved_judgment"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = audit(args.attempt, args.case_id)
    args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
