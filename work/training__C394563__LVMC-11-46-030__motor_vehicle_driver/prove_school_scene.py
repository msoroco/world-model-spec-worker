"""CPU authored-scene and warning-controller proof, not Native motion."""

import copy
import hashlib
import json
from pathlib import Path

from school_warning_scene import controller_command, scene_request, validate_request


def reject(label, fn, expected):
    try:
        fn()
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    far, near = scene_request("probe_1"), scene_request("probe_2")
    positive = [validate_request(far), validate_request(near)]
    assert far["road_opendrive"] == near["road_opendrive"]
    for key in ("school_pedestrian_lane", "warning", "child", "cameras"):
        assert far[key] == near[key]
    assert far["vehicle"]["start_xyz"] == near["vehicle"]["start_xyz"]
    assert far["vehicle"]["requested_stop_center_x_m"] < near["vehicle"]["requested_stop_center_x_m"]
    assert controller_command("probe_1", 0, -65, 5, True, None)["phase"] == "approach"
    assert controller_command("probe_1", 100, -17, 1, True, None)["phase"] == "brake_or_hold"
    assert controller_command("probe_1", 250, -17, 0, False, "signal_stopped")["phase"] == "released"
    assert controller_command("probe_1", 250, -17, 0, False, None)["phase"] == "await_sourced_release"
    missing_camera = copy.deepcopy(far)
    missing_camera["cameras"].pop()
    false_child = copy.deepcopy(far)
    false_child["child"]["age_status_verified"] = True
    negative = [
        reject("unknown_case", lambda: scene_request("none"), "Unknown"),
        reject("bad_warning_prop", lambda: scene_request("probe_1", warning_blueprint="vehicle.car"), "warning device"),
        reject("missing_camera", lambda: validate_request(missing_camera), "Four source camera"),
        reject("false_child_claim", lambda: validate_request(false_child), "cannot assert"),
        reject("overshot_without_release", lambda: controller_command("probe_1", 200, 0, 3, True, None), "overshot"),
        reject("unknown_release", lambda: controller_command("probe_1", 250, -17, 0, False, "timer"), "warning or release"),
    ]
    proof = {"format": "worker-cpu-school-warning-scene-proof", "passed": True,
             "diagnostic_only": True, "native_scene_executed": False,
             "positive": positive, "negative": negative,
             "fixed_condition_checks": ["road", "school lane", "warning actor", "child request", "cameras"],
             "difference": "requested stop centre station only"}
    path = Path(__file__).with_name("school-scene-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
