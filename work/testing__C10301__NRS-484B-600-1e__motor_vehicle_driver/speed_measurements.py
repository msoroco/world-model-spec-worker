"""Source-bound sampled speed measurements for NRS 484B.600(1)(e).

The exact statutory boundary is 80 mph. A sampled maximum cannot establish a
between-sample maximum or the legal character of the road/vehicle operation.
"""

import hashlib
import json
import math
from pathlib import Path


MPH_TO_MPS = 0.44704
BOUNDARY_MPS = 80 * MPH_TO_MPS
REQUIRED = ("subject_motion.jsonl", "video_frames.jsonl", "road_context.json")


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Missing finite " + label)
    return float(value)


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(root: Path) -> dict:
    root = Path(root)
    sources = {}
    for name in REQUIRED:
        path = root / name
        if not path.is_file():
            raise ValueError("Missing required source: " + name)
        sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    context = json.loads((root / "road_context.json").read_text())
    for key in ("native_map_id", "subject_actor_id", "subject_blueprint_id",
                "route_source", "alley_source", "access_aisle_source"):
        if not context.get(key):
            raise ValueError("Missing Native subject/road context: " + key)
    motion, frames = _rows(root / "subject_motion.jsonl"), _rows(root / "video_frames.jsonl")
    if len(motion) < 2 or len(motion) != len(frames):
        raise ValueError("Incomplete motion/frame history")
    previous = (-1, -math.inf)
    samples = []
    for index, (row, frame) in enumerate(zip(motion, frames)):
        fid, time = row.get("frame"), _number(row.get("time_s"), "time")
        if type(fid) is not int or fid <= previous[0] or time <= previous[1]:
            raise ValueError("Nonmonotone original motion history")
        previous = (fid, time)
        if frame.get("video_frame") != index or frame.get("carla_frame") != fid or frame.get("time_s") != time:
            raise ValueError("Original frame/time join failed")
        if row.get("subject_actor_id") != context["subject_actor_id"] or row.get("speed_source") != "actor.get_velocity":
            raise ValueError("Subject identity or original velocity source mismatch")
        velocity = row.get("velocity_mps")
        if not isinstance(velocity, list) or len(velocity) != 3:
            raise ValueError("Missing complete Native velocity")
        xyz = [_number(value, "velocity component") for value in velocity]
        speed_mps = math.sqrt(sum(value * value for value in xyz))
        if "speed_mps" in row and abs(_number(row["speed_mps"], "speed") - speed_mps) > 1e-5:
            raise ValueError("Reported speed and Native velocity disagree")
        samples.append({"frame": fid, "time_s": time, "speed_mps": speed_mps,
                        "speed_mph": speed_mps / MPH_TO_MPS})
    peak = max(samples, key=lambda sample: sample["speed_mps"])
    return {"format": "worker-absolute-speed-samples", "sources": sources,
            "subject_actor_id": context["subject_actor_id"],
            "statutory_boundary_mps": BOUNDARY_MPS, "statutory_boundary_mph": 80.0,
            "peak_sample": peak,
            "sampled_peak_greater_than_80_mph": peak["speed_mps"] > BOUNDARY_MPS,
            "samples": samples,
            "between_sample_peak": "unresolved",
            "road_public_way_judgment": "unresolved",
            "legal_conclusion": "unresolved"}
