"""Measure original yield approach samples without making a legal determination.

The nearest-view selector is geometric. A reviewer must still determine whether
the original driver had a view and whether safety required a stop.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from yield_site import select_stop_reference


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def measure(root, case_id):
    root = Path(root)
    site_path = require(root, "original-yield-site.json")
    trace_path = require(root, "original-yield-trace.jsonl")
    receipt_path = require(root, "original-yield-receipt.json")
    site = json.loads(site_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if site.get("case_id") != case_id or receipt.get("case_id") != case_id:
        raise ValueError("original case identity mismatch")
    if receipt.get("site_sha256") != digest(site_path) or receipt.get("trace_sha256") != digest(trace_path):
        raise ValueError("original source hash mismatch")
    if site.get("source_review_status") not in ("diagnostic_only", "reviewed_original"):
        raise ValueError("source review status missing")
    if site["source_review_status"] == "reviewed_original" and not site.get("source_records"):
        raise ValueError("reviewed original site records missing")
    reference = select_stop_reference(site_path)
    rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    if len(rows) < 3 or receipt.get("frame_count") != len(rows):
        raise ValueError("original stop trace frame count mismatch")
    previous_frame = previous_time = None
    stops = []
    for index, row in enumerate(rows):
        frame, time = row.get("frame"), row.get("time_s")
        if type(frame) is not int or type(time) not in (int, float) or not math.isfinite(time):
            raise ValueError("invalid original frame or time")
        if previous_frame is not None and (frame != previous_frame + 1 or abs(time - previous_time - .05) > .005):
            raise ValueError("original 20 Hz frame/time join differs")
        previous_frame, previous_time = frame, time
        if row.get("ego_actor_id") != receipt.get("ego_actor_id"):
            raise ValueError("original ego actor differs")
        position, speed = row.get("ego_center_xy_m"), row.get("ego_speed_mps")
        if (not isinstance(position, list) or len(position) != 2 or
                any(type(v) not in (float, int) or not math.isfinite(v) for v in position) or
                type(speed) not in (float, int) or not math.isfinite(speed) or speed < 0):
            raise ValueError("original position/speed missing")
        if row.get("camera_frames") is None:
            raise ValueError("original four-camera frame join missing")
        control = row.get("yield_control_readback")
        if (not isinstance(control, dict) or control.get("yield_sign_id") != site["yield_sign_id"] or
                control.get("control") != "yield_sign"):
            raise ValueError("original yield-sign readback differs")
        if not receipt.get("diagnostic_fixture") and (not control.get("live_actor_id") or
                set(row["camera_frames"]) != {"overview", "approach", "reference_corner", "driver_reference"}):
            raise ValueError("original sign actor or four-camera source missing")
        vertices = row.get("ego_vertices")
        if (not isinstance(vertices, list) or len(vertices) != 8 or any(
                not isinstance(vertex, list) or len(vertex) != 3 or any(
                    type(value) not in (float, int) or not math.isfinite(value) for value in vertex)
                for vertex in vertices)):
            raise ValueError("original eight-vertex motor-vehicle body missing")
        # A small speed is an engineering witness only; preserve the full trace.
        if speed <= .1 and position[0] < site["intersecting_highway_boundary_x"]:
            stops.append({"frame": frame, "time_s": time, "position_xy_m": position,
                          "distance_to_reference_m": math.dist(position, reference["reference_position"]),
                          "leading_body_x_minus_reference_x_m": max(vertex[0] for vertex in vertices) -
                              reference["reference_position"][0]})
    return {"case_id": case_id, "reference": reference,
            "original_stop_samples": stops, "original_sample_count": len(rows),
            "source_bindings": {name: digest(root / name) for name in
                ("original-yield-site.json", "original-yield-trace.jsonl", "original-yield-receipt.json")},
            "safety_necessity_source": site.get("safety_necessity_source"),
            "legal_judgment": None,
            "limitations": ["0.1 m/s is a diagnostic stop-sample threshold, not a legal cutoff.",
                            "Geometric view rays do not establish what the original driver saw.",
                            "Safety necessity and adequacy of stopping remain independent reviews."]}
