"""CPU source-shaped diagnostics, not original Native observations."""

import copy
import hashlib
import json
from pathlib import Path

from measure_fixture import CAMERAS, FRAMES, measure


def context():
    return {"source_kind": "native_sidewalk_fixture_and_vehicle_readback",
            "native_map_sha256": "1" * 64, "fixture_identity_sha256": "2" * 64,
            "fixture_geometry_sha256": "3" * 64, "sidewalk_geometry_sha256": "4" * 64,
            "fixture_kind": "sidewalk_elevator",
            "fixture_bounds_m": {"min_x": 0, "max_x": 2, "min_y": 0, "max_y": 2},
            "sidewalk_bounds_m": {"min_x": -20, "max_x": 20, "min_y": 0, "max_y": 3}}


def trace(stop_center_x):
    rows = []
    for i in range(FRAMES):
        x = -50 + (stop_center_x + 50) * i / 100 if i < 100 else stop_center_x
        rows.append({"video_frame": i, "native_frame": 5000 + i, "time_s": i / 20,
                     "source_cameras": {name: i for name in CAMERAS},
                     "observed_vehicle_speed_mps": 3.0 if i < 100 else 0.0,
                     "vehicle_footprint_m": {"min_x": x - 2, "max_x": x + 2,
                                             "min_y": -2.5, "max_y": -0.3}})
    return rows


def reject(label, source, rows, expected):
    try:
        measure(source, rows)
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    source = context()
    outside, band = trace(10), trace(5)
    a, b = measure(source, outside), measure(source, band)
    assert a["rest_interval_frames"] == b["rest_interval_frames"] == [100, 599]
    assert a["within_five_foot_side_band_at_rest"] is False
    assert b["within_five_foot_side_band_at_rest"] is True
    assert a["directly_in_front_frame_count_at_rest"] == b["directly_in_front_frame_count_at_rest"] == 0
    negative = []
    bad = copy.deepcopy(source)
    bad.pop("fixture_identity_sha256")
    negative.append(reject("missing_fixture_identity", bad, band, "Missing source hash"))
    bad = copy.deepcopy(source)
    bad["fixture_kind"] = "unspecified"
    negative.append(reject("unknown_fixture", bad, band, "identity not sourced"))
    bad = copy.deepcopy(source)
    bad["fixture_bounds_m"]["min_y"] = -1
    negative.append(reject("fixture_outside_sidewalk", bad, band, "not contained"))
    negative.append(reject("short_capture", source, band[:-1], "Incomplete 30-second"))
    bad_rows = copy.deepcopy(band)
    bad_rows[250]["source_cameras"].pop("fixture_side")
    negative.append(reject("missing_camera", source, bad_rows, "Four source camera"))
    bad_rows = copy.deepcopy(band)
    bad_rows[250]["native_frame"] = bad_rows[249]["native_frame"]
    negative.append(reject("repeated_native_frame", source, bad_rows, "Native frame identity"))
    bad_rows = copy.deepcopy(band)
    for row in bad_rows:
        row["observed_vehicle_speed_mps"] = 3.0
    negative.append(reject("no_stop", source, bad_rows, "five-second stop"))
    proof = {"format": "worker-cpu-sidewalk-fixture-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "positive": {"outside": a, "side_band": b}, "negative": negative}
    path = Path(__file__).with_name("fixture-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
