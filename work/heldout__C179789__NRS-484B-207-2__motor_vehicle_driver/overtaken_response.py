"""Measure an overtaken driver's response from retained original CPU sources.

The result contains observations and source hashes, never a legal verdict.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _source(path):
    data = Path(path).read_bytes()
    return json.loads(data), hashlib.sha256(data).hexdigest()


def measure(context_path, events_path, motion_path):
    context, context_hash = _source(context_path)
    events, events_hash = _source(events_path)
    motion, motion_hash = _source(motion_path)
    subject = context.get("subject_id")
    overtaker = context.get("overtaker_id")
    if not subject or not overtaker or subject == overtaker:
        raise ValueError("Original participant identities differ or are missing")
    if not context.get("road_source") or not context.get("actor_source"):
        raise ValueError("Original road and actor sources are required")
    if not isinstance(context.get("right_pass_permitted"), bool) or not context.get("right_pass_permission_source"):
        raise ValueError("Right-pass exception needs a sourced premise")
    if events.get("subject_id") != subject or events.get("overtaker_id") != overtaker:
        raise ValueError("Original event identities differ")
    if events.get("notice_kind") not in ("observed_vehicle", "audible_signal") or not events.get("notice_source"):
        raise ValueError("Observed or audible notice source is required")
    notice = events.get("notice_frame")
    complete = events.get("pass_complete_frame")
    if not isinstance(notice, int) or not isinstance(complete, int) or complete <= notice:
        raise ValueError("Pass completion must follow notice in original frame order")
    frames = motion.get("frames", [])
    if not isinstance(frames, list):
        raise ValueError("Original motion frames must be a list")
    by_frame = {}
    for row in frames:
        if row.get("subject_id") != subject or row.get("overtaker_id") != overtaker:
            raise ValueError("Original motion identities differ")
        frame = row.get("frame")
        if not isinstance(frame, int) or frame in by_frame:
            raise ValueError("Original motion frame IDs must be unique integers")
        for key in ("speed_mps", "right_offset_m"):
            if isinstance(row.get(key), bool) or not isinstance(row.get(key), (int, float)):
                raise ValueError("Original motion needs numeric "+key)
        by_frame[frame] = row
    baseline = by_frame.get(notice)
    precompletion = [by_frame[f] for f in sorted(by_frame) if notice < f < complete]
    if baseline is None or not precompletion:
        raise ValueError("There are no motion samples after notice and before pass completion")
    return {
        "subject_id": subject,
        "overtaker_id": overtaker,
        "notice_kind": events["notice_kind"],
        "notice_frame": notice,
        "pass_complete_frame": complete,
        "right_pass_permitted_premise": context["right_pass_permitted"],
        "right_pass_permission_source": context["right_pass_permission_source"],
        "road_source": context["road_source"],
        "actor_source": context["actor_source"],
        "notice_source": events["notice_source"],
        "source_sha256": {"context": context_hash, "events": events_hash, "motion": motion_hash},
        "source_paths": {"context": str(Path(context_path).resolve()),
                         "events": str(Path(events_path).resolve()),
                         "motion": str(Path(motion_path).resolve())},
        "max_right_shift_m": max(row["right_offset_m"] - baseline["right_offset_m"] for row in precompletion),
        "max_precompletion_speed_delta_mps": max(row["speed_mps"] - baseline["speed_mps"] for row in precompletion),
        "legal_conclusion": None,
    }
