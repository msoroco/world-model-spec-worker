"""Source-bound CPU measurement of the proposed intersection approach.

This measures saved original-frame polygons. It does not infer a legal verdict.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

BOUNDARY_X_M = -7.0
APPROACH_M = 30.48


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure(samples: list[dict], source_path: Path, expected_sha256: str) -> dict:
    if sha256(source_path) != expected_sha256:
        raise ValueError("Original Native sample source hash differs")
    if len(samples) < 2:
        raise ValueError("Insufficient original Native samples")
    left = []
    previous = None
    for index, sample in enumerate(samples):
        if sample.get("video_frame") != index or sample.get("native_frame") != index:
            raise ValueError("Original video/Native frame join differs")
        t = sample.get("time_s")
        if not isinstance(t, (int, float)) or not math.isfinite(t):
            raise ValueError("Invalid original Native timestamp")
        if previous is not None and abs(t - previous - .05) > 1e-6:
            raise ValueError("Missing or mistimed original Native sample")
        previous = t
        vertices = sample.get("body_xy_m")
        if not isinstance(vertices, list) or len(vertices) != 4 or any(
            not isinstance(p, list) or len(p) != 2 or any(
                not isinstance(v, (float, int)) or not math.isfinite(v) for v in p)
            for p in vertices
        ):
            raise ValueError("Missing original full-body footprint")
        speed = sample.get("speed_m_s")
        if not isinstance(speed, (float, int)) or speed < 0 or not math.isfinite(speed):
            raise ValueError("Missing observed speed")
        if sample.get("two_way_native_survey") is not True:
            raise ValueError("Two-way Native direction survey is required")
        # Body fully across the centerline, in the incoming road before its
        # intersection boundary. The closest front corner governs distance.
        if min(p[1] for p in vertices) > 0 and max(p[0] for p in vertices) < BOUNDARY_X_M and speed > .05:
            front = max(p[0] for p in vertices)
            left.append({"frame": index, "distance_to_intersection_m": BOUNDARY_X_M - front})
    if not left:
        raise ValueError("No observed driven full-body left-side interval")
    nearest = min(row["distance_to_intersection_m"] for row in left)
    return {"source_sha256": expected_sha256, "source_kind": "source_hashed_native_sample_schema",
            "left_driving_frames": len(left), "nearest_body_front_to_intersection_m": nearest,
            "approach_threshold_m": APPROACH_M,
            "sampled_relation": "within_100_ft" if nearest < APPROACH_M else "outside_100_ft",
            "uncertainty": "50 ms sampling; intersample and physical map uncertainty remain",
            "legal_verdict": None}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(measure(json.loads(args.source.read_text()), args.source, args.sha256)))


if __name__ == "__main__":
    main()
