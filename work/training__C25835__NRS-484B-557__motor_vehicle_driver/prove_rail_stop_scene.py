"""CPU proof of authored scene requests; no CARLA world is created."""

import copy
import hashlib
import json
from pathlib import Path

from rail_stop_scene import scene_request, validate_request


def reject(label, fn, expected):
    try:
        fn()
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    first, second = scene_request("probe_1"), scene_request("probe_2")
    positive = [validate_request(first), validate_request(second)]
    assert first["road_opendrive"] == second["road_opendrive"]
    for key in ("rails", "stop_sign", "occluder", "cameras"):
        assert first[key] == second[key]
    assert first["vehicle"]["requested_stop_center_x_m"] < second["vehicle"]["requested_stop_center_x_m"]
    missing_camera = copy.deepcopy(first)
    missing_camera["cameras"].pop()
    false_governance = copy.deepcopy(first)
    false_governance["stop_sign"]["official_governance_verified"] = True
    negative = [
        reject("unknown_case", lambda: scene_request("unknown"), "Unknown"),
        reject("non_sign_prop", lambda: scene_request("probe_1", stop_sign_blueprint="vehicle.car"), "stop sign"),
        reject("missing_source_camera", lambda: validate_request(missing_camera), "Four source-camera"),
        reject("authored_governance_assertion", lambda: validate_request(false_governance), "cannot assert"),
    ]
    proof = {"format": "worker-cpu-rail-stop-scene-proof", "passed": True,
             "diagnostic_only": True, "native_scene_executed": False,
             "positive": positive, "negative": negative,
             "fixed_condition_checks": ["identical road", "identical rails", "identical stop sign", "identical occluder", "identical cameras"],
             "difference": "requested stop centre station only"}
    path = Path(__file__).with_name("rail-stop-scene-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
