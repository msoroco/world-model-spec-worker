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


def measure(samples: list[dict], source_path: Path, expected_sha256: str, boundary_x_m: float, one_way: bool, zone_kind: str) -> dict:
    if sha256(source_path) != expected_sha256:
        raise ValueError("Original Native sample source hash differs")
    if len(samples) < 2:
        raise ValueError("Insufficient original Native samples")
    left = []
    previous = None
    previous_native = None
    for index, sample in enumerate(samples):
        native_frame = sample.get("native_frame")
        if sample.get("video_frame") != index or type(native_frame) is not int or (
            previous_native is not None and native_frame != previous_native + 1
        ):
            raise ValueError("Original video/Native frame join differs")
        previous_native = native_frame
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
        if sample.get("one_way_native_survey") is not one_way or sample.get("two_way_native_survey") is not (not one_way):
            raise ValueError("Native direction survey differs from statutory alternative")
        # Body fully across the centerline, in the incoming road before its
        # intersection boundary. The closest front corner governs distance.
        if min(p[1] for p in vertices) > 0 and max(p[0] for p in vertices) < boundary_x_m and speed > .05:
            front = max(p[0] for p in vertices)
            left.append({"frame": index, "distance_to_intersection_m": boundary_x_m - front})
    if not left:
        raise ValueError("No observed driven full-body left-side interval")
    nearest = min(row["distance_to_intersection_m"] for row in left)
    return {"source_sha256": expected_sha256, "source_kind": "source_hashed_native_sample_schema",
            "left_driving_frames": len(left), "nearest_body_front_to_zone_m": nearest,
            "zone_kind":zone_kind,"one_way_native_survey":one_way,"boundary_x_m":boundary_x_m,
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
    print(json.dumps(measure(json.loads(args.source.read_text()), args.source, args.sha256, -7.0, False, "intersection")))


if __name__ == "__main__":
    main()
