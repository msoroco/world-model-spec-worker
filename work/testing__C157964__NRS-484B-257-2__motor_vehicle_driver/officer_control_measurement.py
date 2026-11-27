"""Saved-only source admission for a reviewed officer-control exception interval.

An officer's presence alone does not establish that the officer controls traffic.
The result is an engineering context measurement, never a legal verdict.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ASSIGNMENT = "testing__C157964__NRS-484B-257-2__motor_vehicle_driver"


def source_bytes(root: Path, ref: dict) -> bytes:
    if not isinstance(ref, dict) or not isinstance(ref.get("path"), str):
        raise ValueError("source path required")
    relative = Path(ref["path"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("source path must remain beneath source root")
    raw = (root / relative).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref.get("sha256"):
        raise ValueError("original source hash differs")
    return raw


def source(root: Path, ref: dict) -> dict:
    return json.loads(source_bytes(root, ref))


def measure(packet: dict, root: Path) -> dict:
    if packet.get("assignment_id") != ASSIGNMENT or packet.get("cell_id") != "C157964":
        raise ValueError("assignment/cell differs")
    if packet.get("law_id") != "NRS-484B-257-2" or packet.get("actor") != "motor_vehicle_driver":
        raise ValueError("law/actor differs")
    result = source(root, packet.get("native_result"))
    frames = source(root, packet.get("frame_map"))
    review = source(root, packet.get("officer_review"))
    video = source_bytes(root, packet.get("original_video"))
    if result.get("source_kind") != "original_native" or result.get("assignment_id") != ASSIGNMENT:
        raise ValueError("sealed original Native result required")
    if result.get("recording_id") != packet.get("recording_id"):
        raise ValueError("recording identity differs")
    if not isinstance(frames, list) or len(frames) != 900:
        raise ValueError("complete 900-frame original map required")
    if any(row.get("frame") != index or row.get("elapsed_s") != index / 20
           for index, row in enumerate(frames)):
        raise ValueError("original frame map is not contiguous 20 Hz")
    if review.get("source_kind") != "original_independent_review":
        raise ValueError("independent original officer review required")
    if review.get("recording_id") != packet["recording_id"]:
        raise ValueError("officer review recording differs")
    if not review.get("reviewer_id") or review.get("source_video_sha256") != hashlib.sha256(video).hexdigest():
        raise ValueError("officer review provenance missing")
    interval = review.get("crossing_interval_frames")
    if not isinstance(interval, list) or len(interval) != 2 or not all(isinstance(x, int) and not isinstance(x, bool) for x in interval):
        raise ValueError("reviewed crossing frame interval required")
    first, last = interval
    if not 0 <= first <= last < len(frames):
        raise ValueError("reviewed crossing interval outside original capture")
    state = review.get("officer_controlling_traffic")
    if state is not None and type(state) is not bool:
        raise ValueError("reviewed control state invalid")
    if review.get("officer_visible") is not True and state is True:
        raise ValueError("controlling officer lacks original visibility")
    return {
        "format": "worker-officer-control-context-measurement",
        "assignment_id": ASSIGNMENT,
        "recording_id": packet["recording_id"],
        "crossing_interval_frames": interval,
        "officer_visible": review.get("officer_visible") is True,
        "officer_controlling_traffic": state,
        "exception_context": "observed_officer_control" if state is True else
                             "officer_present_not_controlling" if state is False else "unverified",
        "source_sha256": {key: packet[key]["sha256"] for key in
                          ("native_result", "frame_map", "officer_review", "original_video")},
        "legal_verdict": None,
    }
