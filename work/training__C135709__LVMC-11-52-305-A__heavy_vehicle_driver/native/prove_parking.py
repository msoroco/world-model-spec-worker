"""CPU-only source-shaped tests for parking geometry measurement."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from measure_parking import CAMERAS, FRAMES, measure


def context():
    return {
        "source_kind": "native_map_and_external_status_readback",
        "native_map_sha256": "1" * 64,
        "park_status_document_sha256": "2" * 64,
        "vehicle_specification_sha256": "3" * 64,
        "park_status": "public_park",
        "vehicle_class": "commercial_motor_vehicle",
        "vehicle_overall_length_m": 8.0,
        "vehicle_unladen_mass_kg": 4000.0,
        "street_bounds_m": {"min_x": -100.0, "max_x": 100.0, "min_y": -3.0, "max_y": 3.0},
        "park_bounds_m": {"min_x": 10.0, "max_x": 70.0, "min_y": 3.0, "max_y": 20.0},
    }


def trace(parked_x):
    rows = []
    for index in range(FRAMES):
        # Source-shaped diagnostic only; these speeds are not original CARLA velocity.
        moving = index < 100
        center_x = -80.0 + (parked_x + 80.0) * index / 100 if moving else parked_x
        rows.append({
            "video_frame": index,
            "native_frame": 2000 + index,
            "time_s": index / 20,
            "source_cameras": {camera: index for camera in CAMERAS},
            "observed_speed_mps": 3.0 if moving else 0.0,
            "vehicle_footprint_m": {"min_x": center_x - 4.0, "max_x": center_x + 4.0, "min_y": -2.4, "max_y": 0.1},
        })
    return rows


def rejects(label, source, rows, expected):
    try:
        measure(source, rows)
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError(f"{label}: unexpected rejection {error}") from error
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label}: expected rejection")


def run():
    source = context()
    away = trace(-30.0)
    beside = trace(40.0)
    a = measure(source, away)
    b = measure(source, beside)
    assert a["frame_count"] == b["frame_count"] == 600
    assert a["rest_duration_s"] == b["rest_duration_s"] == 25.0
    assert a["park_frontage_overlap_at_rest"] is False
    assert b["park_frontage_overlap_at_rest"] is True
    assert a["legal_compliance"] == b["legal_compliance"] == "unassessed"
    negative = []
    bad = copy.deepcopy(source)
    bad.pop("park_status_document_sha256")
    negative.append(rejects("missing_park_status_source", bad, beside, "Missing source hash"))
    bad = copy.deepcopy(source)
    bad["park_status"] = "unknown"
    negative.append(rejects("unknown_park_status", bad, beside, "Public park status"))
    bad = copy.deepcopy(source)
    bad["park_bounds_m"]["min_y"] = 4.0
    negative.append(rejects("disjoint_park_boundary", bad, beside, "share a surveyed boundary"))
    negative.append(rejects("short_capture", source, beside[:-1], "Incomplete 30-second"))
    bad_rows = copy.deepcopy(beside)
    bad_rows[300]["source_cameras"].pop("curb")
    negative.append(rejects("missing_camera", source, bad_rows, "Missing four source camera"))
    bad_rows = copy.deepcopy(beside)
    bad_rows[300]["native_frame"] = bad_rows[299]["native_frame"]
    negative.append(rejects("native_frame_gap", source, bad_rows, "Native frame identity gap"))
    bad_rows = copy.deepcopy(beside)
    bad_rows[300]["time_s"] += 0.05
    negative.append(rejects("time_join", source, bad_rows, "Native trace time join failed"))
    bad_rows = copy.deepcopy(beside)
    for row in bad_rows:
        row["observed_speed_mps"] = 3.0
    negative.append(rejects("no_rest", source, bad_rows, "No measured five-second"))
    return {"format": "worker-cpu-parking-proof", "diagnostic_only": True,
            "fixtures_are_original_native": False, "positive": {"away": a, "beside": b},
            "negative": negative, "passed": True}


if __name__ == "__main__":
    proof = run()
    path = Path(__file__).with_name("parking-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(proof["negative"]),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
