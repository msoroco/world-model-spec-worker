"""Synthetic source-shaped right-wheel curb boundary diagnostic."""

import hashlib
import json
from pathlib import Path

from measure_right_curb import CAMERAS, FRAMES, HASHES, measure
from right_curb_scene import CLEARANCES_IN, request, validate


def context():
    result = {"source_kind": "original_native_right_curb_readback",
              "highway_has_adjacent_curbs": True, "right_curb_verified": True,
              "left_curb_ordinance_permits": False, "angle_parking_ordinance_permits": False,
              "right_curb_y_m": -4}
    for name in HASHES:
        result[name + "_sha256"] = hashlib.sha256(("synthetic-fixture:" + name).encode()).hexdigest()
    return result


def trace(case):
    wheel_y = -4 + CLEARANCES_IN[case] * 0.0254
    rows = []
    for i in range(FRAMES):
        parked = 200 <= i <= 450
        rows.append({"video_frame": i, "native_frame": 750000 + i, "time_s": i / 20,
                     "source_cameras": {name: i for name in CAMERAS},
                     "ego_speed_mps": 0 if parked else 2,
                     "parking_brake_applied": parked,
                     "right_front_wheel_outer_y_m": wheel_y,
                     "right_rear_wheel_outer_y_m": wheel_y,
                     "ego_heading_deg": 0, "curb_heading_deg": 0})
    return rows


def reject(label, source, rows, expected):
    try:
        measure(source, rows)
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(label + " unexpectedly passed")


if __name__ == "__main__":
    scenes = {case: validate(request(case)) for case in CLEARANCES_IN}
    measured = {case: measure(context(), trace(case)) for case in CLEARANCES_IN}
    for case, value in measured.items():
        assert abs(value["right_front_wheel_gap_in_min"] - CLEARANCES_IN[case]) < 1e-9
        assert abs(value["right_rear_wheel_gap_in_max"] - CLEARANCES_IN[case]) < 1e-9
        assert value["parked_frame_count"] == 251
        assert value["maximum_heading_difference_deg"] == 0
        assert value["legal_compliance"] == "unassessed"
    negative = []
    source = context()
    source.pop("right_curb_sha256")
    negative.append(reject("missing_curb_source", source, trace("18"), "source hash"))
    source = context()
    source["left_curb_ordinance_permits"] = True
    negative.append(reject("ordinance_exception", source, trace("18"), "exception"))
    negative.append(reject("short_capture", context(), trace("18")[:-1], "Incomplete"))
    rows = trace("18")
    rows[200]["source_cameras"].pop("wheel_closeup")
    negative.append(reject("missing_camera", context(), rows, "camera"))
    rows = trace("18")
    rows[200]["native_frame"] = rows[199]["native_frame"]
    negative.append(reject("duplicate_native_frame", context(), rows, "Native frame"))
    rows = trace("18")
    rows[200]["right_front_wheel_outer_y_m"] = -4.1
    negative.append(reject("wheel_beyond_curb", context(), rows, "Wheel beyond curb"))
    rows = trace("18")
    for row in rows:
        row["parking_brake_applied"] = False
    negative.append(reject("no_parked_interval", context(), rows, "interval"))
    proof = {"format": "worker-cpu-right-curb-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "scenes": scenes, "positive": measured, "negative": negative}
    path = Path(__file__).with_name("right-curb-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
