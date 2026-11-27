"""Source-bound freight curb zone observation over 600 joined Native frames.

Expeditious and temporary remain statutory judgments; no time cutoff is made.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


FRAMES = 600
RATE_HZ = 20
CAMERAS = {"overview", "approach", "reference_corner", "driver_reference"}


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Invalid {name}")
    return float(value)


def source_hash(value, name):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"Missing source hash: {name}")


def measure(context, rows):
    if context.get("source_kind") != "original_native_freight_zone_sources":
        raise ValueError("Original freight zone sources missing")
    for name in ("native_map_sha256", "zone_marking_sha256", "regulatory_sign_sha256",
                 "sign_hours_source_sha256", "civil_time_source_sha256", "vehicle_identity_sha256",
                 "material_activity_source_sha256", "passenger_activity_source_sha256",
                 "waiting_vehicle_source_sha256"):
        source_hash(context.get(name), name)
    if context.get("zone_kind") != "freight_curb_loading":
        raise ValueError("Freight curb zone not sourced")
    start = finite(context.get("effective_start_minute_local"), "sign start")
    end = finite(context.get("effective_end_minute_local"), "sign end")
    if not 0 <= start < end <= 1440:
        raise ValueError("Invalid source sign hours")
    if len(rows) != FRAMES:
        raise ValueError("Incomplete 30-second Native trace")
    previous_native = None
    active = []
    zone_stopped = []
    materials = []
    passengers = []
    waiting = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("video_frame") != index:
            raise ValueError("Video frame identity gap")
        native = row.get("native_frame")
        if type(native) is not int or (previous_native is not None and native <= previous_native):
            raise ValueError("Native frame identity gap")
        previous_native = native
        if abs(finite(row.get("time_s"), "Native time") - index / RATE_HZ) > 1e-6:
            raise ValueError("Native time join failed")
        cameras = row.get("source_cameras")
        if not isinstance(cameras, dict) or set(cameras) != CAMERAS or any(cameras[name] != native for name in CAMERAS):
            raise ValueError("Four source camera frame join failed")
        local_minute = finite(row.get("civil_minute_local"), "civil time")
        if not 0 <= local_minute < 1440:
            raise ValueError("Civil time outside day")
        if row.get("vehicle_id") != context.get("vehicle_id"):
            raise ValueError("Vehicle identity source differs")
        if row.get("zone_occupancy") not in {"within_marked_zone", "outside_zone", "unknown"}:
            raise ValueError("Marked zone occupancy source missing")
        speed = finite(row.get("observed_speed_mps"), "observed speed")
        if speed < 0:
            raise ValueError("Negative observed speed")
        material = row.get("material_activity")
        if material not in {"pickup_loading", "unloading_delivery", "none_observed", "unknown"}:
            raise ValueError("Material activity source missing")
        passenger = row.get("passenger_activity")
        if passenger not in {"loading", "unloading", "none_observed", "unknown"}:
            raise ValueError("Passenger activity source missing")
        wait_state = row.get("material_vehicle_wait_state")
        if wait_state not in {"waiting_to_enter", "about_to_enter", "none_observed", "unknown"}:
            raise ValueError("Material vehicle wait source missing")
        active.append(start <= local_minute < end)
        zone_stopped.append(row["zone_occupancy"] == "within_marked_zone" and speed <= 0.10)
        materials.append(material)
        passengers.append(passenger)
        waiting.append(wait_state)
    return {
        "format": "worker-source-freight-curb-zone-measurement",
        "frame_count": FRAMES, "rate_hz": RATE_HZ,
        "sign_effective_frames": sum(active),
        "zone_stopped_during_effective_hours_frames": sum(a and z for a, z in zip(active, zone_stopped)),
        "material_handling_observed_frames": sum(z and m in {"pickup_loading", "unloading_delivery"} for z, m in zip(zone_stopped, materials)),
        "stopped_without_material_handling_frames": sum(a and z and m == "none_observed" for a, z, m in zip(active, zone_stopped, materials)),
        "passenger_exchange_observed_frames": sum(z and p in {"loading", "unloading"} for z, p in zip(zone_stopped, passengers)),
        "material_vehicle_waiting_or_about_to_enter_frames": sum(w in {"waiting_to_enter", "about_to_enter"} for w in waiting),
        "passenger_exchange_with_waiting_material_vehicle_frames": sum(
            z and p in {"loading", "unloading"} and w in {"waiting_to_enter", "about_to_enter"}
            for z, p, w in zip(zone_stopped, passengers, waiting)),
        "expeditious_or_temporary": "independent_judgment_required",
        "interference": "requires_original_spatial_and_temporal_review",
        "legal_compliance": "unassessed",
        "limitations": [
            "Thirty-second fixture evidence cannot establish expeditious or temporary as legal cutoffs",
            "Sign hours, markings, actor/material identities and civil clock require original-source review",
            "Waiting or about-to-enter state alone does not prove interference",
            "No material observed in a diagnostic fixture is not proof of absence in an original recording",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.trace.read_text().splitlines() if line]
    args.output.write_text(json.dumps(measure(json.loads(args.context.read_text()), rows), indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
