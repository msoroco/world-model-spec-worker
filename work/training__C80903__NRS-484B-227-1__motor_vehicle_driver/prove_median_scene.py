"""CPU authored median-scene checks; no Native execution claimed."""

import copy
import hashlib
import json
from pathlib import Path

from median_turn_scene import scene_request, validate_request


def reject(label, action, expected):
    try:
        action()
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    opening, continuous = scene_request("probe_1"), scene_request("probe_2")
    positive = [validate_request(opening), validate_request(continuous)]
    assert opening["road_opendrive"] == continuous["road_opendrive"]
    assert opening["median"] == continuous["median"]
    assert opening["cameras"] == continuous["cameras"]
    assert opening["ego"]["start_xyz"] == continuous["ego"]["start_xyz"]
    assert 0 <= opening["ego"]["requested_left_turn_crossing_x_m"] <= 10
    assert 10 < continuous["ego"]["requested_left_turn_crossing_x_m"] < 25
    missing_camera = copy.deepcopy(opening)
    missing_camera["cameras"].pop()
    false_authority = copy.deepcopy(opening)
    false_authority["median"]["public_authority_verified"] = True
    negative = [reject("unknown_case", lambda: scene_request("none"), "Unknown"),
                reject("invalid_blueprint", lambda: scene_request("probe_1", ego_blueprint="walker.pedestrian.0001"), "blueprint"),
                reject("missing_camera", lambda: validate_request(missing_camera), "Four source camera"),
                reject("false_authority", lambda: validate_request(false_authority), "cannot assert")]
    proof = {"format": "worker-cpu-median-scene-proof", "passed": True,
             "diagnostic_only": True, "native_scene_executed": False,
             "positive": positive, "negative": negative,
             "fixed_conditions": ["two roadways", "median geometry", "ego origin", "cameras"],
             "difference": "requested crossing station only"}
    path = Path(__file__).with_name("median-scene-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
