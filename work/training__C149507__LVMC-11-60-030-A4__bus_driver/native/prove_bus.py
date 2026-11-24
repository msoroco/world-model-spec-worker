"""Source-shaped CPU diagnostics; no original CARLA wheel measurements."""

import copy
import hashlib
import json
from pathlib import Path

from measure_bus import CAMERAS, FRAMES, measure


def context():
    return {"source_kind": "native_bus_wheel_curb_and_traffic_readback",
            "native_map_sha256": "1" * 64, "curb_calibration_sha256": "2" * 64,
            "bus_classification_sha256": "3" * 64, "wheel_geometry_sha256": "4" * 64,
            "loading_zone_sha256": "5" * 64, "vehicle_class": "non_tour_bus",
            "location_kind": "bus_stop", "public_street": True, "curb_face_y_m": 0.0}


def trace(wheel_gap_m):
    return [{"video_frame": i, "native_frame": 3000 + i, "time_s": i / 20,
             "source_cameras": {name: i for name in CAMERAS},
             "bus_observed_speed_mps": 3.0 if i < 100 else 0.0,
             "right_front_wheel_contact_y_m": wheel_gap_m,
             "bus_curb_heading_difference_deg": 2.0,
             "loading_activity_observed": i >= 100,
             "other_vehicle_observed_speed_mps": 4.0 if i < 180 else 2.5,
             "other_vehicle_delay_s": 0.0 if i < 180 else 0.5}
            for i in range(FRAMES)]


def reject(label, source, rows, expected):
    try:
        measure(source, rows)
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    source = context()
    near = trace(0.30)
    far = trace(0.70)
    a, b = measure(source, near), measure(source, far)
    assert a["all_loading_frames_within_18_inches"] is True
    assert b["all_loading_frames_within_18_inches"] is False
    assert a["stopped_loading_interval_frames"] == b["stopped_loading_interval_frames"] == [100, 599]
    assert a["unduly_impede"] == b["unduly_impede"] == "requires_independent_judgment"
    negative = []
    bad = copy.deepcopy(source)
    bad.pop("wheel_geometry_sha256")
    negative.append(reject("missing_wheel_source", bad, near, "Missing source hash"))
    bad = copy.deepcopy(source)
    bad.pop("curb_calibration_sha256")
    negative.append(reject("missing_curb_source", bad, near, "Missing source hash"))
    bad = copy.deepcopy(source)
    bad["vehicle_class"] = "tour_bus"
    negative.append(reject("tour_bus", bad, near, "non-tour bus"))
    bad = copy.deepcopy(source)
    bad["public_street"] = False
    negative.append(reject("not_public_street", bad, near, "Public street"))
    negative.append(reject("short_capture", source, near[:-1], "Incomplete 30-second"))
    bad_rows = copy.deepcopy(near)
    bad_rows[250]["source_cameras"].pop("curb_wheel")
    negative.append(reject("missing_camera", source, bad_rows, "Four source camera"))
    bad_rows = copy.deepcopy(near)
    bad_rows[250]["right_front_wheel_contact_y_m"] = float("nan")
    negative.append(reject("invalid_wheel_geometry", source, bad_rows, "front wheel contact"))
    bad_rows = copy.deepcopy(near)
    for row in bad_rows:
        row["loading_activity_observed"] = False
    negative.append(reject("no_loading", source, bad_rows, "stopped loading interval"))
    proof = {"format": "worker-cpu-bus-wheel-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "positive": {"near": a, "far": b}, "negative": negative}
    path = Path(__file__).with_name("bus-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
