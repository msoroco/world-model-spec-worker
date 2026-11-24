"""CPU authored road/paired meeting request checks, not Native motion."""

import copy
import hashlib
import json
from pathlib import Path

from meeting_scene import scene_request, validate_request


def reject(label, fn, expected):
    try:
        fn()
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    less, more = scene_request("0.45"), scene_request("0.55")
    positive = [validate_request(less), validate_request(more)]
    assert less["road_opendrive"] == more["road_opendrive"]
    for key in ("oncoming", "cameras", "paved_bounds_y_m", "paved_center_y_m"):
        assert less[key] == more[key]
    assert less["ego"]["start_xyz"][0] == more["ego"]["start_xyz"][0]
    assert less["ego"]["start_xyz"][1] > more["ego"]["start_xyz"][1]
    missing_camera = copy.deepcopy(less)
    missing_camera["cameras"].pop()
    false_native = copy.deepcopy(less)
    false_native["native_road_verified"] = True
    negative = [reject("unknown_case", lambda: scene_request("none"), "Unknown"),
                reject("invalid_blueprint", lambda: scene_request("0.45", vehicle_blueprint="walker.pedestrian.0001"), "blueprint"),
                reject("missing_camera", lambda: validate_request(missing_camera), "Four source camera"),
                reject("false_native", lambda: validate_request(false_native), "cannot assert")]
    proof = {"format": "worker-cpu-opposite-meeting-scene-proof", "passed": True,
             "diagnostic_only": True, "native_scene_executed": False,
             "positive": positive, "negative": negative,
             "fixed_conditions": ["road", "oncoming vehicle", "camera plan", "ego longitudinal origin"],
             "difference": "requested ego lateral placement for the two footprint-fraction probes"}
    path = Path(__file__).with_name("meeting-scene-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
