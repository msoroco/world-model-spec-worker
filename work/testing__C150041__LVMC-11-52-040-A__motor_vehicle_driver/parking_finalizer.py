"""Saved-only original-history finalizer for C150041 stationary geometry.

This reports observed geometry and controls without deciding standing, parking,
legal parallelism, or any Chapter exception.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from parking_measurement import measure_sequence
from parking_pose import request
from parking_scene import ASSIGNMENT
from source_review import validate


def finalize(packet_path, source_root, suffix, history_path, expected_sha256):
    activity = request(suffix)[0]
    context = validate(packet_path, source_root=source_root)
    if context["activity"] != activity:
        raise ValueError("source-reviewed activity differs from requested case")
    raw = Path(history_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("original stationary history hash changed")
    frames = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    measured = measure_sequence(frames, context)
    observations = []
    for original, geometry in zip(frames, measured["frames"]):
        speed = original.get("speed_m_s")
        control = original.get("control")
        if type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
            raise ValueError("original speed must be finite and nonnegative")
        if not isinstance(control, dict) or set(control) != {"throttle", "steer", "brake"}:
            raise ValueError("original control fields missing")
        if any(type(value) not in (int, float) or not math.isfinite(value)
               for value in control.values()):
            raise ValueError("original control values must be finite")
        if not (0 <= control["throttle"] <= 1 and -1 <= control["steer"] <= 1 and
                0 <= control["brake"] <= 1):
            raise ValueError("original control values outside Native range")
        observations.append({**geometry, "speed_m_s": speed, "control": control,
                             "engineering_stationary": speed <= 0.15})
    intervals = []
    start = None
    for index, item in enumerate(observations):
        if item["engineering_stationary"] and start is None:
            start = index
        if start is not None and (not item["engineering_stationary"] or
                                  index == len(observations) - 1):
            end = index if item["engineering_stationary"] else index - 1
            if end > start:
                intervals.append({"first_frame": observations[start]["frame"],
                                  "last_frame": observations[end]["frame"],
                                  "duration_s": observations[end]["time_s"] -
                                                observations[start]["time_s"]})
            start = None
    if not intervals:
        raise ValueError("original history lacks a multi-frame stationary interval")
    return {"case_id": ASSIGNMENT + "__" + suffix,
            "source_packet_sha256": context["reviewed_packet_sha256"],
            "original_history_sha256": expected_sha256,
            "activity_source": context["activity_source"],
            "chapter_exception_source": context["chapter_exception_source"],
            "stationary_intervals": intervals,
            "observations": observations,
            "engineering_stationary_speed_m_s": 0.15,
            "legal_judgment": "unresolved",
            "physical_acceptance_claimed": False}
