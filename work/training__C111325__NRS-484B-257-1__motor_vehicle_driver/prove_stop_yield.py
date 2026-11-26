"""Source-shaped CPU diagnostic; synthetic motion is not a Native observation."""

import hashlib
import json
from pathlib import Path

from measure_stop_yield import CAMERAS, FRAMES, HASHES, measure
from stop_yield_scene import request, validate


def context():
    result = {"source_kind": "original_native_stop_yield_readback", "sign": "stop",
              "marked_stop_line": True, "police_controlling": False, "signal_controlling": False,
              "stop_line_x_m": -6, "intersection_near_x_m": -3.5, "intersection_far_x_m": 3.5}
    for name in HASHES:
        result[name + "_sha256"] = hashlib.sha256(("synthetic-fixture:" + name).encode()).hexdigest()
    return result


def trace(case):
    rows = []
    for i in range(FRAMES):
        if case == "complete_stop_then_yield":
            x = -45 + min(i, 100) * 0.3575 if i <= 100 else (-9.25 if i < 250 else -9.25 + (i - 250) * 0.25)
            speed = 0 if 100 <= i < 250 else (7.15 if i < 100 else 5)
        elif case == "roll_through_conflict":
            x, speed = -45 + i * 0.25, 5
        else:
            raise ValueError("Unknown fixture")
        rows.append({"video_frame": i, "native_frame": 900000 + i, "time_s": i / 20,
                     "source_cameras": {name: i for name in CAMERAS},
                     "ego_x_m": x, "ego_speed_mps": speed, "ego_length_m": 4.5,
                     "through_vehicle_y_m": -50 + i * 0.25,
                     "through_vehicle_speed_mps": 5})
    return rows


def reject(label, source, rows, expected):
    try:
        measure(source, rows)
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(label + " unexpectedly passed")


if __name__ == "__main__":
    scenes = {case: validate(request(case)) for case in ("complete_stop_then_yield", "roll_through_conflict")}
    stopped = measure(context(), trace("complete_stop_then_yield"))
    rolling = measure(context(), trace("roll_through_conflict"))
    assert stopped["pre_line_stopped_frame_count"] >= 100
    assert rolling["pre_line_stopped_frame_count"] == 0
    assert stopped["first_intersection_entry_frame"] > rolling["first_intersection_entry_frame"]
    assert stopped["simultaneous_intersection_occupancy_frames"] == []
    assert rolling["simultaneous_intersection_occupancy_frames"]
    assert stopped["legal_compliance"] == rolling["legal_compliance"] == "unassessed"
    negative = []
    source = context()
    source.pop("stop_line_sha256")
    negative.append(reject("missing_line_source", source, trace("complete_stop_then_yield"), "source hash"))
    source = context()
    source["signal_controlling"] = True
    negative.append(reject("signal_exception", source, trace("complete_stop_then_yield"), "exception"))
    source = context()
    source["marked_stop_line"] = False
    negative.append(reject("no_marked_line", source, trace("complete_stop_then_yield"), "marked line"))
    negative.append(reject("short_capture", context(), trace("complete_stop_then_yield")[:-1], "Incomplete"))
    rows = trace("complete_stop_then_yield")
    rows[200]["source_cameras"].pop("reference_corner")
    negative.append(reject("missing_camera", context(), rows, "camera"))
    rows = trace("complete_stop_then_yield")
    rows[200]["native_frame"] = rows[199]["native_frame"]
    negative.append(reject("duplicate_native_frame", context(), rows, "Native frame"))
    proof = {"format": "worker-cpu-stop-yield-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "scenes": scenes, "positive": {"complete_stop_then_yield": stopped,
                                     "roll_through_conflict": rolling}, "negative": negative}
    path = Path(__file__).with_name("stop-yield-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
