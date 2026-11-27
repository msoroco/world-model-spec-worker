"""Measure cumulative alley parking in every source-covered rolling hour.

A 30-second camera clip alone cannot decide this one-hour rule. The independent
source ledger must cover at least one hour and be reviewed for lawful parking.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


FRAMES = 600
RATE_HZ = 20
WINDOW_S = 3600.0
LIMIT_S = 1800.0
CAMERAS = {"overview", "approach", "reference_corner", "driver_reference"}


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Invalid {name}")
    return float(value)


def source_hash(value, name):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"Missing source hash: {name}")


def overlap(start, end, intervals):
    return sum(max(0.0, min(end, interval[1]) - max(start, interval[0])) for interval in intervals)


def measure(context, ledger, frames):
    if context.get("source_kind") != "original_native_alley_parking_ledger":
        raise ValueError("Original alley parking ledger missing")
    for name in ("native_map_sha256", "alley_boundary_sha256", "vehicle_identity_sha256",
                 "parking_ledger_sha256", "civil_time_source_sha256", "lawful_parking_review_sha256"):
        source_hash(context.get(name), name)
    if context.get("alley_status") != "source_surveyed_alley":
        raise ValueError("Alley status not sourced")
    if context.get("otherwise_lawful_review") != "independently_reviewed":
        raise ValueError("Otherwise lawful parking prerequisite not reviewed")
    span_start = finite(ledger.get("span_start_s"), "ledger start")
    span_end = finite(ledger.get("span_end_s"), "ledger end")
    if span_end - span_start < WINDOW_S:
        raise ValueError("Original ledger covers less than one hour")
    entries = ledger.get("parked_intervals")
    if not isinstance(entries, list):
        raise ValueError("Parked interval ledger missing")
    intervals = []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("vehicle_id") != context.get("vehicle_id"):
            raise ValueError("Parked interval vehicle identity differs")
        if entry.get("within_alley") is not True or entry.get("otherwise_lawful_reviewed") is not True:
            raise ValueError("Parked interval alley/lawful source missing")
        start = finite(entry.get("start_s"), "parking start")
        end = finite(entry.get("end_s"), "parking end")
        if not span_start <= start < end <= span_end:
            raise ValueError("Parked interval lies outside sourced ledger")
        intervals.append((start, end))
    intervals.sort()
    if any(b[0] < a[1] for a, b in zip(intervals, intervals[1:])):
        raise ValueError("Overlapping parked intervals double count time")
    if len(frames) != FRAMES:
        raise ValueError("Incomplete 30-second four-camera capture")
    capture_start = finite(ledger.get("capture_start_s"), "capture start")
    if not span_start <= capture_start <= span_end - FRAMES / RATE_HZ:
        raise ValueError("Capture outside original ledger span")
    previous_native = None
    for index, row in enumerate(frames):
        if not isinstance(row, dict) or row.get("video_frame") != index:
            raise ValueError("Video frame identity gap")
        native = row.get("native_frame")
        if type(native) is not int or (previous_native is not None and native <= previous_native):
            raise ValueError("Native frame identity gap")
        previous_native = native
        if abs(finite(row.get("time_s"), "Native capture time") - capture_start - index / RATE_HZ) > 1e-6:
            raise ValueError("Original civil/Native time join failed")
        cameras = row.get("source_cameras")
        if not isinstance(cameras, dict) or set(cameras) != CAMERAS or any(cameras[name] != index for name in CAMERAS):
            raise ValueError("Four source camera frame join failed")
        if row.get("vehicle_id") != context.get("vehicle_id"):
            raise ValueError("Capture vehicle identity differs")
        if row.get("within_alley") is not True:
            raise ValueError("Capture alley occupancy not sourced")
    # Piecewise-linear overlap changes slope only when a window boundary meets
    # an interval boundary. Test these exact candidate starts, clipped to the
    # source-covered range. This covers disjoint re-parking episodes.
    low, high = span_start, span_end - WINDOW_S
    starts = {low, high}
    for start, end in intervals:
        for candidate in (start, end, start - WINDOW_S, end - WINDOW_S):
            if low <= candidate <= high:
                starts.add(candidate)
    best_start = min(starts)
    best_seconds = -1.0
    for start in sorted(starts):
        seconds = overlap(start, start + WINDOW_S, intervals)
        if seconds > best_seconds:
            best_start, best_seconds = start, seconds
    return {
        "format": "worker-source-alley-parking-rolling-hour-measurement",
        "source_covered_seconds": span_end - span_start,
        "capture_frames": FRAMES, "capture_rate_hz": RATE_HZ,
        "capture_start_s": capture_start,
        "parked_interval_count": len(intervals),
        "max_parked_seconds_in_sourced_rolling_hour": best_seconds,
        "max_window_start_s": best_start,
        "statutory_comparison_seconds": LIMIT_S,
        "measured_greater_than_30_minutes": best_seconds > LIMIT_S,
        "otherwise_lawful_prerequisite": "independently_reviewed_source_claim_requires_original_audit",
        "legal_compliance": "unassessed",
        "limitations": [
            "Thirty-second video cannot establish a one-hour history; the separately hashed ledger must be audited",
            "Civil/Native time continuity and vehicle identity need original source review",
            "A move within the alley does not erase time already parked in the rolling hour",
            "Other parking rules determine the otherwise-lawfully-parked prerequisite",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.capture.read_text().splitlines() if line]
    result = measure(json.loads(args.context.read_text()), json.loads(args.ledger.read_text()), rows)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
