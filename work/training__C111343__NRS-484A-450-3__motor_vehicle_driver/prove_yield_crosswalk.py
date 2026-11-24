"""Synthetic source-shaped conditional crosswalk-stop comparison proof."""

import hashlib
import json
from pathlib import Path

from measure_yield_crosswalk import CAMERAS, FRAMES, HASHES, measure
from yield_crosswalk_scene import CASES, request, validate


def context():
    result = {"source_kind": "original_native_yield_crosswalk_readback",
              "governing_yield_sign": True, "near_side_crosswalk": True,
              "safety_stop_requirement_sourced": True,
              "crosswalk_near_x_m": -6, "crosswalk_far_x_m": -4,
              "intersection_near_x_m": -3.5}
    for name in HASHES:
        result[name + "_sha256"] = hashlib.sha256(("synthetic-fixture:" + name).encode()).hexdigest()
    return result


def trace(case):
    stop_center = CASES[case] - 2.25
    rows = []
    for i in range(FRAMES):
        if i < 100:
            x = -45 + (stop_center + 45) * i / 100
            speed = (stop_center + 45) / 5
        elif i < 200:
            x, speed = stop_center, 0
        else:
            x, speed = stop_center + (i - 200) * 0.25, 5
        rows.append({"video_frame": i, "native_frame": 800000 + i, "time_s": i / 20,
                     "source_cameras": {name: i for name in CAMERAS}, "ego_x_m": x,
                     "ego_length_m": 4.5, "ego_speed_mps": speed,
                     "intersecting_vehicle_y_m": -40 + i * 0.25})
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
    before = measure(context(), trace("before_crosswalk"))
    past = measure(context(), trace("past_crosswalk"))
    assert before["first_stop_before_crosswalk"] is True
    assert past["first_stop_before_crosswalk"] is False and past["first_stop_in_crosswalk"] is True
    assert before["first_stop_front_x_m"] == -9 and past["first_stop_front_x_m"] == -4
    assert before["legal_compliance"] == past["legal_compliance"] == "unassessed"
    negative = []
    source = context()
    source.pop("near_crosswalk_sha256")
    negative.append(reject("missing_crosswalk_source", source, trace("before_crosswalk"), "source hash"))
    source = context()
    source["near_side_crosswalk"] = False
    negative.append(reject("absent_crosswalk_branch", source, trace("before_crosswalk"), "crosswalk required"))
    source = context()
    source["safety_stop_requirement_sourced"] = False
    negative.append(reject("unsourced_safety_condition", source, trace("before_crosswalk"), "unsourced"))
    negative.append(reject("short_capture", context(), trace("before_crosswalk")[:-1], "Incomplete"))
    rows = trace("before_crosswalk")
    rows[200]["source_cameras"].pop("crosswalk_side")
    negative.append(reject("missing_camera", context(), rows, "camera"))
    rows = trace("before_crosswalk")
    rows[200]["native_frame"] = rows[199]["native_frame"]
    negative.append(reject("duplicate_native_frame", context(), rows, "Native frame"))
    proof = {"format": "worker-cpu-yield-crosswalk-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "scenes": scenes, "positive": {"before_crosswalk": before, "past_crosswalk": past},
             "negative": negative}
    path = Path(__file__).with_name("yield-crosswalk-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
