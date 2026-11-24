"""CPU source-shaped paired meeting proof; motion and hashes are invented."""

import hashlib
import json
from pathlib import Path

from measure_meeting import CAMERAS, FRAMES, measure


def context():
    result = {"source_kind": "original_native_opposite_meeting_readback",
              "one_lane_each_direction_verified": True,
              "paved_left_y_m": -4, "paved_center_y_m": 0, "paved_right_y_m": 4}
    for index, name in enumerate(("native_map", "paved_bounds", "lane_direction", "ego_body",
                                  "oncoming_body", "vehicle_motion"), 1):
        result[name + "_sha256"] = f"{index:x}" * 64
    return result


def trace(right_fraction=0.45):
    ego_y = 1 - 2 * right_fraction
    return [{"video_frame": i, "native_frame": 500000 + i, "time_s": i / 20,
             "source_cameras": {name: i for name in CAMERAS},
             "ego_x_m": -60 + 5 * i / 20, "oncoming_x_m": 60 - 5 * i / 20,
             "ego_y_m": ego_y, "oncoming_y_m": 2.5,
             "ego_width_m": 2.0, "oncoming_width_m": 2.0,
             "ego_vx_mps": 5.0, "oncoming_vx_mps": -5.0}
            for i in range(FRAMES)]


def reject(label, source, rows, expected):
    try:
        measure(source, rows)
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    less = measure(context(), trace(0.45))
    more = measure(context(), trace(0.55))
    assert abs(less["ego_right_paved_half_footprint_fraction_min"] - 0.45) < 1e-9
    assert abs(more["ego_right_paved_half_footprint_fraction_min"] - 0.55) < 1e-9
    assert less["minimum_lateral_surface_gap_m"] < more["minimum_lateral_surface_gap_m"]
    assert less["ego_passed_to_right_of_other_center"] and more["ego_passed_to_right_of_other_center"]
    assert less["legal_compliance"] == more["legal_compliance"] == "unassessed"
    negative = []
    source = context()
    source.pop("paved_bounds_sha256")
    negative.append(reject("missing_pavement_source", source, trace(), "source hash"))
    source = context()
    source["one_lane_each_direction_verified"] = False
    negative.append(reject("wrong_lane_count", source, trace(), "One lane"))
    negative.append(reject("short_capture", context(), trace()[:-1], "Incomplete"))
    rows = trace()
    rows[300]["source_cameras"].pop("meeting_side")
    negative.append(reject("missing_camera", context(), rows, "Four source camera"))
    rows = trace()
    rows[300]["native_frame"] = rows[299]["native_frame"]
    negative.append(reject("duplicate_native_frame", context(), rows, "Native frame"))
    rows = trace()
    rows[300]["oncoming_vx_mps"] = 5
    negative.append(reject("same_direction", context(), rows, "Opposite motion"))
    rows = trace()
    for row in rows:
        row["oncoming_x_m"] = 1000
    negative.append(reject("no_meeting", context(), rows, "No observed"))
    proof = {"format": "worker-cpu-opposite-meeting-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "positive": {"requested_0.45": less, "requested_0.55": more}, "negative": negative}
    path = Path(__file__).with_name("meeting-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
