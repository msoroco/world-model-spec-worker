"""Measure retained left-lane and overtaking relations without a legal verdict."""

import hashlib
import json
import math
from pathlib import Path


FRAMES = 600
RATE = 20


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def measure(trace_path, context_path, expected_hashes):
    trace_path, context_path = Path(trace_path), Path(context_path)
    require(sha(trace_path) == expected_hashes[trace_path.name] and
            sha(context_path) == expected_hashes[context_path.name],
            "Sealed Native source differs")
    context = json.loads(context_path.read_text())
    rows = read_rows(trace_path)
    require(len(rows) == FRAMES and context["capture_hz"] == RATE and
            context["frames"] == FRAMES, "Complete 600-frame source required")
    require(context["source_kind"] in ("original_native", "synthetic_native_sample") and
            context["same_direction_marked_lane_count"] >= 2,
            "Source provenance or lane inventory missing")
    require(context["extreme_left_lane_id"] != context["right_lane_id"],
            "Distinct lane identifiers required")
    require(finite(context["posted_speed_limit_mps"]) and
            context["posted_speed_limit_mps"] > 0,
            "Posted speed source invalid")
    first_native = rows[0]["native_frame"]
    rear_before = []
    left_under_limit = []
    crossing = []
    prior_delta = None
    for index, row in enumerate(rows):
        require(row["frame"] == index and row["native_frame"] == first_native + index and
                finite(row["time_s"]) and abs(row["time_s"] - index / RATE) < 1e-6,
                "Native frame/time join differs")
        require(row["source_kind"] == context["source_kind"], "Mixed Native provenance")
        require(all(finite(row[key]) for key in
                    ("ego_longitudinal_m", "rear_longitudinal_m", "ego_speed_mps", "rear_speed_mps")),
                "Incomplete motion sample")
        require(row["ego_speed_mps"] >= 0 and row["rear_speed_mps"] >= 0,
                "Negative speed sample")
        require(row["ego_lane_id"] in (context["extreme_left_lane_id"], context["right_lane_id"]) and
                row["rear_lane_id"] == context["extreme_left_lane_id"],
                "Lane identity differs")
        delta = row["rear_longitudinal_m"] - row["ego_longitudinal_m"]
        same_left = row["ego_lane_id"] == context["extreme_left_lane_id"]
        faster = row["rear_speed_mps"] > row["ego_speed_mps"]
        if delta < 0 and faster:
            rear_before.append(index)
        if same_left and row["ego_speed_mps"] < context["posted_speed_limit_mps"]:
            left_under_limit.append(index)
        if prior_delta is not None and prior_delta < 0 <= delta:
            crossing.append(index)
        prior_delta = delta
    require(len(crossing) == 1 and rear_before and left_under_limit,
            "Rear overtaking or slow-left sample absent")
    after = [index for index in left_under_limit if index >= crossing[0]]
    return {"format": "c230259-source-left-lane-measure-v1",
            "source_kind": context["source_kind"],
            "source_sha256": expected_hashes,
            "sample_count": FRAMES, "capture_hz": RATE,
            "rear_higher_speed_behind_frames": len(rear_before),
            "overtake_crossing_frame": crossing[0],
            "slow_extreme_left_frames": len(left_under_limit),
            "slow_extreme_left_after_overtake_frames": len(after),
            "ego_exited_left_before_crossing": rows[crossing[0] - 1]["ego_lane_id"] != context["extreme_left_lane_id"],
            "controlled_access_verified": False,
            "posted_limit_original_verified": False,
            "driver_knowledge_or_reasonable_notice": None,
            "subsection_2_exception_review": None,
            "legal_verdict": None,
            "physical_completion_claimed": False}
