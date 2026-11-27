"""Check original taxi-stand delivery evidence after Native capture.

The caller must supply independent pixel and activity reviews. This module
does not turn requested passenger activity or diagnostic fixtures into facts.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ASSIGNMENT = "testing__C378245__LVMC-11-60-040__taxi_driver"
SUFFIXES = (
    "outside_stand_park", "designated_stand_park", "outside_stand_stand",
    "outside_stand_load", "outside_stand_unload", "outside_stand_idle_stop",
)
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
CHECKS = (
    "native_source", "all_participants", "time_join", "full_video_decode",
    "actual_pixels", "physical_completion",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(case_id: str, attempt: Path, source: dict, decode: dict,
           physical: dict, pixels: dict, activity: dict, core: dict) -> dict:
    if case_id not in {ASSIGNMENT + "__" + suffix for suffix in SUFFIXES}:
        raise ValueError("unknown exact taxi case")
    attempt = attempt.resolve()
    if source.get("case_id") != case_id or source.get("passed") is not True:
        raise ValueError("original Native source chain unverified")
    if physical.get("case_id") != case_id or physical.get("provenance_kind") != "native":
        raise ValueError("original physical source absent")
    if physical.get("diagnostic_fixture") is not False or physical.get("maneuver_completed") is not True:
        raise ValueError("physical completion unverified")
    checks = physical.get("physical_checks", {})
    if not {"setup", "target", "maneuver"} <= set(checks):
        raise ValueError("physical checks incomplete")
    for item in checks.values():
        if item.get("status") != "met" or not item.get("sources"):
            raise ValueError("physical check lacks measured original sources")
        for relative, digest in item["sources"].items():
            path = (attempt / relative).resolve()
            if not path.is_relative_to(attempt) or not path.is_file() or sha(path) != digest:
                raise ValueError("physical completion source changed: " + relative)
    frame_map = attempt / "video_frames.jsonl"
    rows = [json.loads(line) for line in frame_map.read_text().splitlines()]
    scenes = core.get("scenes", [])
    if len(rows) != 900 or len(scenes) != 900 or source.get("frames") != 900:
        raise ValueError("900 original frames required")
    if source.get("frame_map_sha256") != sha(frame_map):
        raise ValueError("original frame map changed")
    for index, (row, scene) in enumerate(zip(rows, scenes)):
        if row.get("video_frame") != index or scene.get("t") != round(row.get("time_s", -1) * 1000):
            raise ValueError("Core trace/original frame time join differs")
    if decode.get("case_id") != case_id or decode.get("passed") is not True:
        raise ValueError("full video decode unverified")
    videos = decode.get("videos", {})
    if set(videos) != set(VIEWS):
        raise ValueError("four original views required")
    for view in VIEWS:
        video = attempt / (view + ".mkv")
        item = videos[view]
        if item.get("frames") != 900 or item.get("sha256") != sha(video):
            raise ValueError("decoded original view source changed: " + view)
    if pixels.get("format") != "worker-original-pixel-review" or pixels.get("case_id") != case_id:
        raise ValueError("original pixel review missing")
    if pixels.get("diagnostic_fixture") is not False or not pixels.get("reviewer"):
        raise ValueError("original pixel review lacks independent reviewer")
    if pixels.get("frame_map_sha256") != sha(frame_map) or pixels.get("video_sha256") != sha(attempt / "overview.mkv"):
        raise ValueError("original pixel review source changed")
    observations = pixels.get("observations", {})
    for name in ("taxi", "stand_boundary", "street_context", "passenger_door"):
        item = observations.get(name, {})
        if (item.get("visible") is not True or item.get("view") not in VIEWS
                or not isinstance(item.get("frame"), int) or not 0 <= item["frame"] < 900
                or not item.get("description")):
            raise ValueError("actual pixels unverified: " + name)
    if activity.get("case_id") != case_id or activity.get("diagnostic_fixture") is not False:
        raise ValueError("original activity review missing")
    if not activity.get("reviewer") or activity.get("frame_map_sha256") != sha(frame_map):
        raise ValueError("original activity review source changed")
    if case_id.endswith(("__outside_stand_load", "__outside_stand_unload")):
        if not activity.get("actual_passenger_exchange"):
            raise ValueError("actual passenger exchange unverified")
    return {"format": "worker-taxi-delivery-audit", "passed": True,
            "case_id": case_id, "checks": {key: True for key in CHECKS},
            "frames": 900, "frame_map_sha256": sha(frame_map),
            "pixel_review_sha256": pixels.get("_file_sha256"),
            "activity_review_sha256": activity.get("_file_sha256")}
