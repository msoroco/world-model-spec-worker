"""Join independently saved lane, signal and driver-check readbacks.

This is an original-source finalizer. A check observation is retained as an
observation; it does not establish driver ascertainment or movement safety.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from lane_change_timing import ASSIGNMENT, measure_trace


SOURCES = ("frame_map", "ego_pose", "native_signal", "driver_check")


def _load(root: Path, entry: dict) -> dict:
    rel = Path(entry["path"])
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("original source path escapes attempt")
    path = (root / rel).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("original source missing")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != entry.get("sha256"):
        raise ValueError("original source hash mismatch")
    return json.loads(raw)


def finalize(root: str | Path, inventory: dict, case_id: str) -> dict:
    root = Path(root)
    if (not case_id.startswith(ASSIGNMENT + "__") or
            inventory.get("case_id") != case_id or
            inventory.get("source_kind") != "original_native" or
            not inventory.get("original_trace_id")):
        raise ValueError("original exact lane-change identity required")
    entries = inventory.get("sources")
    if not isinstance(entries, dict) or set(entries) != set(SOURCES):
        raise ValueError("four independent original source packets required")
    packets = {name: _load(root, entries[name]) for name in SOURCES}
    for name, packet in packets.items():
        if packet.get("case_id") != case_id or packet.get("source_kind") != "original_native":
            raise ValueError(f"{name} original case/source identity differs")
        if not isinstance(packet.get("samples"), list) or len(packet["samples"]) != 900:
            raise ValueError(f"{name} original 900-frame history missing")
    if (not packets["ego_pose"].get("source_lane_id") or
            not packets["ego_pose"].get("lane_geometry_source") or
            not packets["native_signal"].get("readback_source") or
            not packets["driver_check"].get("readback_source") or
            not packets["driver_check"].get("observation_method")):
        raise ValueError("independent lane, signal and driver-check provenance missing")
    frames = []
    base = packets["frame_map"]["samples"]
    first = base[0].get("frame")
    if type(first) is not int or [row.get("frame") for row in base] != list(range(first, first + 900)):
        raise ValueError("original frame sequence differs")
    for index, anchor in enumerate(base):
        frame, time_s = anchor["frame"], anchor.get("t_s")
        if type(time_s) not in (int, float) or not math.isfinite(time_s):
            raise ValueError("original frame clock missing")
        joined = {}
        for name in SOURCES[1:]:
            row = packets[name]["samples"][index]
            if row.get("frame") != frame or row.get("t_s") != time_s:
                raise ValueError(f"{name} original frame/time join differs")
            joined[name] = row
        frames.append({"t_s": time_s,
            "x_m": joined["ego_pose"].get("x_m"),
            "y_m": joined["ego_pose"].get("y_m"),
            "source_lane_offset_m": joined["ego_pose"].get("source_lane_offset_m"),
            "left_signal": joined["native_signal"].get("left_signal"),
            "right_signal": joined["native_signal"].get("right_signal"),
            "driver_check_observed": joined["driver_check"].get("driver_check_observed")})
    trace = {"assignment_id": ASSIGNMENT,
             "original_trace_id": inventory["original_trace_id"],
             "source_lane_id": packets["ego_pose"]["source_lane_id"],
             "frames": frames}
    result = measure_trace(trace, {"component_sha256": {
        name: entries[name]["sha256"] for name in SOURCES}})
    result["format"] = "c144550-original-independent-readback-finalization-v1"
    result["case_id"] = case_id
    result["original_frame_count"] = 900
    result["driver_check_readback_source"] = packets["driver_check"]["readback_source"]
    result["driver_check_observation_method"] = packets["driver_check"]["observation_method"]
    result["legal_ascertainment_and_safety"] = "unresolved"
    return result
