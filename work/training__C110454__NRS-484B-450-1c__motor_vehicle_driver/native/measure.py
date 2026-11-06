"""Saved 20 Hz source-bound footprint and stop measurement for NRS 484B.450(1)(c)."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
from geometry import overlap_area_xy


def measure(source: Path, expected_sha256: str) -> dict:
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Saved source hash differs")
    rows = [json.loads(line) for line in raw.splitlines()]
    if len(rows) != 480:
        raise ValueError("Exact 480-frame source required")
    overlaps = []
    parked = []
    prior_native = None
    prior_time = None
    for i, row in enumerate(rows):
        if row.get("video_frame") != i or type(row.get("native_frame")) is not int:
            raise ValueError("Video and Native frame join differs")
        if prior_native is not None and row["native_frame"] != prior_native + 1:
            raise ValueError("Native frame gap")
        prior_native = row["native_frame"]
        timestamp = row.get("time_s")
        if type(timestamp) not in (int, float) or not math.isfinite(timestamp) or timestamp < 0:
            raise ValueError("Native timestamp absent")
        if prior_time is not None and abs(timestamp - prior_time - .05) > 1e-6:
            raise ValueError("20 Hz source timing differs")
        prior_time = timestamp
        vertices = row.get("body_xy_m")
        if not isinstance(vertices, list) or len(vertices) != 4 or any(
            not isinstance(v, list) or len(v) != 2 or any(
                type(c) not in (int, float) or not math.isfinite(c) for c in v)
            for v in vertices):
            raise ValueError("Original four-corner body footprint absent")
        speed = row.get("speed_m_s")
        if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
            raise ValueError("Original speed absent")
        if row.get("native_intersection_survey") is not True:
            raise ValueError("Native intersection survey absent")
        exceptions = row.get("exceptions")
        if not isinstance(exceptions, dict) or set(exceptions) != {
            "traffic_conflict", "lawful_direction", "police_direction", "traffic_device"} or any(
                type(v) is not bool for v in exceptions.values()):
            raise ValueError("Exception observations absent")
        if speed <= .05:
            parked.append(i)
            if any(exceptions.values()):
                raise ValueError("Unexcluded exception at sampled parking frame")
            overlaps.append(overlap_area_xy(vertices))
    if len(parked) < 40 or parked[-1] != 479:
        raise ValueError("Sustained parking observation absent")
    return {"source_sha256": expected_sha256, "source_kind": "source_hashed_native_sample_schema",
            "parked_frames": len(parked), "parked_duration_s": len(parked) / 20,
            "max_intersection_body_overlap_m2": round(max(overlaps), 5),
            "parking_relation": "within_intersection" if max(overlaps) > 0 else "outside_intersection",
            "exception_flags_all_false": True,
            "scope": "sampled geometry and saved schema; no intersample or legal verdict",
            "legal_verdict": None}


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(); p.add_argument("source", type=Path); p.add_argument("--sha256", required=True)
    a = p.parse_args(); print(json.dumps(measure(a.source, a.sha256), indent=2))
