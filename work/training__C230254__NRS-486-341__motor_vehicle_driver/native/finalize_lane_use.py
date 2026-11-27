"""Saved-only source-shaped lane geometry finalizer (no legal verdict)."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from lane_use import measure_joined_frames


def finalize(source: Path, output: Path):
    if not source.is_file():
        raise ValueError("Native geometry source file is missing")
    rows = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    measured = measure_joined_frames(rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in measured))
    return len(measured)


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finalize_bound(attempt: Path, output: Path):
    """Join original geometry, frame map and chapter-specific survey by source.

    The survey is a retained operator source packet, never a legal finding.
    Its cited references must themselves exist and match their recorded hashes.
    """
    attempt = Path(attempt)
    source = attempt / "lane-use-source.jsonl"
    mapping = attempt / "video_frames.jsonl"
    survey_path = attempt / "lane-use-context.json"
    for path in (source, mapping, survey_path):
        if not path.is_file():
            raise ValueError("Missing required source: " + path.name)
    survey = json.loads(survey_path.read_text())
    if survey.get("source_kind") != "original_native_context_survey":
        raise ValueError("Original chapter 486 context survey missing")
    required = ("map_name", "highway_public_maintenance_source",
                "highway_public_vehicular_access_source",
                "protected_vehicle_seat_source", "protected_vehicle_wheels_source",
                "protected_vehicle_exclusions_source",
                "subject_motor_vehicle_class_source")
    if any(not survey.get(key) for key in required):
        raise ValueError("Chapter 486 highway or vehicle classification source missing")
    citations = survey.get("citations")
    if not isinstance(citations, list) or not citations:
        raise ValueError("Chapter 486 context source citations missing")
    for citation in citations:
        name, expected = citation.get("path"), citation.get("sha256")
        if not isinstance(name, str) or Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("Unsafe chapter 486 citation path")
        path = attempt / name
        if not path.is_file() or not expected or _digest(path) != expected:
            raise ValueError("Chapter 486 citation missing or changed: " + name)
    rows = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
    frames = [json.loads(line) for line in mapping.read_text().splitlines() if line.strip()]
    if not rows or len(rows) != len(frames):
        raise ValueError("Original geometry and frame map coverage differs")
    for index, (row, frame) in enumerate(zip(rows, frames)):
        if (row.get("frame") != index or row.get("video_frame") != index
                or frame.get("video_frame") != index
                or row.get("native_frame") != frame.get("native_frame")
                or row.get("time_s") != frame.get("time_s")
                or row.get("ego_actor_id") == row.get("motorcycle_actor_id")
                or row.get("source_kind") != "original_native_actor_and_map_geometry"):
            raise ValueError("Original actor, frame or time source join differs")
        cameras = frame.get("camera_native_frames")
        if (not isinstance(cameras, dict) or set(cameras) !=
                {"overview", "approach", "reference_corner", "driver_reference"}
                or any(value != row["native_frame"] for value in cameras.values())):
            raise ValueError("Four original cameras are not synchronized")
    count = finalize(source, output)
    return {"measured_frames": count,
            "sources": {name: _digest(attempt / name) for name in
                        ("lane-use-source.jsonl", "video_frames.jsonl", "lane-use-context.json")},
            "chapter_486_context_unreviewed": True,
            "legal_verdict_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps({"measured_frames": finalize(args.source, args.output)}))


if __name__ == "__main__":
    main()
