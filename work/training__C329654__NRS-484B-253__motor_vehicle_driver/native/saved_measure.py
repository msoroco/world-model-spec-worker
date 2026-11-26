"""Source-bound saved analysis for left-turn sequence diagnostics.

This checks joins and measured actor histories. Canonical conversion and actual
pixel audits are separate later steps and cannot be inferred from this output.
"""
import argparse
import hashlib
import json
from pathlib import Path

from observed_left_turn import FRAMES, measure


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    if not path.is_file():
        raise ValueError("Missing saved original source: " + path.name)
    records = [json.loads(line) for line in path.read_text().splitlines()]
    if len(records) != FRAMES:
        raise ValueError("Incomplete saved frame source: " + path.name)
    return records


def analyze(attempt, output):
    attempt = Path(attempt)
    config_path = attempt / "config.json"
    if not config_path.is_file():
        raise ValueError("Missing saved original source: config.json")
    config = json.loads(config_path.read_text())
    actor_path = attempt / "left-turn-actors.jsonl"
    actor_rows = read_rows(actor_path)
    measured = measure(actor_path)
    if config.get("case_id") != measured["case_id"]:
        raise ValueError("Saved config and actor case identity differ")
    maps = read_rows(attempt / "video_frames.jsonl")
    camera_rows = read_rows(attempt / "camera-frames.jsonl")
    if not (attempt / "road.xodr").is_file():
        raise ValueError("Missing saved original source: road.xodr")
    for index, (actor, frame, camera) in enumerate(zip(actor_rows, maps, camera_rows)):
        native = actor["native_frame"]
        if (frame.get("native_frame") != native or camera.get("native_frame") != native
                or frame.get("video_frame") != index or camera.get("frame") != index):
            raise ValueError("Saved actor and camera frame join differs")
        camera_frames = frame.get("camera_native_frames")
        if not isinstance(camera_frames, dict) or set(camera_frames) != set(CAMERAS) or any(
                camera_frames[name] != native for name in CAMERAS):
            raise ValueError("Four synchronized camera frames required")
        hashes = camera.get("rgb_sha256")
        if not isinstance(hashes, dict) or set(hashes) != set(CAMERAS) or any(
                not isinstance(hashes[name], str) or len(hashes[name]) != 64 for name in CAMERAS):
            raise ValueError("Missing four original camera pixel hashes")
    sources = {name: sha(attempt / name) for name in (
        "config.json", "left-turn-actors.jsonl", "video_frames.jsonl",
        "camera-frames.jsonl", "road.xodr")}
    fixed = {name: config.get(name) for name in (
        "law_id", "cell_id", "actor", "rate_hz", "duration_s", "duration_frames",
        "cameras", "oncoming_conflict_s", "left_signal_requested")}
    if (fixed["law_id"], fixed["cell_id"], fixed["actor"], fixed["rate_hz"],
            fixed["duration_s"], fixed["duration_frames"]) != (
            "NRS-484B-253", "C329654", "motor_vehicle_driver", 20, 30, 600):
        raise ValueError("Saved fixed law, actor, rate or duration differs")
    if not isinstance(fixed["cameras"], list) or [camera.get("name") for camera in fixed["cameras"]] != list(CAMERAS):
        raise ValueError("Saved four-view contract differs")
    report = {"format": "c329654-left-turn-saved-measurement-v1",
              "case_id": measured["case_id"], "source_kind": measured["source_kind"],
              "sources": sources, "measured": measured, "fixed_conditions": fixed,
              "requested_turn_policy": config.get("yield_policy"),
              "actual_pixels_reviewed": False, "legal_priority_verdict": None,
              "physical_acceptance_claimed": False}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.attempt, args.output), sort_keys=True))
