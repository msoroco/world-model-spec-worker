"""Source-bound elapsed parking aggregation for LVMC 11.52.180(C).

The computed maximum is a measurement. Alley status, designation, other
lawfulness and any legal interpretation require separate original review.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

WINDOW_SECONDS = 3600.0
LIMIT_SECONDS = 1800.0


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Invalid {label}")
    return float(value)


def validate_intervals(intervals):
    if not isinstance(intervals, list) or not intervals:
        raise ValueError("Missing original parking intervals")
    checked = []
    for item in intervals:
        if not isinstance(item, dict):
            raise ValueError("Parking interval is not a source record")
        start = _number(item.get("start_s"), "parking start")
        end = _number(item.get("end_s"), "parking end")
        if end <= start:
            raise ValueError("Nonpositive parking interval")
        if checked and start < checked[-1][1]:
            raise ValueError("Overlapping or unordered parking intervals")
        if not item.get("vehicle_id"):
            raise ValueError("Missing original vehicle identity")
        checked.append((start, end, item["vehicle_id"]))
    if len({v for _, _, v in checked}) != 1:
        raise ValueError("Parking intervals belong to different vehicles")
    return [(a, b) for a, b, _ in checked]


def overlap_seconds(intervals, window_start, window_seconds=WINDOW_SECONDS):
    end = window_start + window_seconds
    return sum(max(0.0, min(b, end) - max(a, window_start)) for a, b in intervals)


def maximum_rolling_hour(intervals):
    """Maximum exact interval overlap with any 3600-second window.

    A piecewise linear overlap has extrema when a window edge coincides with
    an interval edge. Testing both edge orientations finds the global maximum.
    """
    valid = validate_intervals(intervals)
    edges = {x for pair in valid for x in pair}
    starts = sorted(edges | {x - WINDOW_SECONDS for x in edges})
    candidates = [(overlap_seconds(valid, start), start) for start in starts]
    maximum, start = max(candidates, key=lambda x: (x[0], -x[1]))
    return {"maximum_parked_seconds_in_any_hour": maximum,
            "controlling_window_start_s": start,
            "controlling_window_end_s": start + WINDOW_SECONDS,
            "statutory_boundary_seconds": LIMIT_SECONDS,
            "greater_than_thirty_minutes": maximum > LIMIT_SECONDS}


def measure_source_packet(root: Path, inventory: dict):
    """Hash-check the original interval and context packets before measuring.

    No legal verdict is issued. Source completeness and other-lawfulness
    remain explicit review fields in the returned report.
    """
    required = ("parking-intervals.json", "alley-context.json", "video_frames.jsonl")
    if set(inventory) != set(required):
        raise ValueError("Incomplete source inventory")
    payloads = {}
    for name in required:
        entry = inventory[name]
        path = root / name
        if not path.is_file() or path.is_symlink():
            raise ValueError("Missing original source: " + name)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry.get("sha256"):
            raise ValueError("Original source hash mismatch: " + name)
        payloads[name] = raw
    context = json.loads(payloads["alley-context.json"])
    if context.get("review_status") != "original_reviewed" or not all(
        context.get(k) for k in ("municipal_alley_source", "engineer_designation_source",
                                  "angle_marking_source", "other_parking_rules_source", "loading_activity_source")
    ):
        raise ValueError("Original alley, designation or other-lawfulness review missing")
    record = json.loads(payloads["parking-intervals.json"])
    if record.get("window_history_status") != "complete_original" or record.get("vehicle_id") is None:
        raise ValueError("Incomplete original rolling-hour vehicle history")
    if not all(x.get("vehicle_id") == record["vehicle_id"] for x in record.get("intervals", [])):
        raise ValueError("Original vehicle identity mismatch")
    if not payloads["video_frames.jsonl"].strip():
        raise ValueError("Empty original frame map")
    measured = maximum_rolling_hour(record["intervals"])
    measured.update({"source_hashes": {name: inventory[name]["sha256"] for name in required},
                     "legal_classification": "unreviewed",
                     "source_history_status": "complete_original"})
    return measured
