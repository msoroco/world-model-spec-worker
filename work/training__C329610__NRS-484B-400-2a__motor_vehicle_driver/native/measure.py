"""Saved-only geometric measurements for the proposed C329610 left-turn cases.

Inputs are observed Native samples and surveyed Native geometry. This module
does not assign a legal outcome or infer intent from motion.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure(samples_path: Path, geometry_path: Path) -> dict:
    if not samples_path.is_file():
        raise ValueError(f"Missing required source: {samples_path.name}")
    if not geometry_path.is_file():
        raise ValueError(f"Missing required source: {geometry_path.name}")
    geometry = json.loads(geometry_path.read_text())
    for key in ("approach_direction", "destination_direction", "approach_opposing_direction",
                "destination_opposing_direction", "native_map_sha256", "centerline_y_m",
                "right_edge_y_m", "intersection_entry_x_m", "destination_exit_y_m"):
        if key not in geometry:
            raise ValueError("Missing surveyed Native geometry: " + key)
    if geometry["approach_direction"] != "eastbound" or geometry["destination_direction"] != "northbound":
        raise ValueError("Native direction survey differs from authored two-way left-turn context")
    if geometry["approach_opposing_direction"] != "westbound" or geometry["destination_opposing_direction"] != "southbound":
        raise ValueError("Native two-way highway evidence missing")
    if not isinstance(geometry["native_map_sha256"], str) or len(geometry["native_map_sha256"]) != 64:
        raise ValueError("Native map hash missing")
    centerline = float(geometry["centerline_y_m"])
    right_edge = float(geometry["right_edge_y_m"])
    entry = float(geometry["intersection_entry_x_m"])
    exit_y = float(geometry["destination_exit_y_m"])
    if not right_edge < centerline or not math.isfinite(entry):
        raise ValueError("Invalid surveyed roadway boundaries")
    rows = [json.loads(line) for line in samples_path.read_text().splitlines() if line.strip()]
    if len(rows) < 2:
        raise ValueError("Too few Native motion samples")
    previous = -math.inf
    approach = []
    entry_bracket = None
    for row in rows:
        t = float(row["time_s"])
        if not math.isfinite(t) or t <= previous:
            raise ValueError("Native sample times are not strictly increasing")
        previous = t
        position = row["native_center_xy_m"]
        vertices = row["native_body_xy_m"]
        if len(position) != 2 or len(vertices) != 4:
            raise ValueError("Native body/center sample incomplete")
        if not all(math.isfinite(float(v)) for point in [position, *vertices] for v in point):
            raise ValueError("Nonfinite Native body/center sample")
        front_x = max(float(vertex[0]) for vertex in vertices)
        if entry_bracket is None and front_x >= entry:
            entry_bracket = [rows[len(approach)-1]["time_s"] if approach else None, t]
        if front_x < entry:
            approach.append(row)
    if not approach or entry_bracket is None:
        raise ValueError("No observed approach and intersection entry bracket")
    offsets = [centerline - float(row["native_center_xy_m"][1]) for row in approach]
    within_right_half = all(right_edge < float(vertex[1]) < centerline for row in approach for vertex in row["native_body_xy_m"])
    completed = any(float(row["native_center_xy_m"][1]) > exit_y and
                    abs(float(row["native_yaw_deg"]) - 90) <= 20 for row in rows)
    return {
        "format": "c329610-saved-geometry-measurement-v1",
        "provenance_kind": "native_samples_required",
        "approach_window_s": [approach[0]["time_s"], approach[-1]["time_s"]],
        "intersection_entry_time_bracket_s": entry_bracket,
        "center_to_centerline_offset_m": {"min": min(offsets), "max": max(offsets), "mean": sum(offsets)/len(offsets)},
        "full_body_within_right_half_on_sampled_approach": within_right_half,
        "northbound_exit_observed": completed,
        "sample_count": len(rows),
        "approach_sample_count": len(approach),
        "sources": {samples_path.name: _sha(samples_path), geometry_path.name: _sha(geometry_path)},
        "limitations": ["Native sampled geometry only", "No continuous intersample claim", "No statutory nearest-centerline cutoff", "No legal verdict or intent inference"]
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", required=True, type=Path)
    parser.add_argument("--geometry", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = measure(args.samples, args.geometry)
    if args.output.exists():
        raise ValueError("Retain prior report; choose a new output")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
