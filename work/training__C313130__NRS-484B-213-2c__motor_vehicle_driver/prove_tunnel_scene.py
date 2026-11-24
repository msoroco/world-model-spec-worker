"""CPU construction-policy proof; no original CARLA world or pixels."""

import copy
import hashlib
import json
from pathlib import Path

from tunnel_scene import command, scene_request, validate_request


def reject(label, fn, expected):
    try:
        fn()
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    right, left = scene_request("probe_1"), scene_request("probe_2")
    positive = [validate_request(right), validate_request(left)]
    assert right["road_opendrive"] == left["road_opendrive"]
    for key in ("tunnel", "occluder", "cameras"):
        assert right[key] == left[key]
    assert right["vehicle"]["start_xyz"] == left["vehicle"]["start_xyz"]
    assert command("probe_1", 0, -65, -1.75, 4)["target_y_m"] < 0
    assert command("probe_2", 0, -65, -1.75, 4)["steer"] > 0
    assert command("probe_2", 180, -28, 1.75, 4)["target_y_m"] > 0
    bad_camera = copy.deepcopy(right)
    bad_camera["cameras"].pop()
    false_physical = copy.deepcopy(left)
    false_physical["tunnel"]["physical_tunnel_verified"] = True
    negative = [
        reject("unknown_case", lambda: scene_request("none"), "Unknown"),
        reject("bad_tunnel_prop", lambda: scene_request("probe_1", tunnel_blueprint="vehicle.car"), "tunnel prop"),
        reject("missing_camera", lambda: validate_request(bad_camera), "Four source camera"),
        reject("false_physical_claim", lambda: validate_request(false_physical), "cannot assert"),
        reject("late_left_shift", lambda: command("probe_2", 180, -28, -1.5, 4), "not attained"),
        reject("missing_native_speed", lambda: command("probe_1", 0, -65, -1.75, None), "pose or speed"),
    ]
    proof = {"format": "worker-cpu-tunnel-scene-proof", "passed": True,
             "diagnostic_only": True, "native_scene_executed": False,
             "positive": positive, "negative": negative,
             "fixed_condition_checks": ["road", "tunnel", "occluder", "camera setup", "vehicle start"],
             "difference": "requested lateral target on approach"}
    path = Path(__file__).with_name("tunnel-scene-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
