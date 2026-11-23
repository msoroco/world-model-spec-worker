"""Check byte custody and geometry for a proposed one-way left-turn site.

This validates a reviewed packet's internal consistency. It cannot establish
that the cited records are authoritative or that CARLA realizes the geometry.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from build_case_plan import AID, KINDS


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vector(value, name: str) -> tuple[float, float]:
    if (not isinstance(value, list) or len(value) != 2 or
            any(type(x) not in (int, float) or not math.isfinite(x) for x in value)):
        raise ValueError("invalid source geometry vector: " + name)
    return float(value[0]), float(value[1])


def cross(a: tuple[float, float], b: tuple[float, float]) -> float:
    return a[0] * b[1] - a[1] * b[0]


def build(packet_path: Path, suffix: str) -> dict:
    if suffix not in KINDS:
        raise ValueError("unknown exact C153046 case")
    packet_path = Path(packet_path).resolve()
    root = packet_path.parent
    packet = json.loads(packet_path.read_text())
    if packet.get("format") != "c153046-reviewed-site-proposal" or not packet.get("reviewer"):
        raise ValueError("reviewed site proposal identity missing")
    required = {"opendrive", "signal_authority", "approach_lanes",
                "receiving_lanes", "stop_boundary"}
    sources = packet.get("sources", {})
    if set(sources) != required:
        raise ValueError("site proposal lacks exact source inventory")
    hashes = {}
    for name, descriptor in sources.items():
        if (not isinstance(descriptor, dict) or not descriptor.get("citation") or
                not descriptor.get("reviewer") or not descriptor.get("path")):
            raise ValueError("unreviewed source descriptor: " + name)
        source = (root / descriptor["path"]).resolve()
        if (not source.is_relative_to(root) or not source.is_file() or
                sha(source) != descriptor.get("sha256")):
            raise ValueError("retained source missing or changed: " + name)
        hashes[name] = descriptor["sha256"]
    approach = packet.get("approach", {})
    receiving = packet.get("receiving", {})
    signal = packet.get("signal", {})
    stop = packet.get("stop_boundary", {})
    _, lane_request, receiving_request, _ = KINDS[suffix]
    if (approach.get("one_way") is not True or
            receiving.get("one_way_to_left") is not (receiving_request == "one_way_left") or
            signal.get("phase_source") != "original_frame_history" or
            signal.get("head_configuration") != "red_alone" or
            not signal.get("native_actor_id") or
            stop.get("hierarchy_reviewed") is not True):
        raise ValueError("one-way, official signal or stop hierarchy unverified")
    incoming = vector(approach.get("direction_xy"), "approach direction")
    outgoing = vector(receiving.get("direction_xy"), "receiving direction")
    if (abs(math.hypot(*incoming) - 1) > 0.05 or
            abs(math.hypot(*outgoing) - 1) > 0.05 or cross(incoming, outgoing) < 0.7):
        raise ValueError("reviewed directions do not form a left turn")
    lanes = approach.get("lane_centers_xy", {})
    if not isinstance(lanes, dict) or len(lanes) < 2:
        raise ValueError("approach lacks distinct same-direction lanes")
    center = vector(approach.get("reference_xy"), "approach reference")
    lateral = {name: cross(incoming, tuple(point[i] - center[i] for i in (0, 1)))
               for name, point in ((name, vector(value, "lane " + name))
                                   for name, value in lanes.items())}
    if len({round(value, 3) for value in lateral.values()}) != len(lateral):
        raise ValueError("approach lanes overlap in lateral position")
    extreme = max(lateral, key=lateral.get)
    if approach.get("extreme_left_lane_id") != extreme:
        raise ValueError("named extreme-left lane differs from source geometry")
    stop_point = vector(stop.get("point_xy"), "stop boundary")
    stop_position = sum((stop_point[i] - center[i]) * incoming[i] for i in (0, 1))
    if not math.isfinite(stop_position):
        raise ValueError("invalid stop boundary position")
    selected = extreme if lane_request == "extreme_left" else min(lateral, key=lateral.get)
    return {"format": "c153046-source-bound-scene-draft",
            "case_id": AID + "__" + suffix,
            "selected_approach_lane_id": selected,
            "approach_reference_xy": center,
            "approach_lane_centers_xy": {name: vector(value, "lane " + name)
                                          for name, value in lanes.items()},
            "approach_direction_xy": incoming,
            "receiving_direction_xy": outgoing,
            "stop_boundary_progress_m": stop_position,
            "receiving_direction_request": receiving_request,
            "source_packet_sha256": sha(packet_path), "source_hashes": hashes,
            "source_custody_checked": True, "physical_realization_claimed": False,
            "legal_judgment": "unresolved"}
