"""Source-shaped CPU diagnostic for NRS 484B.153(3); never a legal verdict.

The input is a decoded Native trace envelope. The local producer must replace
the synthetic proof packets with original frame-map, actor, and camera sources.
"""

from __future__ import annotations

import math

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
FRAME_COUNT = 600
FPS = 20


def measure(packet: dict) -> dict:
    if packet.get("source_kind") != "native_trace" or not packet.get("source_sha256"):
        raise ValueError("original Native trace source required")
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) != FRAME_COUNT:
        raise ValueError("complete 600-frame trace required")
    if set(packet.get("cameras", {})) != set(VIEWS):
        raise ValueError("four named source cameras required")
    for name in VIEWS:
        cam = packet["cameras"][name]
        if cam.get("frame_count") != FRAME_COUNT or not cam.get("sha256"):
            raise ValueError("camera frame count and source hash required")
    if packet.get("driver_actor_id") != packet.get("door_operator_actor_id"):
        raise ValueError("selected driver must operate the observed door")
    door = packet.get("door", {})
    if door.get("side") not in ("left", "right") or not door.get("source_ref"):
        raise ValueError("sourced door side required")
    passing = packet.get("passing_vehicle", {})
    if not passing.get("actor_id") or not passing.get("source_ref"):
        raise ValueError("sourced passing vehicle required")
    if passing["actor_id"] == packet.get("driver_actor_id"):
        raise ValueError("passing vehicle must be another actor")
    offsets = passing.get("lateral_offsets_m")
    if not isinstance(offsets, list) or len(offsets) != FRAME_COUNT:
        raise ValueError("complete passing-vehicle trajectory required")
    if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in offsets):
        raise ValueError("finite passing-vehicle positions required")
    # Lateral offsets use ego-forward coordinates. A passing path must remain
    # on one side throughout its observed transit; crossings need a new case.
    transit = passing.get("transit_frames")
    if not isinstance(transit, list) or len(transit) < 2 or any(not isinstance(i, int) or not 0 <= i < FRAME_COUNT for i in transit):
        raise ValueError("passing transit frames required")
    signs = {1 if offsets[i] > 0 else -1 if offsets[i] < 0 else 0 for i in transit}
    if len(signs) != 1 or 0 in signs:
        raise ValueError("passing path side must be unambiguous")
    passing_side = "left" if signs == {1} else "right"
    if door["side"] != passing_side:
        raise ValueError("observed door is not on passing-traffic side")
    for i, row in enumerate(frames):
        if row.get("native_frame") != i or abs(row.get("native_time_s", -1) - i / FPS) > 1e-6:
            raise ValueError("contiguous original Native frame/time join required")
        if not isinstance(row.get("door_open"), bool) or not row.get("door_state_source_ref"):
            raise ValueError("sourced door-open state required for every frame")
        if not isinstance(row.get("ego_speed_mps"), (int, float)) or not math.isfinite(row["ego_speed_mps"]):
            raise ValueError("sourced finite vehicle speed required")
        if not row.get("ego_motion_source_ref"):
            raise ValueError("sourced ego motion required")
    if any(abs(row["ego_speed_mps"]) > 0.15 for row in frames if row["door_open"]):
        raise ValueError("vehicle not stationary during door-open interval")
    intervals = []
    start = None
    for i, row in enumerate(frames):
        if row["door_open"] and start is None:
            start = i
        elif not row["door_open"] and start is not None:
            intervals.append((start, i))
            start = None
    if start is not None:
        raise ValueError("door interval truncated at capture end")
    if len(intervals) != 1:
        raise ValueError("one fully observed door-open interval required")
    opening, closing = intervals[0]
    events = packet.get("transfer_events")
    if not isinstance(events, list) or not events:
        raise ValueError("sourced passenger or cargo transfer events required")
    for event in events:
        if event.get("kind") not in ("passenger", "cargo") or not event.get("source_ref"):
            raise ValueError("sourced passenger or cargo event required")
        if not isinstance(event.get("native_frame"), int) or not opening <= event["native_frame"] < closing:
            raise ValueError("transfer event must join observed open interval")
        if event["kind"] == "passenger" and not (event.get("occupancy_delta") and event.get("pedestrian_actor_id")):
            raise ValueError("passenger transfer needs occupancy and pedestrian sources")
        if event["kind"] == "cargo" and not event.get("cargo_actor_id"):
            raise ValueError("cargo transfer needs identified cargo")
    last_transfer = max(e["native_frame"] for e in events)
    return {
        "source_kind": packet["source_kind"], "source_sha256": packet["source_sha256"],
        "frame_count": FRAME_COUNT, "fps": FPS, "door_side": door["side"],
        "passing_side": passing_side, "driver_operated_door": True,
        "open_frame": opening, "close_frame": closing,
        "open_duration_s": (closing - opening) / FPS,
        "last_transfer_frame": last_transfer,
        "post_transfer_open_s": (closing - last_transfer) / FPS,
        "transfer_kinds": sorted({e["kind"] for e in events}),
        "legal_necessity": "unresolved_requires_contextual_review",
    }
