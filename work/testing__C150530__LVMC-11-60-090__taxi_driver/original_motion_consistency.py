"""Crosscheck independent Native taxi pose and controller acquisitions.

This is a saved-source consistency proof. It cannot authenticate the sources or
establish legal applicability, visibility, or physical acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from delivery_audit import audit_source_chain
from taxi_cameras import NAMES


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict]:
    try:
        data = [json.loads(line) for line in path.read_text().splitlines()]
    except json.JSONDecodeError as exc:
        raise ValueError("invalid original acquisition JSONL") from exc
    if not data:
        raise ValueError("empty original acquisition")
    return data


def finite(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError("nonfinite or absent " + field)
    return float(value)


def check(attempt: Path, case: str, map_path: Path, layout_path: Path) -> dict:
    root = Path(attempt).resolve()
    source = audit_source_chain(root, case, map_path, layout_path)
    original = rows(root / "original-trace.jsonl")
    pipeline = rows(root / "trace.jsonl")
    commands = rows(root / "taxi-controller-history.jsonl")
    mapping = rows(root / "video_frames.jsonl")
    if len({len(original), len(pipeline), len(commands), len(mapping)}) != 1:
        raise ValueError("original source lengths differ")
    for index, (pose, sample, command, frame) in enumerate(zip(original, pipeline, commands, mapping)):
        point = sample.get("position_m")
        if not isinstance(point, list) or len(point) != 3:
            raise ValueError("pipeline pose missing")
        if any(abs(finite(point[axis], "pipeline pose") - finite(pose["position_m"][axis], "original pose")) > 0.01
               for axis in range(3)):
            raise ValueError("independent Native pose differs")
        heading = finite(sample.get("heading_deg"), "pipeline heading")
        original_heading = finite(pose["yaw_deg"], "original heading")
        if abs((heading - original_heading + 180) % 360 - 180) > 2.0:
            raise ValueError("independent Native heading differs")
        if finite(sample.get("speed_mps"), "pipeline speed") < 0:
            raise ValueError("negative pipeline speed")
        issued = command.get("control")
        applied = sample.get("control")
        if not isinstance(issued, dict) or not isinstance(applied, dict):
            raise ValueError("controller or applied control absent")
        for key, low, high in (("throttle", 0, 1), ("brake", 0, 1), ("steer", -1, 1)):
            value = finite(issued.get(key), "issued " + key)
            observed = finite(applied.get(key), "applied " + key)
            if not (low <= value <= high and low <= observed <= high):
                raise ValueError("control outside Native range: " + key)
            if abs(value - observed) > 1e-4:
                raise ValueError("issued and applied control differ: " + key)
        if type(issued.get("finished")) is not bool:
            raise ValueError("controller completion flag absent")
        if frame.get("video_frame") != index:
            raise ValueError("camera frame map differs")
    return {"format": "c150530-original-motion-consistency-v1",
            "case_id": source["case_id"], "passed": True, "frames": len(original),
            "source_hashes": {name: sha(root / name) for name in
                              ("original-trace.jsonl", "trace.jsonl",
                               "taxi-controller-history.jsonl", "video_frames.jsonl",
                               *(name + ".mkv" for name in NAMES))},
            "capture_seal_sha256": source["capture_seal_sha256"],
            "physical_or_legal_acceptance": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", choices=("near_stand", "far_stand", "near_stand_straight"), required=True)
    parser.add_argument("--map", type=Path, required=True)
    parser.add_argument("--layout", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(check(args.attempt, args.case, args.map, args.layout), indent=2) + "\n")


if __name__ == "__main__":
    main()
