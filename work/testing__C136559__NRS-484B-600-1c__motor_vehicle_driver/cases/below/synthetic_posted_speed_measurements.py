"""Measure Native speed, or a clearly marked CPU diagnostic derivation.

Posted authority and sign governance are source facts, not inferred from a sign
actor label. The output preserves them for review and makes no legal verdict.
"""

import hashlib
import json
import math
from pathlib import Path


MPH_TO_MPS = 0.44704
REQUIRED = ("subject_motion.jsonl", "video_frames.jsonl", "sign_context.json")


def _finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Missing finite " + label)
    return float(value)


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(root: Path) -> dict:
    root = Path(root)
    hashes = {}
    for name in REQUIRED:
        path = root / name
        if not path.is_file():
            raise ValueError("Missing required source: " + name)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    context = json.loads((root / "sign_context.json").read_text())
    for key in ("native_map_id", "subject_actor_id", "governed_road_id", "sign_actor_id",
                "sign_landmark_id", "authority_source", "face_video_source",
                "governance_source", "narrow_road_source"):
        if not context.get(key):
            raise ValueError("Missing sourced posted-speed context: " + key)
    if context.get("posted_unit") != "mph":
        raise ValueError("Posted unit must be source-resolved to mph")
    posted = _finite(context.get("posted_limit_value"), "posted limit")
    start = _finite(context.get("zone_start_s_m"), "zone start")
    end = _finite(context.get("zone_end_s_m"), "zone end")
    if posted <= 0 or end <= start:
        raise ValueError("Invalid posted limit or zone extent")
    rows, frames = _rows(root / "subject_motion.jsonl"), _rows(root / "video_frames.jsonl")
    provenance_path = root / "fixture-provenance.json"
    provenance = json.loads(provenance_path.read_text()) if provenance_path.is_file() else {}
    diagnostic = provenance.get("derivation") == "constant-speed x(t), 20 Hz"
    if diagnostic:
        if not provenance.get("seed_sha256") or provenance.get("frames") != len(rows):
            raise ValueError("Synthetic diagnostic provenance incomplete")
        traces = _rows(root / "trace.jsonl")
        if len(traces) != len(rows):
            raise ValueError("Synthetic trace/frame join incomplete")
        initial_time, initial_x = traces[0]["time_s"], traces[0]["position_m"][0]
    if len(rows) < 2 or len(rows) != len(frames):
        raise ValueError("Incomplete motion/frame history")
    previous = (-1, -math.inf)
    observed = []
    for index, (row, frame) in enumerate(zip(rows, frames)):
        fid, time = row.get("frame"), _finite(row.get("time_s"), "time")
        if type(fid) is not int or fid <= previous[0] or time <= previous[1]:
            raise ValueError("Nonmonotone original history")
        previous = (fid, time)
        if frame.get("video_frame") != index or frame.get("carla_frame") != fid or frame.get("time_s") != time:
            raise ValueError("Original video frame join failed")
        expected_source = "synthetic_kinematic_derivation" if diagnostic else "actor.get_velocity"
        if row.get("subject_actor_id") != context["subject_actor_id"] or row.get("speed_source") != expected_source:
            raise ValueError("Subject velocity source/provenance mismatch")
        velocity = row.get("velocity_mps")
        if not isinstance(velocity, list) or len(velocity) != 3:
            raise ValueError("Missing Native 3D velocity")
        speed = math.sqrt(sum(_finite(v, "velocity component")**2 for v in velocity)) / MPH_TO_MPS
        road_s = _finite(row.get("road_s_m"), "road position")
        if diagnostic:
            trace = traces[index]
            if trace.get("frame") != fid or trace.get("time_s") != time:
                raise ValueError("Synthetic trace/frame join mismatch")
            expected_x = initial_x + speed * MPH_TO_MPS * (time - initial_time)
            if (abs(_finite(trace.get("position_m", [None])[0], "trace position") - expected_x) > 1e-6
                    or abs(road_s - expected_x) > 1e-6
                    or abs(_finite(trace.get("speed_mps"), "trace speed") - speed * MPH_TO_MPS) > 1e-6):
                raise ValueError("Synthetic speed and displacement disagree")
        in_zone = row.get("road_id") == context["governed_road_id"] and start <= road_s <= end
        observed.append({"frame": fid, "time_s": time, "road_id": row.get("road_id"),
                         "road_s_m": road_s, "in_signed_zone": in_zone,
                         "measured_speed_mph": speed})
    selected = [row for row in observed if row["in_signed_zone"]]
    if not selected:
        raise ValueError("No original motion in sourced posted-speed zone")
    peak = max(selected, key=lambda row: row["measured_speed_mph"])
    return {"format": "worker-posted-speed-zone-observations", "sources": hashes,
            "measurement_provenance": ("synthetic_kinematic_derivation" if diagnostic else "actor.get_velocity"),
            "measurement_method": ("synthetic constant-speed x(t) diagnostic in authored zone" if diagnostic
                                   else "original actor.get_velocity in sourced posted zone"),
            "sign_actor_id": context["sign_actor_id"],
            "sign_landmark_id": context["sign_landmark_id"],
            "posted_limit_mph": posted, "zone_start_s_m": start, "zone_end_s_m": end,
            "peak_in_zone": peak,
            "sampled_peak_greater_than_posted": peak["measured_speed_mph"] > posted,
            "samples": observed, "between_sample_peak": "unresolved",
            "public_authority_judgment": "unresolved pending source review",
            "legal_conclusion": "unresolved"}
