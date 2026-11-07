"""Controlled intersection traversal proposal and source-bound saved-frame measure."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from geometry import BODY_HALF_LENGTH_M, BODY_HALF_WIDTH_M, check as check_map

ENTRY_X = -7.0
EXIT_X = 7.0
RATE_HZ = 20
FRAMES = 480


def smooth(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def pose(case: str, frame: int) -> tuple[float, float]:
    if case not in ("traversal_reference", "traversal_contrast") or not 0 <= frame < FRAMES:
        raise ValueError("Unknown traversal case or frame")
    x = -70.0 + min(frame, 399) * 90.0 / 399.0
    y = -1.75
    if case == "traversal_contrast":
        y += 3.5 * smooth((x + 20.0) / 5.0)
        y -= 3.5 * smooth((x - 10.0) / 5.0)
    y -= 3.5 * smooth((x - 12.0) / 8.0)
    return x, y


def body(x: float, y: float) -> list[list[float]]:
    return [[x + dx, y + dy] for dx, dy in
            ((-BODY_HALF_LENGTH_M, -BODY_HALF_WIDTH_M),
             (-BODY_HALF_LENGTH_M, BODY_HALF_WIDTH_M),
             (BODY_HALF_LENGTH_M, BODY_HALF_WIDTH_M),
             (BODY_HALF_LENGTH_M, -BODY_HALF_WIDTH_M))]


def synthetic_samples(case: str) -> list[dict]:
    """CPU proposal only; these rows are never original Native evidence."""
    rows = []
    for frame in range(FRAMES):
        x, y = pose(case, frame)
        prior_x, prior_y = pose(case, max(0, frame - 1))
        speed = math.hypot(x-prior_x, y-prior_y) * RATE_HZ
        rows.append({"video_frame": frame, "native_frame": 1000 + frame,
                     "time_s": frame / RATE_HZ, "body_xy_m": body(x, y),
                     "speed_m_s": speed, "two_way_native_survey": True,
                     "source_kind": "synthetic_cpu_proposal"})
    return rows


def measure(rows: list[dict], source: Path, expected_sha256: str) -> dict:
    if hashlib.sha256(source.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError("Saved frame source hash differs")
    if json.loads(source.read_text()) != rows or len(rows) != FRAMES:
        raise ValueError("Saved frame rows differ")
    traversal = []
    left = []
    previous_native = None
    for frame, row in enumerate(rows):
        if row.get("video_frame") != frame or type(row.get("native_frame")) is not int:
            raise ValueError("Frame identity differs")
        if previous_native is not None and row["native_frame"] != previous_native + 1:
            raise ValueError("Native frame join differs")
        previous_native = row["native_frame"]
        if abs(row.get("time_s", -1) - frame / RATE_HZ) > 1e-8:
            raise ValueError("Frame time differs")
        if row.get("two_way_native_survey") is not True:
            raise ValueError("Two-way survey absent")
        points = row.get("body_xy_m")
        if not isinstance(points, list) or len(points) != 4 or any(
            not isinstance(p, list) or len(p) != 2 or any(
                type(v) not in (int, float) or not math.isfinite(v) for v in p)
            for p in points
        ):
            raise ValueError("Full-body polygon absent")
        speed = row.get("speed_m_s")
        if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
            raise ValueError("Observed speed absent")
        if min(p[0] for p in points) > ENTRY_X and max(p[0] for p in points) < EXIT_X and speed > .05:
            traversal.append(frame)
            if min(p[1] for p in points) > 0:
                left.append(frame)
    if not traversal:
        raise ValueError("No moving full body within intersection")
    return {"source_sha256": expected_sha256, "moving_traversal_frames": len(traversal),
            "moving_left_traversal_frames": len(left),
            "first_traversal_frame": traversal[0], "last_traversal_frame": traversal[-1],
            "first_left_traversal_frame": left[0] if left else None,
            "last_left_traversal_frame": left[-1] if left else None,
            "source_kind": rows[0].get("source_kind"), "legal_verdict": None}


def check_pair() -> dict:
    from shapely.geometry import Polygon, box
    from shapely.ops import unary_union
    check_map()
    pavement = unary_union((box(-100, -3.5, 100, 3.5),
                            box(-3.5, -100, 3.5, 100),
                            box(8, -7, 35, -3.5)))
    result = {}
    for case in ("traversal_reference", "traversal_contrast"):
        rows = synthetic_samples(case)
        if not all(pavement.covers(Polygon(row["body_xy_m"])) for row in rows):
            raise ValueError("Proposed full body leaves authored pavement")
        moving = [r for r in rows if -7 < min(p[0] for p in r["body_xy_m"])
                  and max(p[0] for p in r["body_xy_m"]) < 7 and r["speed_m_s"] > .05]
        left = [r for r in moving if min(p[1] for p in r["body_xy_m"]) > 0]
        result[case] = {"moving_traversal_frames": len(moving),
                        "moving_left_traversal_frames": len(left),
                        "parking_end_xy_m": pose(case, FRAMES - 1)}
    if result["traversal_reference"]["moving_left_traversal_frames"] != 0:
        raise ValueError("Reference has left-side traversal")
    if result["traversal_contrast"]["moving_left_traversal_frames"] < 10:
        raise ValueError("Contrast lacks sustained left-side traversal")
    if result["traversal_reference"]["parking_end_xy_m"] != result["traversal_contrast"]["parking_end_xy_m"]:
        raise ValueError("Parking endpoint differs")
    return {"scope": "authored CPU proposal", "cases": result,
            "native_original_verified": False, "legal_verdict": None}
