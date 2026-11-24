"""Acquire source-bound Native sight packets for the saved NRS 484B.407 audit.

The adapter supplies observed engine state; this module does not synthesize
terrain, road classification, vehicle motion, or visibility judgments.
"""
from __future__ import annotations

import hashlib
import json
import math
import tempfile
from pathlib import Path

from sight_measurement import ASSIGNMENT, DIRECTIONS, STATIONS_M, measure


def _require_native(packet: dict, label: str) -> dict:
    if not isinstance(packet, dict) or packet.get("source_kind") != "original_native":
        raise ValueError(f"{label} lacks original Native provenance")
    return packet


def capture(adapter, case_id: str, destination: Path, frame_count: int = 900,
            recording_id: str | None = None) -> dict:
    """Collect 20 Hz frame, motion and turn-ray records from a Native adapter.

    Adapter methods: geometry(), tick(), ego(frame), ray(frame, direction,
    station_m). Each must return observed packets with source_kind. Geometry
    also binds the loaded road map digest to its reviewed source digest.
    """
    if not case_id.startswith(ASSIGNMENT + "__") or type(frame_count) is not int or frame_count < 900:
        raise ValueError("exact case and at least 900 frames required")
    destination = Path(destination)
    if destination.exists():
        raise ValueError("refusing to overwrite sight attempt")
    geometry = adapter.geometry()
    if not isinstance(geometry, dict) or geometry.get("source_kind") != "original_native_geometry":
        raise ValueError("original Native road geometry required")
    expected = geometry.get("map_source_sha256")
    if not isinstance(expected, str) or len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        raise ValueError("reviewed map source digest required")
    if geometry.get("loaded_map_sha256") != expected:
        raise ValueError("loaded map differs from reviewed source")
    if not geometry.get("ego_vehicle_id") or not geometry.get("highway_source"):
        raise ValueError("road and subject vehicle source required")
    probe_targets_ft = {"distance_below_500ft": 499,
                        "distance_at_500ft": 500,
                        "distance_above_500ft": 501}
    probe_target = probe_targets_ft.get(case_id.removeprefix(ASSIGNMENT + "__"))
    if probe_target is not None and not geometry.get("approach_vehicle_id"):
        raise ValueError("distance probe needs original approaching vehicle identity")
    frames, motion, rays, approach = [], [], [], []
    for _ in range(frame_count):
        frame = _require_native(adapter.tick(), "frame")
        frame_row = {"frame": frame.get("frame"), "time_s": frame.get("time_s")}
        frames.append(frame_row)
        ego = _require_native(adapter.ego(frame), "ego motion")
        if ego.get("vehicle_id") != geometry["ego_vehicle_id"]:
            raise ValueError("subject vehicle identity changed")
        motion.append({"frame": frame_row["frame"], "time_s": frame_row["time_s"],
                       "yaw_deg": ego.get("yaw_deg"), "turn_active": ego.get("turn_active")})
        if ego.get("turn_active") is True:
            if probe_target is not None:
                observed = _require_native(adapter.approach(frame), "approaching vehicle")
                if (observed.get("frame") != frame_row["frame"] or
                        observed.get("time_s") != frame_row["time_s"] or
                        observed.get("vehicle_id") != geometry["approach_vehicle_id"]):
                    raise ValueError("approaching vehicle frame or identity mismatch")
                ego_xyz, other_xyz = observed.get("ego_position"), observed.get("approach_position")
                if (not isinstance(ego_xyz, dict) or not isinstance(other_xyz, dict) or
                        any(not isinstance(pos.get(axis), (int, float)) or
                            not math.isfinite(pos[axis])
                            for pos in (ego_xyz, other_xyz) for axis in ("x", "y", "z"))):
                    raise ValueError("original approaching vehicle positions required")
                distance_m = math.dist([ego_xyz[a] for a in ("x", "y", "z")],
                                       [other_xyz[a] for a in ("x", "y", "z")])
                approach.append({"frame": frame_row["frame"], "time_s": frame_row["time_s"],
                                 "vehicle_id": observed["vehicle_id"],
                                 "ego_position": ego_xyz, "approach_position": other_xyz,
                                 "measured_distance_m": distance_m})
            for direction in DIRECTIONS:
                for station in STATIONS_M:
                    ray = _require_native(adapter.ray(frame, direction, station), "sight ray")
                    if (ray.get("frame") != frame_row["frame"] or
                            ray.get("time_s") != frame_row["time_s"] or
                            ray.get("direction") != direction or
                            ray.get("station_distance_m") != station):
                        raise ValueError("Native ray frame or station mismatch")
                    rays.append({key: ray.get(key) for key in
                                 ("frame", "time_s", "direction", "station_distance_m",
                                  "observer_height_m", "observer_lane_source",
                                  "target_vehicle_id", "body_point_clear", "terrain_hit_id")})
    packets = {
        "frame_map": {"frames": frames},
        "ego_motion": {"case_id": case_id, "source_kind": "original_native", "samples": motion},
        "sight_rays": {"case_id": case_id, "source_kind": "original_native", "samples": rays},
        "road_geometry": geometry,
    }
    if probe_target is not None:
        if not approach:
            raise ValueError("distance probe lacks original turn approach samples")
        target_m = probe_target * 0.3048
        first_m = approach[0]["measured_distance_m"]
        if abs(first_m - target_m) > 0.1:
            raise ValueError("original approach distance misses probe target")
        approach_packet = {"case_id": case_id,
                           "source_kind": "original_native", "samples": approach,
                           "probe_target_ft": probe_target,
                           "first_turn_distance_m": first_m,
                           "engineering_tolerance_m": 0.1,
                           "legal_visibility_judgment": "unresolved"}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="native-sight-", dir=destination.parent) as tmp:
        root = Path(tmp)
        inventory = {"case_id": case_id, "source_kind": "original_native", "sources": {}}
        if recording_id is not None:
            if (len(recording_id) != 64 or
                    any(c not in "0123456789abcdef" for c in recording_id)):
                raise ValueError("exact recording ID digest required")
            inventory["recording_id"] = recording_id
        for name, packet in packets.items():
            path = root / f"{name}.json"
            path.write_text(json.dumps(packet, sort_keys=True, separators=(",", ":")) + "\n")
            inventory["sources"][name] = {"path": path.name,
                                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        measured = measure(root, inventory, case_id)
        if probe_target is not None:
            approach_path = root / "approach_motion.json"
            approach_path.write_text(json.dumps(approach_packet, sort_keys=True,
                                                separators=(",", ":")) + "\n")
            inventory["approach_probe"] = {"path": approach_path.name,
                                           "sha256": hashlib.sha256(approach_path.read_bytes()).hexdigest()}
        (root / "inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
        root.rename(destination)
    if probe_target is not None:
        measured["approach_distance_probe"] = {
            "target_ft": probe_target, "first_turn_distance_m": first_m,
            "engineering_tolerance_m": 0.1,
            "legal_visibility_judgment": "unresolved"}
    return measured
