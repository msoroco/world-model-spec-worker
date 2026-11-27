"""Recorded-only source join for the shoulder and oncoming beam comparison.

This is a measurement preflight. It never decides whether light was sufficient,
whether glare reached an eye, or whether a lowermost distribution was installed.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from oncoming_beam import measure_trace


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCES = ("road.xodr", "beam-rows.jsonl", "video_frames.jsonl",
           "road-position-source.json", "lighting-trigger-source.json",
           "oncoming-driver-source.json", "eye-region-source.json")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def load_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def measure_saved(attempt):
    root = Path(attempt).resolve()
    context = json.loads(source(root, "beam-context.json").read_text())
    config = json.loads(source(root, "config.json").read_text())
    if context.get("case_id") != config.get("selected_case_id"):
        raise ValueError("exact beam case source differs")
    if context.get("deeming_invoked") is not False or context.get("legal_verdict_claimed"):
        raise ValueError("unverified lowermost distribution or legal claim")
    if set(context.get("source_sha256", {})) != set(SOURCES):
        raise ValueError("incomplete original beam source inventory")
    for name in SOURCES:
        if sha(source(root, name)) != context["source_sha256"][name]:
            raise ValueError("Original beam source hash differs: " + name)
    for name in CAMERAS:
        source(root, name + ".mkv")
    rows = load_rows(source(root, "beam-rows.jsonl"))
    frames = load_rows(source(root, "video_frames.jsonl"))
    if len(rows) != 600 or len(frames) != 600 or any(
            row.get("frame") != frame.get("video_frame") or
            row.get("native_frame") != frame.get("native_frame") or
            abs(row["time_s"] - frame["time_s"]) > 1e-6
            for row, frame in zip(rows, frames)):
        raise ValueError("original beam Native/video 600-frame join differs")
    clocks = []
    for row in rows:
        value = row.get("civil_time_utc")
        if not isinstance(value, str):
            raise ValueError("original per-tick UTC clock missing")
        try:
            instant = datetime.fromisoformat(value)
        except ValueError as error:
            raise ValueError("original UTC clock invalid") from error
        if instant.tzinfo is None or instant.utcoffset() != timezone.utc.utcoffset(instant):
            raise ValueError("original per-tick clock must be UTC")
        clocks.append(instant)
    if any(later <= earlier for earlier, later in zip(clocks, clocks[1:])):
        raise ValueError("original per-tick UTC clock must advance")
    road = json.loads(source(root, "road-position-source.json").read_text())
    timing = json.loads(source(root, "lighting-trigger-source.json").read_text())
    other = json.loads(source(root, "oncoming-driver-source.json").read_text())
    eyes = json.loads(source(root, "eye-region-source.json").read_text())
    if not eyes.get("driver_reference_camera") in CAMERAS or not eyes.get("pixel_review_required"):
        raise ValueError("original oncoming eye-region source required")
    if not other.get("oncoming_actor_source"):
        raise ValueError("original oncoming vehicle source required")
    if not timing.get("NRS_484D_100_review_required"):
        raise ValueError("incorporated lighting trigger review required")
    if not timing.get("utc_clock_capture") or not timing.get("local_site_and_sun_event_review_required"):
        raise ValueError("original civil-clock and local sun-event review source required")
    scene = {"road_position": road.get("road_position"),
             "road_source": road.get("map_and_adjacency_source"),
             "lighting_trigger": timing.get("lighting_trigger"),
             "trigger_source": timing.get("original_trigger_source"),
             "oncoming_driver_source": other.get("oncoming_actor_source"),
             "eye_region_source": eyes.get("driver_reference_camera")}
    measurement = measure_trace(rows, scene)
    return {"case_id": context["case_id"], "measurement": measurement,
            "source_sha256": dict(context["source_sha256"]),
            "original_pixels_reviewed": False, "legal_verdict_claimed": False}
