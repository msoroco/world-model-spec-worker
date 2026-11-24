"""CPU authored scene and controller checks; no Native motion is claimed."""

import copy
import hashlib
import json
from pathlib import Path

from emergency_scene import controller_command, scene_request, validate_request


def reject(label, fn, expected):
    try:
        fn()
    except ValueError as error:
        assert expected in str(error), (label, str(error))
        return {"test": label, "rejected": str(error)}
    raise AssertionError(f"{label} unexpectedly passed")


if __name__ == "__main__":
    slow, fast = scene_request("probe_1"), scene_request("probe_2")
    positive = [validate_request(slow), validate_request(fast)]
    assert slow["road_opendrive"] == fast["road_opendrive"]
    for key in ("emergency", "officer_direction", "officer_source_verified", "cameras"):
        assert slow[key] == fast[key]
    assert slow["ego"]["start_xyz"] == fast["ego"]["start_xyz"]
    assert slow["ego"]["requested_ego_speed_mps"] < fast["ego"]["requested_ego_speed_mps"]
    assert slow["ego"]["requested_surface_gap_m"] > fast["ego"]["requested_surface_gap_m"]
    assert controller_command("probe_1", 100, 8, -40, True, True)["phase"] == "approach_decelerate"
    assert controller_command("probe_1", 150, 5, -20, True, True)["phase"] == "approach_hold"
    assert controller_command("probe_2", 100, 5, -40, True, True)["phase"] == "approach_accelerate"
    missing_camera = copy.deepcopy(slow)
    missing_camera["cameras"].pop()
    false_authorization = copy.deepcopy(slow)
    false_authorization["emergency"]["authorization_verified"] = True
    negative = [
        reject("unknown_case", lambda: scene_request("none"), "Unknown"),
        reject("invalid_blueprint", lambda: scene_request("probe_1", emergency_blueprint="walker.pedestrian.0001"), "Vehicle blueprint"),
        reject("missing_camera", lambda: validate_request(missing_camera), "Four source camera"),
        reject("false_authorization", lambda: validate_request(false_authorization), "cannot assert"),
        reject("bad_observation", lambda: controller_command("probe_1", 0, 5, -70, None, True), "Invalid observed"),
    ]
    proof = {"format": "worker-cpu-emergency-scene-proof", "passed": True,
             "diagnostic_only": True, "native_scene_executed": False,
             "positive": positive, "negative": negative,
             "fixed_conditions": ["road", "emergency actor", "lamp request", "officer request", "cameras"],
             "difference": "requested ego speed and lateral surface gap as a coupled caution probe"}
    path = Path(__file__).with_name("emergency-scene-proof.json")
    path.write_text(json.dumps(proof, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"passed": True, "negative_count": len(negative),
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
