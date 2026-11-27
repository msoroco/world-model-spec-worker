"""Saved-only, hash-bound rider-arm diagnostic from original Native sources.

This diagnostic deliberately leaves pixel visibility and legal findings unresolved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from measure_general_signal import measure_left_upward
from measure_hand_signal import measure as measure_right_horizontal
from source_rows import make_rows


SOURCES = ("rider_arm.jsonl", "camera_frames.jsonl", "road_context.json")
ORIGINAL_SOURCES = ("road.xodr", "map_readback.json", "overview.mkv",
                    "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path):
    if not path.is_file():
        raise ValueError("Missing original source: " + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(root: Path, *, allow_fixture=False):
    root = Path(root)
    seal_path = root / "capture-seal.json"
    if not seal_path.is_file():
        raise ValueError("Original Native capture seal missing")
    seal = json.loads(seal_path.read_text())
    if seal.get("format") != "worker-sealed-capture" or seal.get("provenance_kind") != "native":
        raise ValueError("Original Native capture provenance missing")
    if seal.get("diagnostic_fixture") is not bool(allow_fixture):
        raise ValueError("Fixture/original mode differs from capture seal")
    for name in SOURCES + (() if allow_fixture else ORIGINAL_SOURCES):
        path = root / name
        if not path.is_file() or seal.get("sources", {}).get(name) != _hash(path):
            raise ValueError("Missing or stale sealed source: " + name)
    context = json.loads((root / "road_context.json").read_text())
    if not allow_fixture and (
            context.get("authored_road_sha256") != _hash(root / "road.xodr") or
            context.get("map_readback_sha256") != _hash(root / "map_readback.json")):
        raise ValueError("Original roadway map readback changed")
    rig_rows = _rows(root / "rider_arm.jsonl")
    camera_rows = _rows(root / "camera_frames.jsonl")
    rows = make_rows(rig_rows, camera_rows, context)
    measurement_context = {
        "machine_class": context.get("machine_class"),
        "machine_class_source": context.get("machine_class_source_id"),
        "operator_id": str(context["rider_actor_id"]),
        "operator_id_source": context.get("rider_mount_source_id"),
        "roadway_polygon_source": context.get("roadway_polygon_source_id"),
        "connected_right_turn_route_source": context.get("right_turn_route_source_id"),
        "keypoint_capture_source": context.get("rider_arm_source_id"),
        "camera_calibration_source": context.get("camera_calibration_source_id"),
        "derived_channels_used": False,
    }
    right = measure_right_horizontal(rows, measurement_context)
    # The 3D analyzer consumes the exact saved rider-arm readback, enriched only
    # with independently derived roadway and route occupancy from the map.
    left_rows = []
    for raw, derived in zip(rig_rows, rows):
        left_rows.append(dict(raw, time_s=derived["time_s"],
                              roadway_occupied=derived["roadway_occupied"],
                              on_right_turn_route=derived["on_right_turn_route"]))
    left = measure_left_upward(left_rows, rider_id=context["rider_actor_id"],
                               bicycle_id=context["bicycle_actor_id"],
                               source_packet={
                                   "kind": "original_native_arm_readback",
                                   "rider_actor_id": context["rider_actor_id"],
                                   "bicycle_actor_id": context["bicycle_actor_id"],
                               })
    return {
        "format": "worker-rider-arm-diagnostic",
        "source_hashes": {name: seal["sources"][name] for name in SOURCES},
        "right_horizontal": right,
        "left_upward": left,
        "original_pixels_verified": False,
        "physical_mount_verified": False,
        "legal_conclusion": None,
        "diagnostic_fixture": bool(allow_fixture),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = analyze(args.source_dir)
    args.output.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
