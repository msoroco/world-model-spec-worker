"""CPU authored crossing geometry and walker controller checks."""

import copy
import hashlib
import json
from pathlib import Path

from scene import scene_request, validate_request, walker_command


def reject(label, action, expected):
    try:
        action()
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    marked, unmarked = scene_request("marked_crosswalk"), scene_request("unmarked_midblock")
    positive = [validate_request(marked), validate_request(unmarked)]
    assert marked["road_opendrive"] == unmarked["road_opendrive"]
    for key in ("intersections", "marked_crosswalk", "cameras", "native_adjacency_verified", "native_devices_operating_verified"):
        assert marked[key] == unmarked[key]
    assert marked["pedestrian"]["start_xyz"][0] == 40
    assert unmarked["pedestrian"]["start_xyz"][0] == 60
    assert walker_command("marked_crosswalk", 0, [40, -10, 0.2], True)["phase"] == "approach_wait"
    assert walker_command("marked_crosswalk", 260, [40, -3.8, 0.2], True)["phase"] == "cross"
    assert walker_command("marked_crosswalk", 500, [40, 10, 0.2], True)["phase"] == "finished"
    assert walker_command("unmarked_midblock", 260, [60, -3.8, 0.2], False)["phase"] == "cross"
    missing_camera = copy.deepcopy(marked)
    missing_camera["cameras"].pop()
    false_native = copy.deepcopy(marked)
    false_native["native_adjacency_verified"] = True
    negative = [reject("unknown_case", lambda: scene_request("none"), "Unknown"),
                reject("invalid_blueprint", lambda: scene_request("marked_crosswalk", pedestrian_blueprint="vehicle.car"), "pedestrian blueprint"),
                reject("missing_camera", lambda: validate_request(missing_camera), "Four source camera"),
                reject("false_native_claim", lambda: validate_request(false_native), "cannot assert"),
                reject("missing_pose", lambda: walker_command("marked_crosswalk", 260, None, True), "pose missing"),
                reject("missing_device_state", lambda: walker_command("marked_crosswalk", 260, [40, -3.8, 0.2], None), "operating observation")]
    proof = {"format": "worker-cpu-pedestrian-crossing-scene-proof", "passed": True,
             "diagnostic_only": True, "native_scene_executed": False,
             "positive": positive, "negative": negative,
             "fixed_conditions": ["road", "intersection pair", "device pair", "marked crossing", "pedestrian controller", "cameras"],
             "difference": "requested pedestrian crossing x only"}
    path = Path(__file__).with_name("scene-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
