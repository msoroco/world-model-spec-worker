"""Synthetic source-shaped governed-zone parking comparison proof."""

import hashlib
import json
from pathlib import Path

from measure_prohibited_parking import CAMERAS, FRAMES, HASHES, measure
from prohibited_parking_scene import CASES, request, validate


def context():
    result = {"source_kind": "original_native_device_parking_readback",
              "device_code": "no_parking", "device_official": True,
              "condition_in_effect": True, "vehicle_action": "park",
              "traffic_conflict_necessity": False, "law_compliance_exception": False,
              "police_direction_exception": False, "device_direction_exception": False,
              "governed_start_x_m": -20, "governed_end_x_m": 0}
    for name in HASHES:
        result[name + "_sha256"] = hashlib.sha256(("synthetic-fixture:" + name).encode()).hexdigest()
    return result


def trace(case):
    target = CASES[case]
    rows = []
    for i in range(FRAMES):
        if i < 200:
            x, speed, brake = -45 + (target + 45) * i / 200, (target + 45) / 10, False
        elif i <= 450:
            x, speed, brake = target, 0, True
        else:
            x, speed, brake = target + (i - 450) * 0.1, 2, False
        rows.append({"video_frame": i, "native_frame": 600000 + i, "time_s": i / 20,
                     "source_cameras": {name: i for name in CAMERAS}, "ego_x_m": x,
                     "ego_length_m": 4.5, "ego_speed_mps": speed,
                     "parking_brake_applied": brake})
    return rows


def reject(label, source, rows, expected):
    try:
        measure(source, rows)
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(label + " unexpectedly passed")


if __name__ == "__main__":
    scenes = {case: validate(request(case)) for case in CASES}
    outside = measure(context(), trace("false"))
    inside = measure(context(), trace("true"))
    assert outside["parked_frame_count"] == inside["parked_frame_count"] == 251
    assert outside["parked_zone_overlap_frame_count"] == 0
    assert inside["parked_zone_overlap_frame_count"] == 251
    assert outside["legal_compliance"] == inside["legal_compliance"] == "unassessed"
    negative = []
    source = context()
    source.pop("regulatory_device_sha256")
    negative.append(reject("missing_device_source", source, trace("true"), "source hash"))
    source = context()
    source["device_official"] = False
    negative.append(reject("unofficial_device", source, trace("true"), "Official"))
    source = context()
    source["condition_in_effect"] = False
    negative.append(reject("inactive_condition", source, trace("true"), "condition"))
    source = context()
    source["police_direction_exception"] = True
    negative.append(reject("police_exception", source, trace("true"), "Exception"))
    negative.append(reject("short_capture", context(), trace("true")[:-1], "Incomplete"))
    rows = trace("true")
    rows[250]["source_cameras"].pop("curb_side")
    negative.append(reject("missing_camera", context(), rows, "camera"))
    rows = trace("true")
    for row in rows:
        row["parking_brake_applied"] = False
    negative.append(reject("not_parked", context(), rows, "Parked"))
    proof = {"format": "worker-cpu-device-parking-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "scenes": scenes, "positive": {"outside_zone": outside, "inside_zone": inside},
             "negative": negative}
    path = Path(__file__).with_name("prohibited-parking-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
