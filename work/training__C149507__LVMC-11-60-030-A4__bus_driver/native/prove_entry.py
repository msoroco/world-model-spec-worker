"""CPU-only bus entry policy checks, never physical evidence."""

import copy
import hashlib
import json
from pathlib import Path

from entry import FRAMES, WHEEL_GAP_M, check_observed, target


def fixture(case):
    return [{"video_frame": i, "time_s": i / 20,
             "observed_right_front_wheel_gap_m": WHEEL_GAP_M[case],
             "observed_bus_speed_mps": 4.0 if i < 100 else 0.0,
             "loading_observed": i >= 100} for i in range(FRAMES)]


def reject(label, case, rows, expected):
    try:
        check_observed(case, rows)
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    near, far = fixture("near"), fixture("far")
    positive = [check_observed("near", near), check_observed("far", far)]
    assert all(target("near", i)["target_x_m"] == target("far", i)["target_x_m"]
               and target("near", i)["other_vehicle_target_speed_mps"] == target("far", i)["other_vehicle_target_speed_mps"]
               for i in range(FRAMES))
    assert target("near", 100)["target_right_front_wheel_gap_m"] == 0.30
    assert target("far", 100)["target_right_front_wheel_gap_m"] == 0.70
    bad = copy.deepcopy(near)
    bad[250]["observed_bus_speed_mps"] = 2.0
    negative = [reject("moving_during_loading", "near", bad, "loading position"),
                reject("wrong_wheel_gap", "far", near, "loading position"),
                reject("short_capture", "near", near[:-1], "incomplete 30-second")]
    proof = {"format": "worker-cpu-bus-entry-proof", "passed": True,
             "diagnostic_only": True, "original_native_observed": False,
             "positive": positive, "negative": negative}
    path = Path(__file__).with_name("entry-proof.json")
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"passed": True, "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
