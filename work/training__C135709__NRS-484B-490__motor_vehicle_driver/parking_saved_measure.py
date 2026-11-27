"""Saved-packet geometry diagnostic for NRS 484B.490.

The output is factual only. 'Narrow', 'official', and the device's governed
extent require independent source review before a legal conclusion.
"""
from __future__ import annotations

import hashlib
import json

ASSIGNMENT = "training__C135709__NRS-484B-490__motor_vehicle_driver"
ASSIGNMENT_SHA = "6cbfded183e4f759d035d794f63d3366259b30e14ca2c42f87e270659b7f96a2"
WITNESS_SHA = "651e6601af7532e0b33c1fac6899fa5f20d478e6e499caec055d7a4f9ad078a6"


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def measure(packet_bytes: bytes, inventory_bytes: bytes) -> dict:
    packet = json.loads(packet_bytes)
    inventory = json.loads(inventory_bytes)
    require(packet["assignment_id"] == ASSIGNMENT and inventory["assignment_id"] == ASSIGNMENT, "assignment mismatch")
    kind = packet["source_kind"]
    require(kind in {"synthetic_native_sample", "native_saved_sample"} and inventory["source_kind"] == kind, "source kind mismatch")
    require(inventory["road_type"] == "highway", "highway source missing")
    require(inventory["narrow_section_source_id"], "narrow section source missing")
    require(inventory["measured_road_width_m"] > 0, "road width measurement missing")
    require(inventory["device_id"] and inventory["device_erected"] is True, "erected device missing")
    require(inventory["device_official_source_id"], "official-device authority missing")
    require(inventory["device_prohibits_parking"] is True, "parking prohibition missing")
    x0, y0, x1, y1 = inventory["governed_extent_xyxy_m"]
    require(x0 < x1 and y0 < y1, "governed extent missing")
    frames = packet["frames"]
    require(len(frames) >= 600, "recording shorter than 30 seconds")
    require(all(f["frame"] == i and abs(f["t_s"] - i / 20) < 1e-8 for i, f in enumerate(frames)), "noncontiguous 20 Hz frames")
    require(all(f["vehicle_id"] == packet["vehicle_id"] for f in frames), "vehicle identity changed")
    require(all(f["speed_mps"] >= 0 for f in frames), "invalid speed")
    require(all(f["bbox_half_length_m"] > 0 and f["bbox_half_width_m"] > 0 for f in frames), "vehicle footprint missing")
    # Near-zero is a diagnostic tolerance, not a definition of parking.
    stationary = [f for f in frames if f["speed_mps"] <= 0.1]
    inside = [f["frame"] for f in stationary if
              x0 <= f["x_m"] - f["bbox_half_length_m"] and
              f["x_m"] + f["bbox_half_length_m"] <= x1 and
              y0 <= f["y_m"] - f["bbox_half_width_m"] and
              f["y_m"] + f["bbox_half_width_m"] <= y1]
    return {
        "format": "c135709-saved-parking-diagnostic-v1",
        "assignment_id": ASSIGNMENT,
        "source_kind": kind,
        "packet_sha256": digest(packet_bytes),
        "inventory_sha256": digest(inventory_bytes),
        "frame_count": len(frames),
        "duration_s": len(frames) / 20,
        "narrow_section_source_id": inventory["narrow_section_source_id"],
        "measured_road_width_m": inventory["measured_road_width_m"],
        "device_id": inventory["device_id"],
        "device_official_source_id": inventory["device_official_source_id"],
        "governed_extent_xyxy_m": inventory["governed_extent_xyxy_m"],
        "stationary_frame_count": len(stationary),
        "stationary_footprint_fully_within_governed_extent_frames": inside,
        "legal_result": None,
        "unresolved": ["independent narrow-highway classification", "official device provenance", "legal meaning of parking", "physical source validity"],
    }
