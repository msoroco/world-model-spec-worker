"""Join a sealed later-opponent source to an original reciprocal left-turn trace.

This is a saved-only measurement; it does not establish legal right of way or
physical completion. The separate actor must be present in every original frame.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from reciprocal_witness import measure_later_opponent


ASSIGNMENT = "testing__C109749__NRS-484B-253__motor_vehicle_driver"
SOURCE = "later-opponent-original.jsonl"


def _read_confined(root: Path, name: str) -> bytes:
    path = root / name
    if not path.is_file() or path.is_symlink() or path.resolve().parent != root:
        raise ValueError("original reciprocal source missing or outside attempt: " + name)
    return path.read_bytes()


def audit_saved(attempt: Path, *, case_id: str) -> dict:
    suffix = case_id.removeprefix(ASSIGNMENT + "__")
    if not case_id.startswith(ASSIGNMENT + "__") or suffix not in (
            "reciprocal_yield", "reciprocal_no_yield"):
        raise ValueError("exact reciprocal case required")
    root = Path(attempt).resolve()
    receipt = json.loads(_read_confined(root, "acquisition-receipt.json"))
    if receipt.get("case_id") != case_id or receipt.get("simulator_frame_rate_hz") != 20:
        raise ValueError("original reciprocal acquisition identity or cadence differs")
    source_sha = receipt.get("later_opponent_trace_sha256")
    if not isinstance(source_sha, str) or len(source_sha) != 64:
        raise ValueError("sealed separate later-opponent source required")
    map_raw = _read_confined(root, "original-map.json")
    trace_raw = _read_confined(root, "original-trace.jsonl")
    later_raw = _read_confined(root, SOURCE)
    for label, raw, key in (("map", map_raw, "map_sha256"),
                            ("trace", trace_raw, "trace_sha256"),
                            ("later opponent", later_raw, "later_opponent_trace_sha256")):
        if hashlib.sha256(raw).hexdigest() != receipt.get(key):
            raise ValueError("sealed original " + label + " source hash drift")
    map_packet = json.loads(map_raw)
    primary = [json.loads(line) for line in trace_raw.splitlines()]
    later = [json.loads(line) for line in later_raw.splitlines()]
    if len(primary) != 900 or len(later) != 900 or receipt.get("frame_count") != 900:
        raise ValueError("900 joined original reciprocal frames required")
    joined = []
    fields = ("later_opponent_actor_id", "later_opponent_vertices",
              "later_opponent_heading", "later_opponent_speed_mps",
              "later_opponent_braking", "later_opponent_driver_control_source")
    for first, second in zip(primary, later):
        if first.get("frame") != second.get("frame") or first.get("time_s") != second.get("time_s"):
            raise ValueError("original later-opponent frame join differs")
        if any(key not in second for key in fields):
            raise ValueError("original later-opponent actor/control field missing")
        row = dict(first)
        row.update({key: second[key] for key in fields})
        joined.append(row)
    observed = measure_later_opponent(joined, map_packet["intersection_polygon"],
                                      expected_braking=suffix == "reciprocal_yield")
    return {"format": "c109749-reciprocal-saved-join-v1", "case_id": case_id,
            "source_sha256": source_sha, "joined_original_frames": 900,
            "observations": observed, "physical_acceptance": "unverified",
            "legal_right_of_way": "unresolved"}
