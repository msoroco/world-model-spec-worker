"""Source-bound bicycle speed and contemporaneous-condition measurements.

This is a saved-data checker. It does not decide what speed is prudent.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


REQUIRED_CONTEXT = ("jurisdiction", "bicycle_classification", "alley_route", "rack_geometry")
REQUIRED_CONDITIONS = ("weather", "surface", "visibility", "pedestrians", "curvature")


def _read_source(root: Path, entry: dict) -> dict:
    rel = Path(entry["path"])
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("source path must stay within acquisition")
    source = (root / rel).resolve()
    if not source.is_relative_to(root.resolve()) or not source.is_file():
        raise ValueError("missing required source: " + str(rel))
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise ValueError("stale required source: " + str(rel))
    return json.loads(data)


def measure(root: Path, inventory: dict, expected_case_id: str) -> dict:
    """Check source joins and retain all measured samples, without a verdict."""
    if inventory.get("case_id") != expected_case_id:
        raise ValueError("case identity mismatch")
    if inventory.get("source_kind") != "original_native":
        raise ValueError("source is not original Native acquisition")
    sources = inventory.get("sources", {})
    if set(sources) != {"frame_map", "bicycle_motion", "context"}:
        raise ValueError("missing required source inventory")
    frame_map = _read_source(root, sources["frame_map"])
    motion = _read_source(root, sources["bicycle_motion"])
    context = _read_source(root, sources["context"])
    if motion.get("case_id") != expected_case_id or context.get("case_id") != expected_case_id:
        raise ValueError("source case identity mismatch")
    frames = frame_map.get("frames")
    samples = motion.get("samples")
    if not isinstance(frames, list) or len(frames) < 2 or not isinstance(samples, list) or len(samples) != len(frames):
        raise ValueError("incomplete synchronized frame history")
    frame_ids = [row.get("frame") for row in frames]
    times = [row.get("time_s") for row in frames]
    if any(not isinstance(f, int) for f in frame_ids) or frame_ids != list(range(frame_ids[0], frame_ids[0] + len(frames))):
        raise ValueError("nonconsecutive original frame map")
    if any(not isinstance(t, (int, float)) or not math.isfinite(t) for t in times) or any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("nonmonotonic original time")
    if any(k not in context for k in REQUIRED_CONTEXT):
        raise ValueError("missing contemporaneous context")
    classification = context["bicycle_classification"]
    if classification.get("human_powered") is not True or classification.get("moped") is not False or not classification.get("source"):
        raise ValueError("bicycle classification unresolved")
    if context["jurisdiction"].get("city_of_las_vegas") is not True or not context["jurisdiction"].get("source"):
        raise ValueError("municipal jurisdiction unresolved")
    if not context["alley_route"].get("source") or not context["rack_geometry"].get("source"):
        raise ValueError("alley or rack construction unbound")
    conditions = context.get("samples")
    if not isinstance(conditions, list) or len(conditions) != len(frames):
        raise ValueError("missing contemporaneous condition history")
    for frame, t, row in zip(frame_ids, times, conditions):
        if row.get("frame") != frame or row.get("time_s") != t:
            raise ValueError("condition/frame time join mismatch")
        if any(key not in row for key in REQUIRED_CONDITIONS):
            raise ValueError("missing contemporaneous condition")
    output = []
    for frame, t, sample in zip(frame_ids, times, samples):
        if sample.get("frame") != frame or sample.get("time_s") != t:
            raise ValueError("motion/frame time join mismatch")
        velocity = sample.get("velocity_mps")
        if not isinstance(velocity, list) or len(velocity) != 3 or any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in velocity):
            raise ValueError("missing finite bicycle velocity")
        output.append({"frame": frame, "time_s": t, "speed_mps": math.sqrt(sum(x * x for x in velocity))})
    return {
        "format": "c10307-bicycle-speed-measurement",
        "case_id": expected_case_id,
        "source_kind": "original_native",
        "sources": sources,
        "samples": output,
        "context": {key: context[key] for key in REQUIRED_CONTEXT},
        "condition_samples": conditions,
        "summary": {"sample_count": len(output), "mean_speed_mps": sum(row["speed_mps"] for row in output) / len(output), "maximum_speed_mps": max(row["speed_mps"] for row in output)},
        "legal_prudence": "unresolved",
    }


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--inventory", type=Path, required=True)
    p.add_argument("--case", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = measure(args.root, json.loads(args.inventory.read_text()), args.case)
    if args.output.exists():
        raise ValueError("refusing to overwrite saved measurement")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
